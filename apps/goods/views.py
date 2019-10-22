from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.core.cache import cache  # 设置缓存
from django.core.paginator import Paginator  # 设置分页
from goods.models import GoodsType,GoodsSKU,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from order.models import OrderGoods
from django_redis import get_redis_connection
# Create your views here.


class IndexView(View):
    '''首页'''
    def get(self,request):
        '''显示首页'''
        # 尝试从缓存中获取数据
        context=cache.get('index_page_data')
        if context is None:  # 说明缓存中没有数据
            # print("测试")
            # 获取商品的种类信息
            types = GoodsType.objects.all()
            # 获取首页轮播商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')  # 升序（-index降序）
            # 获取首页促销活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
            # 获取首页分类商品展示信息
            # type_goods_banners = IndexTypeGoodsBanner.objects.all()
            for type in types:  # (外键type=“独立”的GoodsType)
                # 获取type种类首页分类商品的图片展示信息
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')  # 外键其实就是数据库中一条数据的引用
                # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
                # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
                type.image_banners = image_banners
                type.title_banners = title_banners
            context = {'types': types,
                       'goods_banners': goods_banners,
                       'promotion_banners': promotion_banners,
                       }
            # 设置缓存
            # key value timeout（过期时间的设置是为了避免无人清除缓存而导致缓存一直存在）
            cache.set('index_page_data',context,3600)

        # 获取用户购物车商品的数目
        user = request.user
        car_count=0  # 默认值
        if user.is_authenticated:
            con = get_redis_connection("default")
            cart_key = "cart_%d" % user.id
            car_count = con.hlen(cart_key)
        context.update(car_count=car_count)  # 字典的更新，存在便更新，不存在便添加(car_count=car_count 理解为键值对)
        # 使用模板
        return render(request, 'index.html',context)


# /goods/商品id
class DetailView(View):
    '''详情页'''
    def get(self,request,goods_id):
        '''显示详情页'''
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在，跳转至首页
            return redirect(reverse('goods:index'))
        # 查询商品分类信息
        types = GoodsType.objects.all()
        # 获取商品评论信息
        # sku_orders = OrderGoods.objects.filter(sku=sku)
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息(type=sku.type 确定是哪个商品分类的新品)
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]  # -代表降序

        # 获取和该商品同一个spu的其他sku商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)
            # 添加用户的历史浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d'%user.id
            # 移除列表的goods_id
            conn.lrem(history_key,0,goods_id)
            # 左侧插入该id
            conn.lpush(history_key,goods_id)
            #  只保存用户最新浏览的五条信息
            conn.ltrim(history_key,0,4)
        context = {'sku': sku,
                   'types': types,
                   'sku_orders': sku_orders,
                   'new_skus': new_skus,
                   'same_spu_skus':same_spu_skus,
                   'cart_count': cart_count}
        return render(request,'detail.html',context)


# 种类id 页码 排序方式
# restful api -> 请求一种资源
# /list?type_id=种类id&page=页码&sort=排序方式
# /list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式
class ListView(View):
    '''显示列表详情页'''
    def get(self,request,type_id,page):
        '''显示列表页'''
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 种类不存在
            return redirect(reverse('goods:index'))
        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取排序的方式(# 获取分类商品信息)
        # sort=default 按照默认id排序
        # sort=price 按照商品价格排序
        # sort=hot 按照商品销量排序
        sort = request.get('sort')
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对数据进行分页(可遍历对象，多少为数据为一页)
        paginator=Paginator(skus,1)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:  # num_pages 页码总数
            page=1
        # 返回这个页码对应的内容(也是第page页的Page的实例对象)
        skus_page = paginator.page(page)

        # 控制最多显示多少页
        # 1.总页数小于5页，页面上显示所有页码
        # 2.如果当前页是前3页，显示1-5页
        # 3.如果当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]
        # 获取购物车数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)
        # 组织模板上下文
        context = {'type': type, 'types': types,
                   'skus_page': skus_page,
                   'new_skus': new_skus,
                   'cart_count': cart_count,
                   'pages': pages,
                   'sort': sort
                   }

        return render(request,'list.html',context)




























