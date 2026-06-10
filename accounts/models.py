from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """平台用户。在内置认证用户基础上增加角色与专长维度。

    role 决定权限(见规格书第 8 节角色权限矩阵);
    languages / traditions 用于任务分配时按专长匹配专家。
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"
        LEAD = "lead", "主任专家"
        EXPERT = "expert", "协作专家"
        TECH = "tech", "技术人员"

    role = models.CharField(
        "角色", max_length=20, choices=Role.choices, default=Role.EXPERT
    )
    languages = models.JSONField(
        "可处理语言", default=list, blank=True,
        help_text='该专家能处理的语言,如 ["zh", "en"]',
    )
    traditions = models.JSONField(
        "擅长神学传统", default=list, blank=True,
        help_text='擅长的神学传统,如 ["改革宗", "卫斯理宗"]',
    )

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.get_full_name() or self.username
