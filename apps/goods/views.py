from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.core.cache import cache  # 设置缓存
from django.core.paginator import Paginator  # 设置分页
from django_redis import get_redis_connection

from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from order.models import OrderGoods


# Create your views here.


class IndexView(View):
    '''首页'''

    def get(self, request):
        '''显示首页'''
        context = cache.get('index_page_data')
        if context is None:
            types = GoodsType.objects.all()
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
            for type in types:
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by(
                    'index')
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
                type.image_banners = image_banners
                type.title_banners = title_banners
            context = {'types': types,
                       'goods_banners': goods_banners,
                       'promotion_banners': promotion_banners,
                       }
            cache.set('index_page_data', context, 3600)

        user = request.user
        car_count = 0  # 默认值
        if user.is_authenticated:
            con = get_redis_connection("default")
            cart_key = "cart_%d" % user.id
            car_count = con.hlen(cart_key)
        context.update(car_count=car_count)
        return render(request, 'index.html', context)


# /goods/商品id
class DetailView(View):
    '''详情页'''

    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))
        types = GoodsType.objects.all()
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            conn.lrem(history_key, 0, goods_id)
            conn.lpush(history_key, goods_id)
            conn.ltrim(history_key, 0, 4)
        context = {'sku': sku,
                   'types': types,
                   'sku_orders': sku_orders,
                   'new_skus': new_skus,
                   'same_spu_skus': same_spu_skus,
                   'cart_count': cart_count}
        return render(request, 'detail.html', context)


# /list?type_id=种类id&page=页码&sort=排序方式
class ListView(View):
    '''显示列表详情页'''

    def get(self, request, type_id, page):
        '''显示列表页'''
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))
        types = GoodsType.objects.all()
        sort = request.get('sort')
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 分页
        paginator = Paginator(skus, 1)
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = 1
        skus_page = paginator.page(page)
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)
        context = {'type': type, 'types': types,
                   'skus_page': skus_page,
                   'new_skus': new_skus,
                   'cart_count': cart_count,
                   'pages': pages,
                   'sort': sort
                   }

        return render(request, 'list.html', context)
