0.富文本编辑器：安装包，settings配置两项，urls配置一项，模型类添加字段。

1.celery异步发送邮件。（使用的是163邮箱（本地））

2.celery异步生成静态页面，访问需要通过虚拟机（配置nginx，默认端口80（虚拟机））。
    ps：（1）异步的三个部分：任务的发出者，中间人，任务的处理者。可以在同一台电脑上启动，也可以不在同一台电脑上（如果在别的电脑上，那么是需要我们这个项目文件的也就是dailyfresh及task.py文件中的相关环境配置）。
        （2）celery -A celery_tasks.tasks worker -l info 启动celery服务

3.分布式存储图片。（需要改写django默认存储方式（本地），及配配置fdfs和nginx服务器，端口：8888（虚拟机））具体配置信息，参考百度或者说明文档（私qq:63763040）。

4.存储在redis上的数据：（（9号数据库）用户登录的session（ login(request, user)保存的），用户浏览记录（通过django_redis，得到对象，设置kv），主页面的缓存（通过seetings配置缓存存储位置））（（8号数据库）redis作为异步的中间者（形成任务队列，从而发邮件或生成静态页面））
    ps:（1）当后台数据修改的时候，静态页面也是需要修改的（通过admin中的api修改了），同时缓存也是需要清除的（这样下次访问的时候便会重新查询数据库中的内容了），
            当然，稳妥起见，我们最好设置缓存的过期时间，这样代码中如果静态页面更新没有清除缓存，在一定时间后，缓存数据还是会自动更新的，出错的也仅仅是这个过期时间内的问题了。
       （2）页面为什么要缓存？因为静态页面和原本的首页不是同一个地址，如果访问首页的话，那么会反复查询多余的数据，所以要有缓存（其实缓存的就是需要返回给模板文件的那个字典）
       （3）通过django_redis的（con = get_redis_connection('default')）连接至redis时，其实返回的便是常规的StrictRedis对象。
    另外：django_redis的版本和django的版本是一种松耦合的关系，需要版本呼应。

5.搜索框三大构成：用户，全文检索框架（不想学搜索引擎的使用，那么就可以借助它去使用搜索引擎），搜索引擎。
    1.本项目选用whoosh搜索引擎（纯python编写，性能稍差，但是够用，无二进制包，程序不会莫名奔溃）及haystack全文检索框架。
    2.haystack的使用：首先在settings中配置相关配置项（相对固定），然后在app文件下建立一个search_indexes文件（固定），文件内容（相对固定），再在templates文件夹下建立一个冗长的目录（相对固定）。
        （1）冗长的目录：这个文件要建在templates下面（search/indexes/(索引对应的类所在的项目文件名)/（模型类名小写）_test.txt
        （2）python manage.py rebuild_index 配置好之后 这个命令来生成对应的索引文件
        （3）设置表单提交（相对固定），及url配置（固定）,在search目录下建一个search.html文件
        （4） 根据返回了的3个模板变量，操作模板文件search.html
    3.中文分词调优（使用jieba分词进行中文分词处理）
        （1）需要下载一个包（jieba），需要在E:\py3\py_virtual\Django_01_env\Lib\site-packages\haystack\backends 新建一个及修改一个文件（更改词语分析类），并重新配置settings
        （2）重新生成索引文件
6.支付宝接口接入（https://github.com/fzlee/alipay/blob/master/README.zh-hans.md）
    1，pip install python-alipay-sdk --upgrade 安装这个包(sdk)
    2，genrsa -out app_private_key.pem   2048  # 私钥（需要在管理员环境下）
       rsa -in app_private_key.pem -pubout -out app_public_key.pem # 导出公钥
    3.沙箱环境配置私钥和公钥
    4.order目录下新建两个pem文件（支付宝的公钥用于解密，自己的私钥用于发送请求）
    5,在view中初始化并访问支付接口，完成支付。
    6,返回结果需要访问支付宝的订单查询接口，通过ajax返回处理结果
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
7.项目部署(nginx（调度）-uwsgiAndDjano-nginx（fdfs及静态页面）) 实现静动态请求转发，负载均衡
- pip install uwsgi
- 修改settings中debug配置
- 新建配置文件uwsgi.ini并填入相关信息
- 启动:uwsgi --ini 配置文件路径 例如:uwsgi --ini uwsgi.ini
- 停止:uwsgi --stop uwsgi.pid路径 例如:uwsgi --stop uwsgi.pid
- 配置nginx 动态请求传给uwsgi，uwsgi传给后台并处理，静态请求（配置location，通过url确定是否为静态请求）nginx处理并直接返回。
    - 更改uwsgi.ini配置文件（socket=127.0.0.1:8080）
    - 更改nginx配置文件nginx.conf
        注意：
        - 静态文件的收集(修改目录权限777，并生成静态文件 python manage.py collectstatic)
        - 重启nginx
    - 配置静态页面及fdfs存储的图片nginx服务器与调度服务器的连接(配置调度ngnix的配置文件)
    - 重启nginx
- 实现负载均衡
    - 赋值并配置uwsgi.ini文件
    - 启动多个wsgi： uwsgi --ini uwsgi2.ini
    - 继续配置nginx.conf，使之合理分配请求
    - 重启nginx服务器
----------------------------------------------------
虚拟环境中的关键版本(需要呼应)：Django==1.11  django-redis==4.10.0

