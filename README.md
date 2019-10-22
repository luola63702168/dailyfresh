# Django B2C天天生鲜项目
 ## 模块
 - 用户模块：注册、登录、celery异步发送邮件激活。
 - 商品模块 ：mysql；haystack+whoosh实现对商品的检索；Nginx+fastdfs图片分布式存储。
 - 订单模块：悲观锁及乐观锁处理并发；支付宝接口使用
 - 购物车模块:redis数据库进行存储
## 项目组成
- 富文本编辑器用于后台编辑。
- celery异步发送邮件。（使用的是163邮箱（本地））
- celery异步生成静态页面，访问需要通过虚拟机（配置nginx，默认端口80（虚拟机））。
        celery -A celery_tasks.tasks worker -l info 启动celery服务
- 分布式存储图片。（改写django默认存储方式（本地），配置fdfs和nginx服务器，端口：8888）
    具体配置信息（私qq:63763040）。
- 存储在redis上的数据：
    9号数据库：用户登录的session；用户浏览记录；购物车记录；主页面的缓存。
    8号数据库：redis作为异步的中间者，形成任务队列，从而发邮件或生成静态页面。
    ps:django_redis的版本和django的版本是一种松耦合的关系，需要版本呼应。
- 搜索框：
    1.whoosh搜索引擎及haystack全文检索框架，使用jieba分词进行中文分词处理。
- 支付
支付宝接口接入
- 项目部署(nginx（调度）-uwsgi+Djano-nginx（fdfs及静态页面）) 
实现静动态请求转发，负载均衡。
## 补充
虚拟环境中的关键版本(需要呼应)：Django==1.11  django-redis==4.10.0