from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import export as export_service
from .forms import DocumentForm, EntryForm, TaskForm
from .models import AIModel, Document, Entry, Language, ReviewLog, Task
from .notifications import notify


def is_reviewer(user):
    """谁能审核:管理员 / 主任专家(规格书 §8)。"""
    return user.is_authenticated and (
        user.is_superuser or user.role in ("admin", "lead")
    )


def can_export(user):
    """谁能导出:管理员 / 技术人员(规格书 §8)。"""
    return user.is_authenticated and (
        user.is_superuser or user.role in ("admin", "tech")
    )


def reviewer_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_reviewer(request.user):
            raise PermissionDenied("仅主任专家或管理员可执行审核操作。")
        return view(request, *args, **kwargs)
    return wrapper


def can_manage_tasks(user):
    """谁能分配任务:管理员 / 主任专家(规格书 §8)。"""
    return user.is_authenticated and (
        user.is_superuser or user.role in ("admin", "lead")
    )


def export_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_export(request.user):
            raise PermissionDenied("仅管理员或技术人员可触发导出。")
        return view(request, *args, **kwargs)
    return wrapper


def manage_tasks_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_manage_tasks(request.user):
            raise PermissionDenied("仅主任专家或管理员可分配任务。")
        return view(request, *args, **kwargs)
    return wrapper


@login_required
def dashboard(request):
    """仪表盘(规格书 5.8):全局数据量、审核进度、各模型产出、质量分布。"""

    def counts_by(model, field, choices):
        raw = dict(
            model.objects.values_list(field).annotate(c=Count("pk"))
        )
        return [
            {"value": v, "label": label, "count": raw.get(v, 0)}
            for v, label in choices
        ]

    doc_total = Document.objects.count()
    entry_total = Entry.objects.count()
    doc_status = counts_by(Document, "status", Document.Status.choices)
    entry_status = counts_by(Entry, "status", Entry.Status.choices)
    approved_total = next(
        (s["count"] for s in entry_status if s["value"] == Entry.Status.APPROVED), 0
    )

    # 各模型:已通过 / 总条目
    models = list(
        AIModel.objects.filter(is_active=True).annotate(
            approved_count=Count(
                "documents__entries",
                filter=Q(documents__entries__status=Entry.Status.APPROVED),
                distinct=True,
            ),
            entry_count=Count("documents__entries", distinct=True),
        )
    )

    # 质量分布(仅已通过且有评分)
    buckets = [
        ("优 ≥0.85", 0.85, 1.01),
        ("良 0.7–0.85", 0.70, 0.85),
        ("中 0.5–0.7", 0.50, 0.70),
        ("低 <0.5", -0.01, 0.50),
    ]
    quality = []
    scored = Entry.objects.filter(
        status=Entry.Status.APPROVED, quality_score__isnull=False
    )
    for label, lo, hi in buckets:
        quality.append({
            "label": label,
            "count": scored.filter(
                quality_score__gte=lo, quality_score__lt=hi
            ).count(),
        })
    unscored = Entry.objects.filter(
        status=Entry.Status.APPROVED, quality_score__isnull=True
    ).count()

    return render(request, "corpus/dashboard.html", {
        "doc_total": doc_total,
        "entry_total": entry_total,
        "approved_total": approved_total,
        "doc_status": doc_status,
        "entry_status": entry_status,
        "models": models,
        "quality": quality,
        "unscored": unscored,
        "max_model_count": max([m.entry_count for m in models], default=0),
    })


@login_required
def document_list(request):
    """资料列表,支持按状态 / 语言 / 目标模型筛选。"""
    docs = (
        Document.objects.select_related("created_by")
        .prefetch_related("target_models")
        .annotate(entry_count=Count("entries"))
    )

    status = request.GET.get("status", "")
    language = request.GET.get("language", "")
    model_id = request.GET.get("model", "")
    q = request.GET.get("q", "").strip()

    if status:
        docs = docs.filter(status=status)
    if language:
        docs = docs.filter(content_language=language)
    if model_id:
        docs = docs.filter(target_models__id=model_id)
    if q:
        docs = docs.filter(title__icontains=q)

    context = {
        "docs": docs,
        "status_choices": Document.Status.choices,
        "language_choices": Language.choices,
        "models": AIModel.objects.filter(is_active=True),
        "cur": {"status": status, "language": language, "model": model_id, "q": q},
    }
    return render(request, "corpus/document_list.html", context)


