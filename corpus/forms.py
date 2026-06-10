from django import forms
from django.contrib.auth import get_user_model

from .models import AIModel, Document, Entry, Task, TranslationGroup

User = get_user_model()


def _parse_tags(text):
    """把用户输入的标签文本(中英文逗号/顿号分隔)解析为去重列表。"""
    if not text:
        return []
    for sep in ("，", "、", "\n"):
        text = text.replace(sep, ",")
    seen, result = set(), []
    for t in (s.strip() for s in text.split(",")):
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


class DocumentForm(forms.ModelForm):
    """资料收集表单(规格书 5.1)。

    created_by / status 由视图设置,不在表单内暴露。
    target_models 用多选,按语言+神学家挑选目标模型。
    """

    class Meta:
        model = Document
        fields = [
            "title",
            "source_type",
            "content_language",
            "author",
            "date",
            "raw_file",
            "raw_text",
            "target_models",
            "translation_group",
            "tradition",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "raw_text": forms.Textarea(attrs={"rows": 12, "placeholder": "粘贴讲稿/文章全文,或上传文件后留空待提取"}),
            "target_models": forms.SelectMultiple(attrs={"size": 8}),
            "title": forms.TextInput(attrs={"placeholder": "如:马太亨利注释·约翰福音卷"}),
            "author": forms.TextInput(attrs={"placeholder": "如:马太·亨利"}),
            "tradition": forms.TextInput(attrs={"placeholder": "如:改革宗"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 只在已启用的目标模型中选择,并按语言排序便于浏览
        self.fields["target_models"].queryset = (
            AIModel.objects.filter(is_active=True).select_related("theologian")
        )
        self.fields["translation_group"].queryset = TranslationGroup.objects.all()
        self.fields["translation_group"].required = False
        self.fields["target_models"].required = False
        # 给所有字段加统一 class,方便样式
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " field-input").strip()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("raw_text") and not cleaned.get("raw_file"):
            raise forms.ValidationError("请至少提供资料正文(粘贴全文)或上传一个文件。")
        return cleaned


class EntryForm(forms.ModelForm):
    """标注表单(规格书 5.4)。

    tags 在模型里是 JSON 列表,这里用逗号分隔的文本框收集,保存时解析回列表。
    """

    tags_text = forms.CharField(
        label="主题标签", required=False,
        widget=forms.TextInput(attrs={"placeholder": "用逗号分隔,如:救恩, 神的爱, 信心"}),
        help_text="多个标签用逗号分隔",
    )

    class Meta:
        model = Entry
        fields = ["verse_ref", "verse_text", "commentary", "quality_score", "disputed"]
        widgets = {
            "verse_ref": forms.TextInput(attrs={"placeholder": "如:约3:16"}),
            "verse_text": forms.Textarea(attrs={"rows": 3, "placeholder": "经文原文(可选)"}),
            "commentary": forms.Textarea(attrs={"rows": 10, "placeholder": "精炼后的注释,将进入 RAG 知识库"}),
            "quality_score": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "1", "placeholder": "0 ~ 1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["tags_text"].initial = ", ".join(self.instance.tags or [])

    def clean_quality_score(self):
        score = self.cleaned_data.get("quality_score")
        if score is not None and not (0 <= score <= 1):
            raise forms.ValidationError("质量评分需在 0 到 1 之间。")
        return score

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.tags = _parse_tags(self.cleaned_data.get("tags_text", ""))
        if commit:
            obj.save()
        return obj


class TaskForm(forms.ModelForm):
    """创建任务(规格书 5.6)。

    指派给某专家;留空则进入可认领任务池(is_claimable=True)。
    """

    class Meta:
        model = Task
        fields = ["document", "assigned_to", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 2, "placeholder": "任务说明(可选),如:请优先处理前三章"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, role__in=["expert", "lead"]
        ).order_by("username")
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].label = "指派给(留空=放入任务池)"
        self.fields["document"].queryset = Document.objects.order_by("-created_at")
