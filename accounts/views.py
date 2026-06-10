from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import RegistrationForm

User = get_user_model()

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


def register(request):
    """自助注册:创建待核准账号,并通知管理员审核。"""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            _notify_admins_new_registration(user)
            messages.success(
                request,
                f"注册成功!账号「{user.username}」需管理员核准后方可登录,"
                "请耐心等待,核准后即可用此用户名与密码登录。",
            )
            return redirect("login")
    else:
        form = RegistrationForm()
    return render(request, "registration/register.html", {"form": form})


def _notify_admins_new_registration(user):
    """给所有管理员/主任专家发一条「新用户待核准」通知。"""
    from corpus.notifications import notify

    admins = User.objects.filter(is_active=True).filter(
        Q(role__in=["admin", "lead"]) | Q(is_superuser=True)
    ).distinct()
    for admin in admins:
        notify(
            admin,
            verb=f"新用户「{user.username}」申请注册,待核准",
            message="到「用户管理」激活该账号后,对方即可登录。",
            url="/admin/accounts/user/?is_active__exact=0",
        )
