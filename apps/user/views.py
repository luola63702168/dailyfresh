from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from celery_tasks.tasks import send_register_active_email  # 使用celery
from django.core.mail import send_mail  # 发送邮件的函数
from django.core.paginator import Paginator
from django.contrib.auth import authenticate,login,logout  # 使用django自带的用户认证(检查账户密码是否正确、记住状态、清除状态)
from django.views.generic import View  # 类视图（使之在url配置中可以as_view）
from django.http import HttpResponse  # 返回字符串
from django.conf import settings  # 使用SECRET_KEY(邮件加密使用)
from utils.mixin import LoginRequiredMixin # 登录状态判断（包装login_required装饰器）
from user.models import User,Address
from goods.models import GoodsSKU
from order.models import OrderInfo,OrderGoods
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer  # 邮件加密数据
from itsdangerous import SignatureExpired  # 数据过期异常
from django_redis import get_redis_connection  # 使历史浏览记录存储在redis中
import re
# Create your views here.


# /user/register
def register(request):
    """注册"""
    if request.method=='GEt':
        # 显示注册页面
        return render(request, 'register.html')
    else:
        # 进行注册处理
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 校验用户名是否重复(get返回一条且只能有一条的数据，查不到的话会返回一个不存在的异常)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务处理：用户注册
        user = User.objects.create_user(username, email, password)  # 使用自带的用户认证系统的创建函数create_user()
        # 默认直接激活，我们修改这个激活
        user.is_active = 0
        user.save()
        # 返回应答
        return redirect(reverse('goods:index'))  # 反向解析


def register_handle(request):
    "进行注册处理"
    # 接受数据
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    # 进行数据校验
    if not all([username, password, email]):
        return render(request,'register.html', {'errmsg': '数据不完整'})
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
        return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
    if allow != 'on':
        return render(request, 'register.html', {'errmsg': '请同意协议'})
    # 校验用户名是否重复(get返回一条且只能有一条的数据，查不到的话会返回一个不存在的异常)
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # 用户名不存在
        user = None
    if user:
        # 用户名已存在
        return render(request, 'register.html', {'errmsg': '用户名已存在'})
    # 进行业务处理：用户注册
    user = User.objects.create_user(username, email, password)  # 使用自带的用户认证系统的创建函数create_user()
    # 默认直接激活，我们修改这个激活
    user.is_active = 0
    user.save()
    # 返回应答
    return redirect(reverse('goods:index'))  # 反向解析


# /user/register 类视图不同请求对应不同函数
# GET PUT DELETE OPTION
class ReisterView(View):
    """注册"""
    def get(self,request):
        """显示注册页面"""
        return render(request,'register.html')

    def post(self,request):
        """进行注册处理"""
        # 进行注册处理
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 校验用户名是否重复(get返回一条且只能有一条的数据，查不到的话会返回一个不存在的异常)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务处理：用户注册
        user = User.objects.create_user(username, email, password)  # 使用自带的用户认证系统的创建函数create_user(),会返回该user对象。
        # 默认直接激活，我们修改这个激活
        user.is_active = 0
        user.save()
        # 发送激活邮件，包含链接：http://127.0.0.1:8000/user/active/3
        # 激活链接中需要包含用户的身份信息，并且该身份信息还需要加密。

        # 加密用户的身份信息，生成激活的token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)  # bytes
        token = token.decode()
        # 发邮件
        send_register_active_email.delay(email, username, token)  # 装饰后具有的方法delay()
        # 返回应答
        return redirect(reverse('goods:index'))  # 反向解析


# /user/active/(?P<name>)
class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        '''进行用户激活'''
        # 解密，获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)  # 不要写load()函数了
            # 获取待激活的用户的id
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 说明激活链接已过期
            return HttpResponse('激活链接已过期')


# /user/login
class LoginView(View):
    '''登录'''
    def get(self, request):
        """显示登录页面"""
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')  # 也可以使用[]获取
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        '''处理登录请求'''
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})
        # 业务处理：登录校验（django自带的用户管理系统）
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户密码正确
            if user.is_active:
                # 用户已激活
                # 记录该用户的登录状态
                login(request, user)
                # 获取登录后要跳转的地址(默认为reverse('goods:index'))
                next_url = request.GET.get('next', reverse('goods:index'))
                # print(next_url)
                response = redirect(next_url)  # HttResponseRedirect对象
                # 判断用户是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                # 跳转到首页(在此之前需要设置cookie)
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})


