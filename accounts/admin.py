from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """在内置 UserAdmin 基础上加入角色与专长字段。"""

    list_display = ("username", "get_full_name", "role", "is_staff", "is_active")
    list_filter = BaseUserAdmin.list_filter + ("role",)

    # 在编辑页加入自定义字段分组
    fieldsets = BaseUserAdmin.fieldsets + (
        ("平台角色与专长", {"fields": ("role", "languages", "traditions")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("平台角色与专长", {"fields": ("role", "languages", "traditions")}),
    )
