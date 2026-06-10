from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """在内置 UserAdmin 基础上加入角色与专长字段,并支持自助注册核准。"""

    list_display = (
        "username", "get_full_name", "email", "role", "is_active", "date_joined",
    )
    list_filter = BaseUserAdmin.list_filter + ("role",)
    ordering = ("-date_joined",)
    actions = ["approve_users"]

    # 在编辑页加入自定义字段分组
    fieldsets = BaseUserAdmin.fieldsets + (
        ("平台角色与专长", {"fields": ("role", "languages", "traditions")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("平台角色与专长", {"fields": ("role", "languages", "traditions")}),
    )

    @admin.action(description="✓ 核准(激活)选中的用户")
    def approve_users(self, request, queryset):
        updated = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"已核准 {updated} 个账号,对方现在可以登录了。")
