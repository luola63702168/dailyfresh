from django.contrib import admin
from django.core.cache import cache

from goods.models import GoodsType, IndexPromotionBanner, IndexGoodsBanner, IndexTypeGoodsBanner


# Register your models here.


class BaseModelAdmin(admin.ModelAdmin):
    '''实现管理员修改后台数据库后，重新生成静态页面'''

    def save_model(self, request, obj, form, change):
        '''新增或更新表中的数据时调用'''
        super().save_model(request, obj, form, change)
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()
        cache.delete('index_page_data')

    # fixme测试发现，删除操作需要点进商品详情管理页面进行删除时，才会重新生成静态页面
    def delete_model(self, request, obj):
        '''删除表中的数据时调用'''
        super().delete_model(request, obj)
        # 发出任务
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()
        cache.delete('index_page_data')


class GoodsTypeAdmin(BaseModelAdmin):
    pass


class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass


admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