@login_required
def document_create(request):
    """新增资料(规格书 5.1)。两个按钮:存草稿 / 提交待标注。"""
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.created_by = request.user
            # "提交"则进入待标注,否则保留草稿
            doc.status = (
                Document.Status.PENDING_ANNOTATION
                if request.POST.get("action") == "submit"
                else Document.Status.DRAFT
            )
            doc.save()
            form.save_m2m()
            messages.success(request, f"已保存《{doc.title}》（{doc.get_status_display()}）")
            return redirect("corpus:document_detail", pk=doc.pk)
    else:
        form = DocumentForm()
    return render(request, "corpus/document_form.html", {"form": form})


@login_required
def document_detail(request, pk):
    """资料详情:基本信息 + 条目列表。"""
    doc = get_object_or_404(
        Document.objects.select_related("created_by", "translation_group")
        .prefetch_related("target_models", "entries"),
        pk=pk,
    )
    return render(
        request, "corpus/document_detail.html",
        {"doc": doc, "entries": doc.entries.all()},
    )


# ============ 标注工作台(规格书 5.4)============

def _suggested_tags(doc):
    """汇总该资料目标模型对应神学家的预设标签,供标注时一键添加。"""
    tags = []
    for model in doc.target_models.select_related("theologian"):
        if model.theologian:
            tags.extend(model.theologian.suggested_tags or [])
    # 去重保序
    seen, result = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _render_workbench(request, doc, entry, form):
    nxt = _next_to_annotate(doc, exclude_pk=entry.pk if entry else None)
    return render(
        request, "corpus/entry_form.html",
        {
            "doc": doc,
            "entry": entry,
            "form": form,
            "suggested_tags": _suggested_tags(doc),
            "entries": doc.entries.all(),
            "next_entry": nxt,
        },
    )


@login_required
def entry_create(request, doc_pk):
    """在某资料下新增一条标注。"""
    doc = get_object_or_404(Document, pk=doc_pk)
    if request.method == "POST":
        form = EntryForm(request.POST)
        if form.is_valid():
            return _save_entry(request, doc, form)
    else:
        form = EntryForm()
    return _render_workbench(request, doc, None, form)


@login_required
def entry_edit(request, pk):
    """编辑已有标注。"""
    entry = get_object_or_404(Entry.objects.select_related("document"), pk=pk)
    doc = entry.document
    if request.method == "POST":
        form = EntryForm(request.POST, instance=entry)
        if form.is_valid():
            return _save_entry(request, doc, form, entry=entry)
    else:
        form = EntryForm(instance=entry)
    return _render_workbench(request, doc, entry, form)


def _save_entry(request, doc, form, entry=None):
    """处理三个动作:存草稿 / 提交审核 / 跳过(跳过在模板里是普通链接,这里只处理前两者)。"""
    obj = form.save(commit=False)
    obj.document = doc
    obj.annotated_by = request.user
    if entry is None and not obj.order:
        # 新建条目:顺序号接在现有条目末尾
        obj.order = doc.entries.count()
    action = request.POST.get("action")
    obj.status = (
        Entry.Status.IN_REVIEW if action == "submit" else Entry.Status.ANNOTATED
    )
    obj.save()

    if action == "submit":
        messages.success(request, f"已提交审核:{obj.verse_ref}")
        nxt = _next_to_annotate(doc, exclude_pk=obj.pk)
        if nxt:
            return redirect("corpus:entry_edit", pk=nxt.pk)
        return redirect("corpus:document_detail", pk=doc.pk)
    messages.success(request, f"已存草稿:{obj.verse_ref}")
    return redirect("corpus:entry_edit", pk=obj.pk)


def _next_to_annotate(doc, exclude_pk=None):
    """找该资料下一条仍待标注的条目。"""
    qs = doc.entries.filter(status=Entry.Status.PENDING_ANNOTATION)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.order_by("order").first()


# ============ 审核工作流(规格书 5.5)============

