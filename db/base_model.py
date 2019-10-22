from django.db import models


class BaseModel(models.Model):
    '''模型抽象基类'''
    # 因为每个模型类都有上面三个字段,所以要创建一个抽象模型类
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    is_delete = models.BooleanField(default=False, verbose_name='删除标记')

    class Meta:
        # 只有这样才说明这是一个抽象模型类
        abstract = True

