from django.contrib.auth.decorators import login_required
class LoginRequiredMixin(object):
    '''登录状态校验'''
    @classmethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view
        # print(LoginRequiredMixin.__mro__)
        # 这个as_view()是继续往后调用的View中的方法(参考多继承03)
        # view = super().as_view(**initkwargs)
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)
