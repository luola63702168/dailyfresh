# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader,RequestContext  # 加载静态模板文件
import time
from django_redis import get_redis_connection


# 在任务处理者一端加这个几行代码（django环境的初始化配置文件）
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")  # wsgi.py
django.setup()

from goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner  # 需要放到Django环境初始化的下面（要不然启动celery的时候会报一个找不到的错误）

# 创建一个celery类的实例对象
app = Celery('clery_tasks.tasks',broker='redis://127.0.0.1:6379/8')


# 定义发送函数
@app.task
def send_register_active_email(to_email,username,token):
    '''发送激活邮件'''
    subject = '天天生鲜欢迎信息'
    message = ''
    html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户，跳转至登录页成功即为激活<br/><a href="http://127.0.0.1:8000/user/active/%s">http:127.0.0.1:8000/user/active/%s</a>' % (
    username, token, token)
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    #  html_message 并不是第五个参数，所以要使用关键字参数
    send_mail(subject, message, sender, receiver, html_message=html_message)
    time.sleep(5)

@app.task
def generate_static_index_html():
    '''产生静态页面'''
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
        image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by(
            'index')  # 外键其实就是数据库中一条数据的引用
        # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
        title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
        # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
        type.image_banners = image_banners
        type.title_banners = title_banners

    context = {'types': types,
               'goods_banners': goods_banners,
               'promotion_banners': promotion_banners,
               }
    # 使用模板
    # return render(request, 'index.html', context)
    # 1加载模板文件
    temp = loader.get_template('static_index.html')
    # 2定义模板上下文(可省略)
    # context = RequestContext(context)
    # 3模板渲染
    static_index_html = temp.render(context)

    # 生成首页对应的静态页面(settings.BASE_DIR 是项目所在路径)
    save_path=os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w',encoding='utf-8') as f:
        f.write(static_index_html)


# celery -A celery_tasks.tasks worker -l info 启动服务
# celery中的三个部分：任务的发出者，中间人，任务的处理着可以在同一台电脑上启动，也可以不在同一台电脑上（如果在别的电脑上，那么是需要我们这个项目文件的也就是dailyfresh）。

#  generate_static_index_html.delay() 启动这个函数,便会在对应目录中生成这个文件
# 可以通过修改linux上的nginx服务器的配置文件从而配置端口（80）(nginx.conf)，在静态文件的生成目录中将其及该静态文件所需要的js，css资源返回(在配置中要考虑其请求对应的静态文件及index.html文件的目录)
# 此项目暂未配置（因为我是在同一台电脑上启动的，但是我的电脑没有装nginx，而且。。。我的电脑还是win）




















