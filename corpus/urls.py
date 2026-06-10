from django.urls import path

from . import views

app_name = "corpus"

urlpatterns = [
    path("docs/", views.document_list, name="document_list"),
    path("docs/new/", views.document_create, name="document_create"),
    path("docs/<int:pk>/", views.document_detail, name="document_detail"),
    # 标注工作台
    path("docs/<int:doc_pk>/entries/new/", views.entry_create, name="entry_create"),
    path("entries/<uuid:pk>/edit/", views.entry_edit, name="entry_edit"),
    # 审核工作流
    path("review/", views.review_queue, name="review_queue"),
    path("entries/<uuid:pk>/review/", views.review_entry, name="review_entry"),
    # 导出
    path("export/", views.export_page, name="export_page"),
    path("export/download/", views.export_download, name="export_download"),
]
