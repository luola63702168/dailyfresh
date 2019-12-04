from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client, get_tracker_conf
from django.conf import settings


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

    def _open(self, name, mode='rb'):
        '''打开文件使用(该项目不需要打开文件)'''
        pass

    def _save(self, name, content):
        '''保存文件时使用
        :param name: 你选择上传文件的名字
        :param content: 包含上传文件内容的File对象
        '''

        trackers = get_tracker_conf(self.client_conf)
        client = Fdfs_client(trackers)
        res = client.upload_by_buffer(content.read())

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
            raise Exception('上传文件失败')
        filename = res.get('Remote file_id')
        return filename.decode()

    def exists(self, name):
        '''文件名是否可用，可用False'''
        return False

    def url(self, name):
        '''返回访问文件的url路径'''
        return self.base_url + name
