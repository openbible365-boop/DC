"""语料域核心模型(规格书第 4 节)。

设计要点:
- 一份原始资料只存一份(Document),通过 target_models 多对多决定归属(原则 3.1)。
- Entry 是导出的最小单位,使用 UUID 主键(对应导出格式 §6 的 "id": "uuid")。
- 状态机贯穿 Document 与 Entry(原则 3.3)。
"""
import uuid

from django.conf import settings
from django.db import models


# ============ 语言与公共选项 ============

class Language(models.TextChoices):
    ZH = "zh", "中文"
    KO = "ko", "韩文"
    EN = "en", "英文"
    EL = "el", "希腊文"
    HE = "he", "希伯来文"


# ============ 模型定义(管理员维护)============

class Theologian(models.Model):
    """神学家 / 传统,由管理员统一维护,避免重复命名。"""

    name = models.CharField("名称", max_length=100)              # "约翰·加尔文"
    name_en = models.CharField("英文名", max_length=100, blank=True)
    tradition = models.CharField("神学传统", max_length=50)       # "改革宗"
    suggested_tags = models.JSONField("预设标签", default=list, blank=True)
    description = models.TextField("简介", blank=True)

    class Meta:
        verbose_name = "神学家/传统"
        verbose_name_plural = "神学家/传统"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AIModel(models.Model):
    """一个待训练的 AI 模型定义(语言维度 × 神学家维度,原则 3.2)。"""

    name = models.CharField("模型名", max_length=100)            # "加尔文·中文"
    code = models.SlugField(
        "代号", max_length=50, unique=True,
        help_text='导出时使用的稳定标识,如 "zh_calvin"',
    )
    language = models.CharField("语言", max_length=10, choices=Language.choices)
    theologian = models.ForeignKey(
        Theologian, verbose_name="神学家", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="models",
    )
    description = models.TextField("说明", blank=True)
    is_active = models.BooleanField("启用中", default=True)

    class Meta:
        verbose_name = "AI 模型"
        verbose_name_plural = "AI 模型"
        ordering = ["language", "name"]

    def __str__(self):
        return f"{self.name}（{self.code}）"


# ============ 资料与标注 ============

class TranslationGroup(models.Model):
    """把同源的多语版本绑在一起,便于跨语言对齐训练。"""

    source_title = models.CharField("源标题", max_length=200)
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "翻译组"
        verbose_name_plural = "翻译组"

    def __str__(self):
        return self.source_title