# /user/logout
class LogoutView(View):
    '''退出登录'''
    def get(self,request):
        # 清除用户的session信息
        logout(request)  # redis中的session也会清除的
        # 跳转到首页
        return redirect(reverse('goods:index'))

# /user
class UserInfoView(LoginRequiredMixin,View):
    '''用户信息页'''
    def get(self, request):
        '''显示页面'''
        # 'page': 'user' 通过返回的page控制按钮中的样式（base_user_center.html）

        # Django会给request对象添加一个属性request.user还会返回到页面中
        # 如果用户未登录->user是AnonymousUser类的一个实例对象
        # 如果用户登录->user是User类的一个实例对象
        # request.user.is_authenticated()(base.html)

        # 获取并返回用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)  # user 是外键

        # 获取用户的历史浏览记录
        # from redis import StrictRedis
        # sr=StrictRedis(host='127.0.0.1',port='6379',db=9)
        # 返回的其实是StrictRedis对象
        con = get_redis_connection('default')  # 为什么传 default？ 参考了settings中的缓存配置，是为了连接到redis(返回的是StrictRedis一个对象)
        history_key = 'history_%d' % user.id
        # 获取用户最近浏览的五个商品id
        sku_ids = con.lrange(history_key, 0, 4)

        # 在数据库中进行查询1
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        # # 按照redis数据库中标准进行排序(查询到的时候就会返回，返回是按照id升序排列，而不是在redis中查到的那样)
        # goods_res = []
        # for a_id in sku_ids:
        #     for goods in goods_li:
        #         if a_id == goods.id:
        #             goods_res.append(goods)

        # 在数据库中进行查询2
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)
        # 组织上下文
        context={'page':'user','address':address,'goods_li':goods_li}
        return render(request, 'user_center_info.html',context)


# user/order/\d+
class UserOrderView(LoginRequiredMixin,View):
    '''用户订单页'''
    def get(self, request,page):
        '''显示页面'''
        # 获取用户的订单信息
        user = request.user
        orders =OrderInfo.objects.filter(user=user).order_by('-create_time')  # 在外键的关联查询中，也可以（filter(user_id=user.id)）---PS:Django中的外键为我们极大的方便了数据的查询（例：外键.外键.外键.字段）
        # 遍历获取每个订单对应的订单商品信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.id)
            # 获取每个商品的小计
            for order_sku in order_skus:
                amount = order_sku.count*order_sku.price
                # 动态的给该对象（order_sku）添加小计属性
                order_sku.amount = amount

            # 动态给order增加属性，保存订单状态标题
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态的给订单添加其对应的商品信息的属性
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 1)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
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

        # 组织上下文
        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'}

        return render(request, 'user_center_order.html',context)

# user/address
class AddressView(LoginRequiredMixin,View):
    '''用户地址页面'''
    def get(self, request):
        '''显示页面'''
        # 获取用户登录对应的User对象(django用户管理系统的特权~~)
        user = request.user
        # 获取地址
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None

        address = Address.objects.get_default_address(user)
        # 使用模板
        return render(request, 'user_center_site.html',{'page':'address','address':address})  # page 控制base_user_center.html中的选项卡

    def post(self,request):
        '''地址的添加'''
        # 接收数据
        receiver=request.POST.get('receiver')
        addr=request.POST.get('addr')
        zip_code=request.POST.get('zip_code')
        phone=request.POST.get('phone')
        # 校验数据
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errmsg':'数据不完整'})
        # 校验手机号
        if not re.match(r'1[3|4|5|6|7|8][0-9]{9}$',phone):
            return render(request,'user_center_site.html',{'errmsg':'手机格式不正确'})
        # 业务处理（地址添加）
        # 如果用户已存在默认收货地址，添加的地址不作为默认地址，否则作为默认地址
        # 获取用户登录对应的User对象
        user = request.user

        # print(str(type(user)))   #  <class 'django.utils.functional.SimpleLazyObject'>  返回的是一个特殊的对象，只需要用它做该做的事情就好了，没必要深追

        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        address = Address.objects.get_default_address(user)  # 这里定义了模型管理类
        if address:  # 说明查到了将设为is_default=False(使之新加的不是默认地址,也就是在查询并显示在模板文件中的时候是不会显示的)
            is_default = False
        else:
            is_default = True
        Address.objects.create(user=user,  # 这里便会把对应的外键给关联上了。
                               receiver=receiver,
                               addr=addr,
                               phone=phone,
                               zip_code=zip_code,
                               is_default=is_default)
        # 返回应答,刷新地址页面
        return redirect(reverse('user:address'))  # get 请求的方式






















