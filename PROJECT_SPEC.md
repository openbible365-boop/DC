# 数据收集(Data Collection)协作平台 — 项目开发规格书

> 本文档供 Claude Code 使用，作为项目开发的总纲。
> 项目目标：建立一个供神学专家远程协作的资料收集、标注、审核、导出平台，
> 产出可用于训练「圣经解释 AI 语言模型」的高质量数据集。

---

## 1. 项目背景与愿景

团队心志：「敏捷地运用神的话语，为世人指一条明路，一条通达的道路。」

最终目标是训练出能够贴切解释圣经的 AI 语言模型。本平台是整个工程的**数据基础设施**——
所有训练数据都在这里被收集、标注、审核、导出。

**关键特性：**

- 支持**多语言**模型（起步：中文、韩文、英文，未来可扩展希腊文、希伯来文等）
- 支持**多模型**架构（同一语言可建多个模型，如分别针对不同神学家：加尔文、卫斯理、马太亨利等）
- 支持**文字 / 音频 / 视频**多种输入源（音视频自动转录为文字）
- 支持**注释书自动拆分**为标准 JSON 条目，再由专家审核
- 多位神学专家**远程协作**，按语言 / 传统 / 专长分配任务

---

## 2. 技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| 后端框架 | Django (Python) | AI 生态母语，便于日后接 Whisper、向量化、微调脚本 |
| 数据库 | PostgreSQL | 生产环境；开发可用 SQLite |
| 任务队列 | Celery + Redis | 处理音视频转录、注释书拆分等耗时任务 |
| 权限 | django-guardian | 条目级细粒度权限 |
| 前端交互 | HTMX + Alpine.js | 轻量、少写 JS，适合快速开发 |
| 管理后台 | Django Admin | 用户、模型定义、神学家列表等基础维护 |
| 语音转录 | OpenAI Whisper API（启动期）→ 本地 Whisper large-v3（成长期） | 中文识别质量好 |
| 音轨提取 | ffmpeg | 视频转音频 |
| 向量化 | sentence-transformers / OpenAI embeddings | 导出 RAG 知识库时使用 |
| 向量数据库 | Chroma（起步）/ Qdrant | RAG 知识库存储 |

**选用 Django 的核心理由**：项目核心资产是 AI 处理能力，Python 是该领域母语。
Whisper、RAG 框架、微调脚本全是 Python，避免跨语言调用。

---

## 3. 核心设计原则

### 3.1 资料只收一次，用标签决定归属

一份原始资料（如一本加尔文注释）**只存一份**，通过「目标模型」多对多标签
决定它训练哪些模型。同一篇讲道可同时属于「中文模型」和「卫斯理模型」。

### 3.2 模型矩阵 = 语言维度 × 神学家维度

```
                中文          韩文          英文
  加尔文      zh_calvin    ko_calvin    en_calvin
  卫斯理      zh_wesley    ko_wesley    en_wesley
  马太亨利    zh_henry     ko_henry     en_henry
  ...
```

### 3.3 数据生命周期（状态机）

```
草稿 → 待标注 → 已标注 → 审核中 → 已通过 → 已导出
                              ↓（打回）
                           待标注
```

### 3.4 自动化出初稿，专家做定稿

注释书自动拆分、音视频转录、AI 预填标签——都只产出**草稿**，
最终质量把关必须由神学专家完成。AI 高置信的条目可批量通过，
可疑条目系统主动标记，引导专家注意力。

---

## 4. 数据库模型设计

