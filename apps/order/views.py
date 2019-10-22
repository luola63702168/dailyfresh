from django.shortcuts import render
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction  # 开启事务
from django.core.urlresolvers import reverse
from django.views.generic import View
from django_redis import get_redis_connection
from goods.models import GoodsSKU
from user.models import Address
from utils.mixin import LoginRequiredMixin
from order.models import OrderInfo,OrderGoods
from datetime import datetime
from alipay import AliPay
import os
# Create your views here.

# /order/place
class OrderPlaceView(LoginRequiredMixin,View):
    '''提交订单页面显示'''
    def post(self,request):
        '''提交订单页面的显示'''
        user = request.user
        # 获取参数
        sku_ids = request.POST.getlist('sku_ids')
        # 校验参数
        if not sku_ids:
            return redirect(reverse('cart:show'))
        # redis
        coon = get_redis_connection('default')
        cart_key = "cart_%d" % user.id
        skus = []
        total_count = 0
        total_price = 0
        # 遍历sku_ids获取用户要购买的商品的信息
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            count = coon.hget(cart_key,sku_id)
            amount = sku.price*int(count)
            # 动态的给sku添加属性
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += int(count)
            total_price += amount
        # 运费:实际开发的时候，属于一个子系统
        transit_price = 10  # 写死
        # 实付款
        total_pay = transit_price + total_price
        addrs = Address.objects.filter(user)

        # 组织上下文
        sku_ids = ','.join(sku_ids)  # [1,25]->1,25
        # 组织模板上下文
        context = {'skus': skus,
                   'total_count': total_count,
                   'total_price': total_price,
                   'transit_price': transit_price,
                   'total_pay': total_pay,
                   'addrs': addrs,
                   'sku_ids': sku_ids}
        return render(request, 'place_order.html', context)


# 前端传递的参数:地址id(addr_id) 支付方式(pay_method) 用户要购买的商品id字符串(sku_ids)
# mysql事务: 一组sql操作，要么都成功，要么都失败
# 高并发:秒杀
# 支付宝支付
class OrderCommitView(View):
    '''订单创建(悲观锁)'''
    @transaction.atomic()  # 该函数所有涉及数据库的操作都形成一个事务(其实可以不用设置保存点的---.----)
    def post(self,request):
        '''订单创建'''
        user=request.user
        if not user.is_authenticated:
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')  # 1,3（字符串）
        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2, 'errmsg':'非法的支付方式'})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'地址非法'})

        # todo: 创建订单核心业务
        # 组织参数
        # 订单id: 20171122181630+用户id（保证id唯一）
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10  # 写死
        # 总数目和总金额(先假设一个默认值，计算出来之后再修改)---因为df_order_goods存在OrderInfo外键的原因，所以必须要先创建这个表
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo: 向df_order_info表中添加一条记录（订单表）
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)
            # todo: 用户的订单中有几个商品，需要向df_order_goods表（订单商品表）中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # sku = GoodsSKU.objects.get(id=sku_id)  # 不加锁的时候
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)  # 悲观锁 select * from df_goods_sku where id=17 for update;
                except:
                    # 商品不存在
                    # 回滚（只是事务的回滚，不是代码的回滚）
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                # 测试悲观锁
                # print('user:%d stock:%d'%(user.id,sku.stock))
                # import time
                # time.sleep(20)

                # 从redis中获取用户所要购买的商品的数量（在购物车页面中点击去结算的时候就会将数目写入redis了）
                count = conn.hget(cart_key, sku_id)
                # todo 判断商品库存
                if int(count)>sku.stock:  # 当两个进程都已经判断完这一项的时候，继续往下走，便出现了并发问题,所以要加锁。
                    # 回滚
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':6,'errmsg':'商品库存不足'})
                # todo: 向df_order_goods表中添加记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)
                # todo 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales -= int(count)
                sku.save()

                # todo 累加计算订单商品的总数量和总价格
                amount = sku.price * int(count)
                total_count += int(count)
                total_price += amount

            # todo 更新订单表中的商品总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            # 回滚
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        # 提交事务
        transaction.savepoint_commit(save_id)
        # todo 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)  # *sku_ids 列表的拆包
        return JsonResponse({'res': 5, 'message': '创建成功'})


