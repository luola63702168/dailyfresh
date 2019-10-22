from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client,get_tracker_conf
from django.conf import settings  # 代码优化
class FDFSStorage(Storage):
    '''fdfs文件存储类'''
    def __init__(self, client_conf=None, base_url=None):
        '''初始化传参'''
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf
        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    # 必须要有的一个方法
    def _open(self, name, mode='rb'):
        '''打开文件使用(该项目不需要打开文件)'''
        pass

    def _save(self, name, content):
        '''保存文件时使用
        :param name: 你选择上传文件的名字
        :param content: 包含上传文件内容的File对象
        '''

        # 创建一个 Fdfs_client对象
        # client = Fdfs_client('./utils/fdfs/client.conf')

        # 改进版本
        trackers = get_tracker_conf(self.client_conf)
        client = Fdfs_client(trackers)
        # 上传到该系统中
        res = client.upload_by_buffer(content.read())  # 返回的是字典

        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': local_file_name,
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }

        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传文件失败')
        # 获取返回的文件id
        filename = res.get('Remote file_id')
        # 只能返回str类型, filename为bytes类型(需要转换类型，不然会报错)
        return filename.decode()

    # 调用save()方法之前调用的方法
    def exists(self, name):
        '''Django判断文件名是否可用的方法，不可用返回True,可用返回False'''
        # 没有保存在本地（一定可用），所以返回False,
        return False

    # 模板文件中的goods.images.url会调用这个方法
    def url(self,name):
        '''返回访问文件的url路径'''
        return self.base_url+name

    # 海量存储 存储容量拓展 避免文件内容重复