```python
# ============ 用户与角色 ============

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', '管理员'),
        ('lead', '主任专家'),
        ('expert', '协作专家'),
        ('tech', '技术人员'),
    ]
    role = CharField(max_length=20, choices=ROLE_CHOICES)
    languages = JSONField(default=list)   # 该专家能处理的语言 ["zh","en"]
    traditions = JSONField(default=list)  # 擅长的神学传统


# ============ 模型定义（管理员维护）============

class Theologian(Model):
    """神学家 / 传统，由管理员统一维护，避免重复命名"""
    name = CharField(max_length=100)            # "约翰·加尔文"
    name_en = CharField(max_length=100, blank=True)
    tradition = CharField(max_length=50)        # "改革宗"
    suggested_tags = JSONField(default=list)    # 预设关键词标签
    description = TextField(blank=True)


class AIModel(Model):
    """一个待训练的 AI 模型定义"""
    name = CharField(max_length=100)            # "加尔文·中文"
    language = CharField(max_length=10)         # "zh" / "ko" / "en"
    theologian = ForeignKey(Theologian, null=True, blank=True,
                            on_delete=SET_NULL)
    description = TextField(blank=True)
    is_active = BooleanField(default=True)


# ============ 资料与标注 ============

class TranslationGroup(Model):
    """把同源的多语版本绑在一起，便于跨语言对齐训练"""
    source_title = CharField(max_length=200)
    note = TextField(blank=True)


class Document(Model):
    """一份原始资料（注释书、讲道、文章等）"""
    SOURCE_TYPES = [
        ('sermon_audio', '讲道音频'),
        ('sermon_video', '讲道视频'),
        ('sermon_text', '讲稿文字'),
        ('commentary', '学术注释'),
        ('book', '神学著作'),
        ('url', 'URL抓取'),
    ]
    STATUS = [
        ('draft', '草稿'),
        ('pending_annotation', '待标注'),
        ('annotated', '已标注'),
        ('in_review', '审核中'),
        ('approved', '已通过'),
        ('exported', '已导出'),
    ]

    title = CharField(max_length=300)
    source_type = CharField(max_length=20, choices=SOURCE_TYPES)
    content_language = CharField(max_length=10)   # 原文语言
    author = CharField(max_length=100, blank=True)
    date = DateField(null=True, blank=True)

    raw_file = FileField(upload_to='uploads/', null=True, blank=True)
    raw_text = TextField(blank=True)              # 提取/转录后的全文
    transcript_meta = JSONField(default=dict)     # 音视频时间戳等

    target_models = ManyToManyField(AIModel)      # ★ 多对多归属
    translation_group = ForeignKey(TranslationGroup, null=True, blank=True,
                                   on_delete=SET_NULL)
    tradition = CharField(max_length=50, blank=True)

    status = CharField(max_length=20, choices=STATUS, default='draft')
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True,
                            related_name='created_docs')
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)


class Entry(Model):
    """一条标准化的「经文 → 注释」数据，是导出的最小单位"""
    document = ForeignKey(Document, on_delete=CASCADE, related_name='entries')

    verse_ref = CharField(max_length=100)         # "约3:16"
    verse_text = TextField(blank=True)            # 经文本身
    commentary = TextField()                      # 精炼注释（进 RAG）

    tags = JSONField(default=list)                # ["救恩","神的爱"]
    quality_score = FloatField(null=True, blank=True)  # 0~1 或 1~5
    disputed = BooleanField(default=False)        # 争议内容标记

    # 自动拆分相关
    auto_generated = BooleanField(default=False)  # 是否 AI 自动拆分产生
    ai_confidence = FloatField(null=True, blank=True)  # AI 置信度
    needs_attention = BooleanField(default=False)  # 系统标记需重点检查

    status = CharField(max_length=20, default='pending_annotation')
    annotated_by = ForeignKey(User, null=True, blank=True,
                              on_delete=SET_NULL, related_name='annotated')
    reviewed_by = ForeignKey(User, null=True, blank=True,
                             on_delete=SET_NULL, related_name='reviewed')
    order = IntegerField(default=0)               # 在文档内的顺序


# ============ 任务与审核 ============

class Task(Model):
    """任务分配：指派或认领"""
    document = ForeignKey(Document, on_delete=CASCADE)
    assigned_to = ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    is_claimable = BooleanField(default=True)     # True=任务池可认领
    status = CharField(max_length=20, default='open')
    created_at = DateTimeField(auto_now_add=True)


class ReviewLog(Model):
    """审核记录：通过 / 修改 / 打回"""
    entry = ForeignKey(Entry, on_delete=CASCADE, related_name='reviews')
    reviewer = ForeignKey(User, on_delete=SET_NULL, null=True)
    action = CharField(max_length=20)   # 'approve' / 'edit' / 'reject'
    comment = TextField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

---

## 5. 功能模块清单

### 5.1 资料收集
- 上传 PDF / DOCX / MP3 / MP4 / WAV / M4A，或粘贴文字、填 URL
- 表单字段：标题、来源类型、**资料语言**、作者、日期、主题经文、
  **目标模型（多选，按语言 + 按神学家）**、关联翻译版本、神学传统
- 草稿自动保存

### 5.2 音视频转录（Celery 异步）
- 视频 → ffmpeg 提取音轨 → Whisper 转文字
- 转录结果带时间戳，存入 `Document.raw_text` 与 `transcript_meta`
- 完成后通知专家

### 5.3 注释书自动拆分（Celery 异步）
- 文本提取（扫描版可选 OCR）
- 经文锚点识别（正则 + 书卷名对照表 + AI 辅助）
- 按锚点切段，生成多条 `Entry` 草稿（`auto_generated=True`）
- AI 预填 `tags`、`tradition`、`quality_score`，标注置信度
- 跨多节或可疑段落标记 `needs_attention=True`

### 5.4 标注工作台
- 左侧原文（音频可同步播放校对），右侧标注表单
- 经文对应、主题标签、神学传统、精炼注释、质量评分、争议标记
- 多语言：可显示原文 + 译文对照
- 操作：存草稿 / 提交审核 / 跳过

### 5.5 审核工作流
- 审核队列按文档分组
- 每条显示 AI 置信度（高置信=绿色，可疑=橙色警示）
- 单条操作：通过 / 编辑 / 删除
- 切分修正：**拆分此条** / **与上条合并**（自动拆分场景高频）
- 批量通过本页
- 打回时附批注，通知提交者

### 5.6 任务分配
- 管理员指派，或专家从任务池认领
- 按语言、神学传统、主题匹配合适专家
- 进度追踪

### 5.7 导出
- 按 `target_models` 筛选，得到某模型专用训练集
- 格式：JSONL（RAG 知识库 / 微调用）
- Celery 异步处理大批量导出，完成后提供下载

### 5.8 仪表盘
- 各模型数据量、审核进度、质量分布

---

## 6. 标准数据格式（导出）

每条 `Entry` 导出为一行 JSON：

```json
{
  "id": "uuid",
  "verse_ref": "约3:16",
  "verse_text": "神爱世人，甚至将他的独生子赐给他们……",
  "commentary": "本段从原文κόσμος阐明神爱的普世性，强调信心是得救唯一条件……",
  "source": "马太亨利注释·约翰福音卷",
  "content_language": "zh",
  "tradition": "改革宗",
  "tags": ["救恩", "神的爱", "信心"],
  "quality_score": 0.9,
  "disputed": false,
  "target_models": ["zh_henry", "zh_general"],
  "translation_group": "jn3-16-henry"
}
```

---

## 7. 经文引用识别要点

中文经文引用有多种写法，需先建**书卷名对照表**统一映射：

- "约翰福音3:16" / "约3:16" / "约 3:16" / "翰3:16" → 标准化为 `JHN 3:16`
- 处理范围引用："约3:16-18"、"约3:16,18"
- 建议参考标准化编号体系（如 OSIS 或自定义）

正则先粗筛，AI 辅助处理不规则情况。

---

## 8. 角色权限矩阵

| 功能 | 管理员 | 主任专家 | 协作专家 | 技术员 |
|------|:---:|:---:|:---:|:---:|
| 邀请成员、分配任务 | ✓ | | | |
| 维护神学家 / 模型定义 | ✓ | ✓ | | |
| 上传资料 | ✓ | ✓ | ✓ | ✓ |
| 标注（自己的任务） | | ✓ | ✓ | |
| 审核、最终通过 | | ✓ | | |
| 触发导出 | ✓ | | | ✓ |

- 神学家列表只由管理员 / 主任维护，避免重复命名混乱
- 协作专家只能看自己认领或被指派的条目

---

## 9. 建议的开发顺序

| 阶段 | 内容 | 产出 |
|------|------|------|
| 第 1 周 | 用户系统 + 角色权限 + `Document` / `Entry` 基础 CRUD | 能登录、上传文字、看列表 |
| 第 2 周 | 标注工作台 + 状态流转 | 专家可开始真实标注 |
| 第 3 周 | 任务分配 + 审核队列（含打回） | 协作闭环 |
| 第 4 周 | 导出功能（JSONL，按 target_models 筛选） | 产出第一批训练集 |
| 第 5 周 | 注释书自动拆分（Celery + 经文识别 + 拆分审核页） | 批量提效 |
| 第 6 周 | 音视频转录（Whisper） | 多源输入完整 |

**原则**：不必一次做完。文字资料先跑起来，让神学专家第 2 周就能参与、
边用边反馈。音视频与自动拆分作为增量功能后续加入。

---

## 10. 给 Claude Code 的起步指令建议

建立项目时，可按此顺序请 Claude Code 执行：

1. `初始化 Django 项目，配置 PostgreSQL、Celery + Redis、django-guardian`
2. `按第 4 节的数据库模型创建 app 与 models，生成 migration`
3. `创建用户角色系统与登录，配置 Django Admin 维护 Theologian / AIModel`
4. `实现资料收集表单（第 5.1 节字段），含 target_models 多选`
5. `实现标注工作台（第 5.4 节布局）`
6. `实现审核队列与状态流转（第 5.5 节）`
7. `实现 JSONL 导出（第 6 节格式）`
8. `实现注释书自动拆分 Celery 任务（第 5.3 + 第 7 节）`
9. `集成 Whisper 音视频转录（第 5.2 节）`

---

*文档结束。这是一份活文档，开发过程中可随团队反馈持续修订。*
