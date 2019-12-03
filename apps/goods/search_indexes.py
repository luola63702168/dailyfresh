from haystack import indexes  # 定义索引类

from goods.models import GoodsSKU


# 索引类名格式:模型类名+Index
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    # 索引字段 use_template=True说明文件，templates/search/indexes/(索引对应的类所在的项目文件名)/（模型类名小写）_test.txt）
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        return GoodsSKU

    def index_queryset(self, using=None):
        """建立索引数据"""
        return self.get_model().objects.all()

# python manage.py rebuild_index 配置好之后 这个命令来生成对应的索引文件
