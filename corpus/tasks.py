"""Celery 异步任务。"""
from celery import shared_task

from .models import Document, Entry
from .notifications import notify
from .splitter import split_text


@shared_task
def auto_split_document(document_id, user_id=None):
    """对一份资料的正文做自动拆分,生成 Entry 草稿(规格书 5.3)。

    只产出草稿(auto_generated=True),最终由专家审核(原则 3.4)。
    """
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return {"ok": False, "error": "资料不存在"}

    segments = split_text(doc.raw_text)

    # 顺序号接在现有条目之后
    base_order = doc.entries.count()
    created = 0
    flagged = 0
    new_entries = []
    for i, seg in enumerate(segments):
        new_entries.append(Entry(
            document=doc,
            verse_ref=seg["verse_ref"],
            commentary=seg["commentary"],
            order=base_order + i,
            auto_generated=True,
            needs_attention=seg["needs_attention"],
            status=Entry.Status.PENDING_ANNOTATION,
        ))
        created += 1
        if seg["needs_attention"]:
            flagged += 1

    Entry.objects.bulk_create(new_entries)

    # 有产出则把资料推进到「待标注」
    if created and doc.status == Document.Status.DRAFT:
        doc.status = Document.Status.PENDING_ANNOTATION
        doc.save(update_fields=["status"])

    # 通知触发者
    if user_id:
        from accounts.models import User
        user = User.objects.filter(pk=user_id).first()
        if created:
            msg = f"《{doc.title}》自动拆分完成:生成 {created} 条草稿"
            if flagged:
                msg += f",其中 {flagged} 条已标记需重点检查"
        else:
            msg = f"《{doc.title}》未识别到经文引用,未生成条目"
        notify(
            user, verb="自动拆分完成", actor=None,
            message=msg, url=f"/corpus/docs/{doc.pk}/",
        )

    return {"ok": True, "created": created, "flagged": flagged}