@reviewer_required
def review_queue(request):
    """审核队列:列出所有「审核中」条目,按资料分组。支持批量通过本页。"""
    if request.method == "POST" and request.POST.get("action") == "batch_approve":
        ids = request.POST.getlist("entry_ids")
        entries = Entry.objects.filter(pk__in=ids, status=Entry.Status.IN_REVIEW)
        n = 0
        for e in entries:
            _approve(e, request.user)
            n += 1
        messages.success(request, f"已批量通过 {n} 条。")
        return redirect("corpus:review_queue")

    pending = (
        Entry.objects.filter(status=Entry.Status.IN_REVIEW)
        .select_related("document", "annotated_by")
        .order_by("document_id", "order")
    )
    # 按资料分组
    groups = {}
    for e in pending:
        groups.setdefault(e.document, []).append(e)
    groups = [
        {"doc": doc, "entries": entries} for doc, entries in groups.items()
    ]
    return render(
        request, "corpus/review_queue.html",
        {"groups": groups, "total": pending.count()},
    )


@reviewer_required
def review_entry(request, pk):
    """单条审核:可编辑后通过 / 保存修改(留审) / 打回(附批注)。"""
    entry = get_object_or_404(
        Entry.objects.select_related("document", "annotated_by"), pk=pk
    )
    doc = entry.document

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "reject":
            comment = request.POST.get("comment", "").strip()
            if not comment:
                messages.error(request, "打回必须填写批注,告知标注者修改方向。")
            else:
                entry.status = Entry.Status.PENDING_ANNOTATION
                entry.reviewed_by = request.user
                entry.save(update_fields=["status", "reviewed_by"])
                ReviewLog.objects.create(
                    entry=entry, reviewer=request.user,
                    action=ReviewLog.Action.REJECT, comment=comment,
                )
                # 通知标注者:你的条目被打回了
                notify(
                    entry.annotated_by,
                    verb=f"条目「{entry.verse_ref}」被打回",
                    actor=request.user,
                    message=comment,
                    url=f"/corpus/entries/{entry.pk}/edit/",
                )
                messages.success(request, f"已打回:{entry.verse_ref}(批注已记录,已通知标注者)")
                return redirect("corpus:review_queue")
            form = EntryForm(instance=entry)
        else:
            form = EntryForm(request.POST, instance=entry)
            if form.is_valid():
                obj = form.save(commit=False)
                changed = bool(form.changed_data)
                if action == "approve":
                    obj.save()
                    _approve(obj, request.user, edited=changed)
                    messages.success(request, f"已通过:{obj.verse_ref}")
                    nxt = (
                        Entry.objects.filter(status=Entry.Status.IN_REVIEW)
                        .exclude(pk=obj.pk).order_by("document_id", "order").first()
                    )
                    if nxt:
                        return redirect("corpus:review_entry", pk=nxt.pk)
                    return redirect("corpus:review_queue")
                else:  # save edits, keep in review
                    obj.reviewed_by = request.user
                    obj.save()
                    ReviewLog.objects.create(
                        entry=obj, reviewer=request.user,
                        action=ReviewLog.Action.EDIT,
                        comment=request.POST.get("comment", "").strip(),
                    )
                    messages.success(request, f"已保存修改(仍在审核):{obj.verse_ref}")
                    return redirect("corpus:review_entry", pk=obj.pk)
    else:
        form = EntryForm(instance=entry)

    return render(
        request, "corpus/review_entry.html",
        {
            "doc": doc, "entry": entry, "form": form,
            "reviews": entry.reviews.select_related("reviewer").all(),
        },
    )


def _approve(entry, user, edited=False):
    """通过一条:置为已通过,记录审核日志。"""
    entry.status = Entry.Status.APPROVED
    entry.reviewed_by = user
    entry.save(update_fields=["status", "reviewed_by"])
    ReviewLog.objects.create(
        entry=entry, reviewer=user,
        action=ReviewLog.Action.EDIT if edited else ReviewLog.Action.APPROVE,
        comment="审核时有修改" if edited else "",
    )


# ============ 导出(规格书 5.7 + §6)============

