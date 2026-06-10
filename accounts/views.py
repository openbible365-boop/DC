from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    """登录后的首页占位。后续阶段会替换为仪表盘(规格书 5.8)。"""
    return render(request, "home.html")
