"""导出:把「已通过」条目序列化为规格书 §6 的标准 JSON 格式。"""
import json

from .models import Entry


def entry_to_dict(entry):
    """单条 Entry → §6 标准字典。

    source / content_language / tradition / target_models / translation_group
    取自所属 Document(资料只存一份,归属由 Document.target_models 决定)。
    """
    doc = entry.document
    return {
        "id": str(entry.id),
        "verse_ref": entry.verse_ref,
        "verse_text": entry.verse_text,
        "commentary": entry.commentary,
        "source": doc.title,
        "content_language": doc.content_language,
        "tradition": doc.tradition,
        "tags": entry.tags or [],
        "quality_score": entry.quality_score,
        "disputed": entry.disputed,
        "target_models": list(
            doc.target_models.values_list("code", flat=True)
        ),
        "translation_group": (
            doc.translation_group.source_title if doc.translation_group else None
        ),
    }


def approved_entries(model=None, include_disputed=True):
    """取可导出的已通过条目。

    model: 指定 AIModel 则只取归属该模型的资料下的条目;None 表示不限。
    include_disputed: False 时排除标记为争议的条目。
    """
    qs = (
        Entry.objects.filter(status=Entry.Status.APPROVED)
        .select_related("document", "document__translation_group")
        .prefetch_related("document__target_models")
        .order_by("document_id", "order")
    )
    if model is not None:
        qs = qs.filter(document__target_models=model)
    if not include_disputed:
        qs = qs.exclude(disputed=True)
    return qs


def iter_jsonl(entries):
    """生成 JSONL 文本行(逐行 yield,便于流式响应)。"""
    for entry in entries:
        yield json.dumps(entry_to_dict(entry), ensure_ascii=False) + "\n"