@export_required
def export_page(request):
    """导出页:选择目标模型,预览各模型可导出条目数。"""
    models = AIModel.objects.filter(is_active=True).annotate(
        approved_count=Count(
            "documents__entries",
            filter=Q(documents__entries__status=Entry.Status.APPROVED),
            distinct=True,
        )
    )
    total_approved = Entry.objects.filter(status=Entry.Status.APPROVED).count()
    return render(
        request, "corpus/export.html",
        {"models": models, "total_approved": total_approved},
    )


@export_required
def export_download(request):
    """流式下载 JSONL(规格书 §6 格式)。

    参数:model=<id>(留空=全部已通过)、include_disputed=on/off。
    """
    model_id = request.GET.get("model", "").strip()
    include_disputed = request.GET.get("include_disputed", "on") == "on"

    model = None
    if model_id:
        model = get_object_or_404(AIModel, pk=model_id)

    entries = export_service.approved_entries(
        model=model, include_disputed=include_disputed
    )

    filename = f"{model.code if model else 'all_approved'}.jsonl"
    response = StreamingHttpResponse(
        export_service.iter_jsonl(entries),
        content_type="application/x-ndjson; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ============ 任务分配(规格书 5.6)============

@login_required
def task_list(request):
    """任务页:专家看「我的任务」+「任务池」;管理者另见全部任务与创建入口。"""
    base = Task.objects.select_related("document", "assigned_to", "created_by")
    my_tasks = base.filter(assigned_to=request.user).exclude(status=Task.Status.DONE)
    pool = base.filter(
        is_claimable=True, assigned_to__isnull=True, status=Task.Status.OPEN
    )
    context = {
        "my_tasks": my_tasks,
        "pool": pool,
        "can_manage": can_manage_tasks(request.user),
    }
    if can_manage_tasks(request.user):
        context["all_tasks"] = base.all()[:100]
    return render(request, "corpus/task_list.html", context)


@manage_tasks_required
def task_create(request):
    """创建任务并(可选)指派给专家;指派则通知对方。"""
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if task.assigned_to:
                task.is_claimable = False
                task.status = Task.Status.CLAIMED
            else:
                task.is_claimable = True
                task.status = Task.Status.OPEN
            task.save()
            if task.assigned_to:
                notify(
                    task.assigned_to,
                    verb=f"你被指派了任务:{task.document.title}",
                    actor=request.user, message=task.note,
                    url="/corpus/tasks/",
                )
                messages.success(request, f"已指派给 {task.assigned_to}(已通知)。")
            else:
                messages.success(request, "已放入任务池,等待认领。")
            return redirect("corpus:task_list")
    else:
        form = TaskForm(initial={"document": request.GET.get("document")})
    return render(request, "corpus/task_form.html", {"form": form})


@login_required
def task_claim(request, pk):
    """从任务池认领一个任务。"""
    task = get_object_or_404(Task, pk=pk)
    if task.assigned_to is not None or task.status != Task.Status.OPEN:
        messages.error(request, "该任务已被认领或已关闭。")
    else:
        task.assigned_to = request.user
        task.status = Task.Status.CLAIMED
        task.save(update_fields=["assigned_to", "status"])
        notify(
            task.created_by,
            verb=f"{request.user} 认领了任务:{task.document.title}",
            actor=request.user, url="/corpus/tasks/",
        )
        messages.success(request, f"已认领:{task.document.title}")
    return redirect("corpus:task_list")


@login_required
def task_done(request, pk):
    """标记任务完成(指派对象本人或管理者)。"""
    task = get_object_or_404(Task, pk=pk)
    if request.user != task.assigned_to and not can_manage_tasks(request.user):
        raise PermissionDenied("只有任务负责人或管理者可标记完成。")
    task.status = Task.Status.DONE
    task.save(update_fields=["status"])
    messages.success(request, "任务已标记完成。")
    return redirect("corpus:task_list")


# ============ 站内通知 ============

@login_required
def notification_list(request):
    notes = request.user.notifications.select_related("actor").all()[:100]
    return render(request, "corpus/notifications.html", {"notes": notes})


@login_required
def notification_open(request, pk):
    """标记单条通知已读并跳转到其关联页面。"""
    note = get_object_or_404(request.user.notifications, pk=pk)
    note.is_read = True
    note.save(update_fields=["is_read"])
    return redirect(note.url or "corpus:notification_list")


@login_required
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "已全部标记为已读。")
    return redirect("corpus:notification_list")
