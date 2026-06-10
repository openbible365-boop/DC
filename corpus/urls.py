from django.urls import path

from . import views

app_name = "corpus"

urlpatterns = [
    path("docs/", views.document_list, name="document_list"),
    path("docs/new/", views.document_create, name="document_create"),
    path("docs/<int:pk>/", views.document_detail, name="document_detail"),
    path("docs/<int:pk>/autosplit/", views.document_autosplit, name="document_autosplit"),
    # 标注工作台
    path("docs/<int:doc_pk>/entries/new/", views.entry_create, name="entry_create"),
    path("entries/<uuid:pk>/edit/", views.entry_edit, name="entry_edit"),
    # 审核工作流
    path("review/", views.review_queue, name="review_queue"),
    path("entries/<uuid:pk>/review/", views.review_entry, name="review_entry"),
    # 导出
    path("export/", views.export_page, name="export_page"),
    path("export/download/", views.export_download, name="export_download"),
    # 任务分配
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/claim/", views.task_claim, name="task_claim"),
    path("tasks/<int:pk>/done/", views.task_done, name="task_done"),
    # 站内通知
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
    path("notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
]
