"""注释书自动拆分引擎(规格书 5.3 + §7)。

策略:用「书卷名 + 章:节」正则在全文中找经文锚点,按锚点把全文切段,
每段 = 一条 Entry 草稿(verse_ref + 该处注释)。正则先粗筛,
可疑段落标 needs_attention,引导专家重点检查。AI 辅助为可选增强(预留接口)。
"""
import re

from .bible_books import ALL_NAMES, NAME_INDEX

# 书卷名 alternation(长名优先)
_BOOK_RE = "|".join(re.escape(n) for n in ALL_NAMES)

# 经文引用:书卷 + 章 [:：] 节 [范围/列举]
#   约3:16 / 约 3：16 / 约翰福音3:16-18 / 罗8:28,30
_REF_RE = re.compile(
    r"(?P<book>" + _BOOK_RE + r")"
    r"\s*(?P<chapter>\d{1,3})"
    r"\s*[:：]\s*"
    r"(?P<verse>\d{1,3})"
    r"(?P<extra>\s*[-–~]\s*\d{1,3}|(?:\s*[,，]\s*\d{1,3})+)?"
)

# 段落长度阈值(字符),超出或过短则标记需检查
_MIN_LEN = 15
_MAX_LEN = 2000


def normalize_ref(m):
    """把一次匹配规整成统一的显示形式,如「约3:16」「罗8:28-30」。"""
    code, abbr = NAME_INDEX[m.group("book")]
    ref = f"{abbr}{m.group('chapter')}:{m.group('verse')}"
    extra = m.group("extra")
    if extra:
        extra = re.sub(r"\s+", "", extra).replace("，", ",").replace("–", "-").replace("~", "-")
        ref += extra
    return ref, code


def is_range(m):
    extra = m.group("extra") or ""
    return bool(extra.strip())


def split_text(text):
    """把整段注释文本拆为条目草稿列表。

    返回 [{verse_ref, osis, commentary, needs_attention, reason}]
    """
    if not text or not text.strip():
        return []

    anchors = list(_REF_RE.finditer(text))
    if not anchors:
        return []

    results = []
    for i, m in enumerate(anchors):
        start = m.end()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
        commentary = text[start:end].strip(" \t\r\n:：—-")

        ref, code = normalize_ref(m)

        needs_attention = False
        reasons = []
        if is_range(m):
            needs_attention = True
            reasons.append("跨多节引用")
        if len(commentary) < _MIN_LEN:
            needs_attention = True
            reasons.append("注释过短")
        if len(commentary) > _MAX_LEN:
            needs_attention = True
            reasons.append("注释过长(可能含多条)")

        results.append({
            "verse_ref": ref,
            "osis": code,
            "commentary": commentary,
            "needs_attention": needs_attention,
            "reason": "、".join(reasons),
        })
    return results
