"""config 项目的 URL 路由总表。"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from corpus import views as corpus_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # 内置认证视图:登录/登出/改密等,模板放在 templates/registration/
    path("accounts/", include("django.contrib.auth.urls")),
    path("corpus/", include("corpus.urls")),
    path("", corpus_views.dashboard, name="home"),
]

# 开发环境下由 Django 直接服务用户上传的媒体文件
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
