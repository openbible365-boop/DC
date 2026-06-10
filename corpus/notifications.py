"""站内通知工具。"""
from .models import Notification


def notify(recipient, verb, *, actor=None, message="", url=""):
    """给某用户创建一条通知。recipient 为空或等于 actor 时跳过(不给自己发)。"""
    if recipient is None or recipient == actor:
        return None
    return Notification.objects.create(
        recipient=recipient, actor=actor, verb=verb, message=message, url=url,
    )
