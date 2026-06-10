"""模板上下文处理器:让导航栏在所有页面都能显示未读通知。"""


def notifications(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    qs = user.notifications.filter(is_read=False)
    return {
        "unread_count": qs.count(),
        "recent_notifications": list(qs[:5]),
    }