class Document(models.Model):
    """一份原始资料(注释书、讲道、文章等)。"""

    class SourceType(models.TextChoices):
        SERMON_AUDIO = "sermon_audio", "讲道音频"
        SERMON_VIDEO = "sermon_video", "讲道视频"
        SERMON_TEXT = "sermon_text", "讲稿文字"
        COMMENTARY = "commentary", "学术注释"
        BOOK = "book", "神学著作"
        URL = "url", "URL抓取"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING_ANNOTATION = "pending_annotation", "待标注"
        ANNOTATED = "annotated", "已标注"
        IN_REVIEW = "in_review", "审核中"
        APPROVED = "approved", "已通过"
        EXPORTED = "exported", "已导出"

    title = models.CharField("标题", max_length=300)
    source_type = models.CharField("来源类型", max_length=20, choices=SourceType.choices)
    content_language = models.CharField("资料语言", max_length=10, choices=Language.choices)
    author = models.CharField("作者", max_length=100, blank=True)
    date = models.DateField("日期", null=True, blank=True)

    raw_file = models.FileField("原始文件", upload_to="uploads/%Y/%m/", null=True, blank=True)
    raw_text = models.TextField("全文", blank=True, help_text="提取/转录后的全文")
    transcript_meta = models.JSONField("转录元数据", default=dict, blank=True)

    target_models = models.ManyToManyField(
        AIModel, verbose_name="目标模型", blank=True, related_name="documents",
    )
    translation_group = models.ForeignKey(
        TranslationGroup, verbose_name="翻译组", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="documents",
    )
    tradition = models.CharField("神学传统", max_length=50, blank=True)

    status = models.CharField(
        "状态", max_length=20, choices=Status.choices, default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="创建者", on_delete=models.SET_NULL,
        null=True, related_name="created_docs",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "资料"
        verbose_name_plural = "资料"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Entry(models.Model):
    """一条标准化的「经文 → 注释」数据,是导出的最小单位。"""

    class Status(models.TextChoices):
        PENDING_ANNOTATION = "pending_annotation", "待标注"
        ANNOTATED = "annotated", "已标注"
        IN_REVIEW = "in_review", "审核中"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已打回"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, verbose_name="所属资料", on_delete=models.CASCADE, related_name="entries",
    )

    verse_ref = models.CharField("经文引用", max_length=100)       # "约3:16"
    verse_text = models.TextField("经文", blank=True)
    commentary = models.TextField("注释")                         # 精炼注释(进 RAG)

    tags = models.JSONField("主题标签", default=list, blank=True)   # ["救恩","神的爱"]
    quality_score = models.FloatField("质量评分", null=True, blank=True)  # 0~1
    disputed = models.BooleanField("争议内容", default=False)

    # 自动拆分相关
    auto_generated = models.BooleanField("AI自动生成", default=False)
    ai_confidence = models.FloatField("AI置信度", null=True, blank=True)
    needs_attention = models.BooleanField("需重点检查", default=False)

    status = models.CharField(
        "状态", max_length=20, choices=Status.choices, default=Status.PENDING_ANNOTATION,
    )
    annotated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="标注者", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="annotated_entries",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="审核者", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_entries",
    )
    order = models.IntegerField("文档内顺序", default=0)

    class Meta:
        verbose_name = "条目"
        verbose_name_plural = "条目"
        ordering = ["document", "order"]

    def __str__(self):
        return f"{self.verse_ref}（{self.document.title}）"


# ============ 任务与审核 ============

class Task(models.Model):
    """任务分配:指派或认领。"""

    class Status(models.TextChoices):
        OPEN = "open", "待处理"
        CLAIMED = "claimed", "已认领"
        DONE = "done", "已完成"

    document = models.ForeignKey(Document, verbose_name="资料", on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="指派给", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="创建者", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_tasks",
    )
    is_claimable = models.BooleanField("可认领", default=True)      # True=任务池可认领
    note = models.TextField("说明", blank=True)
    status = models.CharField(
        "状态", max_length=20, choices=Status.choices, default=Status.OPEN,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "任务"
        verbose_name_plural = "任务"
        ordering = ["-created_at"]

    def __str__(self):
        return f"任务#{self.pk} · {self.document.title}"


class ReviewLog(models.Model):
    """审核记录:通过 / 修改 / 打回。"""

    class Action(models.TextChoices):
        APPROVE = "approve", "通过"
        EDIT = "edit", "修改"
        REJECT = "reject", "打回"

    entry = models.ForeignKey(
        Entry, verbose_name="条目", on_delete=models.CASCADE, related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="审核者", on_delete=models.SET_NULL, null=True,
    )
    action = models.CharField("动作", max_length=20, choices=Action.choices)
    comment = models.TextField("批注", blank=True)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = "审核记录"
        verbose_name_plural = "审核记录"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} · {self.entry.verse_ref}"


# ============ 站内通知 ============

class Notification(models.Model):
    """站内通知:任务指派、条目打回等事件提醒接收者。"""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="接收者",
        on_delete=models.CASCADE, related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="触发者", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    verb = models.CharField("事件", max_length=200)        # "指派了任务" / "打回了条目"
    message = models.TextField("内容", blank=True)
    url = models.CharField("跳转链接", max_length=300, blank=True)
    is_read = models.BooleanField("已读", default=False)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ["-created_at"]

    def __str__(self):
        return f"→{self.recipient}: {self.verb}"
