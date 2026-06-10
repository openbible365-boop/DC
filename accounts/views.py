from django.contrib.auth.views import LoginView

# 首页已由 corpus.views.dashboard 接管(规格书 5.8 仪表盘)。


class StyledLoginView(LoginView):
    """自定义登录视图:沿用分栏品牌登录页,并支持「记住我」。"""

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        # 勾选「记住我」则保持 14 天,否则关闭浏览器即失效
        if self.request.POST.get("remember"):
            self.request.session.set_expiry(60 * 60 * 24 * 14)
        else:
            self.request.session.set_expiry(0)
        return super().form_valid(form)
