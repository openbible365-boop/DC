"""config 项目的 URL 路由总表。"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as media_serve

from accounts import views as account_views
from accounts.views import StyledLoginView
from corpus import views as corpus_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # 自定义登录页(分栏品牌设计 + 记住我),需在 auth.urls 之前以覆盖默认 login
    path("accounts/login/", StyledLoginView.as_view(), name="login"),
    path("accounts/register/", account_views.register, name="register"),
    # 内置认证视图:登出/改密等,模板放在 templates/registration/
    path("accounts/", include("django.contrib.auth.urls")),
    path("corpus/", include("corpus.urls")),
    path("", corpus_views.dashboard, name="home"),
]

# 用户上传的媒体文件由 Django 服务(生产环境位于 Caddy 反代之后)。
# 静态文件由 WhiteNoise 处理,无需单独路由。
urlpatterns += [
    re_path(
        r"^%s(?P<path>.*)$" % settings.MEDIA_URL.lstrip("/"),
        media_serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