class OrderCommitView2(View):
    '''订单创建(乐观锁)'''
    @transaction.atomic()  # 该函数所有涉及数据库的操作都形成一个事务(其实可以不用设置保存点的---.----)
    def post(self,request):
        '''订单创建'''
        user=request.user
        if not user.is_authenticated:
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')  # 1,3（字符串）
        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2, 'errmsg':'非法的支付方式'})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'地址非法'})

        # todo: 创建订单核心业务
        # 组织参数
        # 订单id: 20171122181630+用户id（保证id唯一）
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10  # 写死
        # 总数目和总金额(先假设一个默认值，计算出来之后再修改)---因为df_order_goods存在OrderInfo外键的原因，所以必须要先创建这个表
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo: 向df_order_info表中添加一条记录（订单表）
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)
            # todo: 用户的订单中有几个商品，需要向df_order_goods表（订单商品表）中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):  # 避免乐观锁“两人买三件库存时”的bug
                    # 获取商品的信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        # 商品不存在
                        # 回滚（只是事务的回滚，不是代码的回滚）
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                    # 从redis中获取用户所要购买的商品的数量（在购物车页面中点击去结算的时候就会将数目写入redis了）
                    count = conn.hget(cart_key, sku_id)
                    # todo 判断商品库存
                    if int(count)>sku.stock:  # 当两个进程都已经判断完这一项的时候，继续往下走，便出现了并发问题,所以要加锁。
                        # 回滚
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':7,'errmsg':'商品库存不足'})

                    # todo 更新商品的库存和销量(乐观锁)
                    # sku.stock -= int(count)
                    # sku.sales -= int(count)
                    # sku.save()
                    orgin_stock = sku.stock
                    new_stock = orgin_stock-int(count)
                    new_sales = sku.sales+int(count)

                    # 测试乐观锁
                    # print('user:%d times:%d stock:%d'%(user.id,i,sku.stock))
                    # import time
                    # time.sleep(20)

                    # update df_goods_sku set stock = new_stock,sales=new_sales where id=sku_id and stock = orgin_stock
                    res = GoodsSKU.objects.filter(id=sku_id,stock=orgin_stock).update(stock=new_stock,sales=new_sales)  # 返回受影响的行数

                    if res == 0:
                        if i == 2:
                            # 尝试第三次了
                            transaction.savepoint_commit(sku_id)
                            return JsonResponse({'res':7,'errmsg':'下单失败请重新下单'})
                        else:
                            continue

                    # todo: 向df_order_goods表中添加记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # todo 累加计算订单商品的总数量和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount
                    # 如果一次就成功了，就跳出循环
                    break

            # todo 更新订单表中的商品总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

        except Exception as e:
            # 回滚
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        # 提交事务
        transaction.savepoint_commit(save_id)
        # todo 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)  # *sku_ids 列表的拆包
        return JsonResponse({'res': 5, 'message': '创建成功'})

# 并发问题的解决。
# 1，悲观锁--唉~肯定有人跟我抢东西，上锁。（查询库存的时候，拿锁，谁拿到谁才能操作（查））  （在数据库中加锁的语法是 select * from df_goods_sku where id=17 for update;）
# 2, 乐观锁-- 没人跟我抢，大不了我提交的时候再查一下看看。（查询数据的时候不加锁，在修改的时候进行判断（判断更新时的库存和之前查出的库存是否一致）） （update df_goods_sku set stock=0,sales=1 where id=17 and stock=1）
#     存在2人买3物仍不成功问题（有人在我下单之前下单了，修改了库存）：添加循环尝试多次即可。
#     存在重复读（mysql默认级别：repeatable read）：在日志文件中修改事物级别（read committed）。 // django2.0的版本就直接修改了事物级别
# 3，事物结束的时候，锁释放


# 在冲突比较少的时候 用乐观锁 （冲突比较多的时候要不停的尝试，浪费资源）
# 冲突比较多的时候就用 悲观锁 （冲突比较少的时候，上锁解锁浪费资源 ）
# 乐观锁重复代价比较大的时候，直接使用悲观锁。

# ajax post
# 前端传递的参数:订单id(order_id)
# /order/pay
class OrderPayView(View):
    '''订单支付'''
    def post(self, request):
        '''订单支付'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res':1, 'errmsg':'无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'订单错误'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016101300676042", # 应用id
            app_notify_url=None,  # 默认回调url(不能传空，异步返回的支付结果，由于本项目没有公网ip，所以填None)
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'), # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False（False代表不是沙箱环境）
        )

        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price+order.transit_price # Decimal
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id, # 订单id
            total_amount=str(total_pay), # 支付总金额
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})

# ajax post
# 前端传递的参数:订单id(order_id)
# /order/check
class CheckPayView(View):
    '''查看订单支付的结果'''
    def post(self, request):
        '''查询支付结果'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016090800464054",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付宝的交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(order_id)

            # response = {
            #         "trade_no": "2017032121001004070200176844", # 支付宝交易号
            #         "code": "10000", # 接口调用是否成功
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS", # 支付结果
            #         "total_amount": "20.00"
            # }

            code = response.get('code')

            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4 # 待评价
                order.save()
                # 返回结果
                return JsonResponse({'res':3, 'message':'支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 40004--业务处理失败（这是一个比较特殊的状态码），可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res':4, 'errmsg':'支付失败'})
# /order/comment/(?P<order_id>.+)
class CommentView(LoginRequiredMixin, View):
    """订单评论"""
    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品的小计
            amount = order_sku.count*order_sku.price
            # 动态给order_sku增加属性amount,保存商品小计
            order_sku.amount = amount
        # 动态给order增加属性order_skus, 保存订单商品信息
        order.order_skus = order_skus

        # 使用模板
        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):  # post提交的仍是这个地址，所以仍能捕获该参数
        """处理评论内容"""
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        # 循环获取订单中商品的评论内容
        for i in range(1, total_count + 1):
            # 获取评论的商品的id（name：sku_id对应的值便是商品的id）
            sku_id = request.POST.get("sku_%d" % i) # sku_1 sku_2
            # 获取评论的商品的内容
            content = request.POST.get('content_%d' % i, '') # cotent_1 content_2 content_3
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status = 5  # 已完成
        order.save()

        return redirect(reverse("user:order", kwargs={"page": 1}))
















