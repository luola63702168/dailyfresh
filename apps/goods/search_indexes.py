# 名字是固定的
# 定义索引类
from haystack import indexes
# 导入你的模型类
from goods.models import GoodsSKU


# 指定对于某个类的某些数据建立索引
# 索引类名格式:模型类名+Index
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    # 索引字段 use_template=True 会指定表中的哪些字段建立索引文件的说明文件，它的会放在一个文件中（这个文件要建在templates下面（search/indexes/(索引对应的类所在的项目文件名)/（模型类名小写）_test.txt）
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        # 返回你的模型类
        return GoodsSKU

    # 对谁建立索引数据
    def index_queryset(self, using=None):
        return self.get_model().objects.all()


# 一般就是这个流程，是不需要去改变的
# python manage.py rebuild_index 配置好之后 这个命令来生成对应的索引文件
























