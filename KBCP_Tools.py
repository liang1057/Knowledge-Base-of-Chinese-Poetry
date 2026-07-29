# -*- coding: utf-8 -*-
"""
KBCP_Tools.py - Agent 工具集（智能问答的"手脚"）
================================================
每个工具函数对应一种精确能力，返回【结构化 dict】供 LLM 阅读与综合，
而不是拼接给人看的字符串。这样既能让 LLM "理解"自然语言，
又保证数字/事实的精确性（工具内部复用 SQLiteDAL / RAGIndex）。

工具列表：
  - search_poem(line, author)            按诗句片段/标题查找诗词（找出处）
  - get_poem_full(line_or_title)         查找并返回诗词全文
  - get_author(name)                     查询诗人信息
  - count_poems(author)                  统计某诗人收录诗数
  - count_poems_by_tag(author, tag)      按主题标签精确计数（确定性 vocab 映射 + 可选 LLM 近义扩展）
  - compare_by_tag(authors, tag)         多位诗人按主题标签对比计数
  - semantic_search(query, top_k)        智能化 RAG 语义检索（向量 + 标签）

近义理解开关：
  near_synonym 参数由 Agent 中枢统一传入（来自 config 的 LLM_NEAR_SYNONYM）。
  True  = 调用 LLM 将主题词扩展为近义标签集合（召回更智能）
  False = 仅 vocab 确定性映射（如 月亮→月）
"""
import json
from typing import List, Dict, Optional

from KBCP_DAL import SQLiteDAL
from KBCP_LLM_Provider import load_config, get_llm_priority_list, create_provider


# ============================================================
#  模块级单例
# ============================================================

_dal = None


def _get_dal() -> SQLiteDAL:
    """复用 KBCP_DAL 单例（独立脚本环境直接连 SQLite 文件）"""
    global _dal
    if _dal is None:
        _dal = SQLiteDAL()
    return _dal


# ============================================================
#  内部辅助：作者解析
# ============================================================

def _resolve_author(name: str) -> Optional[object]:
    """
    解析作者：先按标准名精确匹配，失败则按别名/字号模糊匹配。
    返回 AuthorData 或 None。
    """
    dal = _get_dal()
    author = dal.get_author_by_name(name)
    if author:
        return author
    authors = dal.get_author_by_alias(name)
    if authors:
        return authors[0]
    return None


# ============================================================
#  内部辅助：主题标签解析（确定性 + 近义扩展）
# ============================================================

def _resolve_tag_label(tag: str) -> List[str]:
    """
    确定性标签映射：把用户主题词映射成 vocab 表中的标准 label。
    例：'月亮' → ['月']（'月' 是 '月亮' 的子串，被模糊匹配命中）
    例：'思乡' → ['思乡']（精确命中）
    不做任何 LLM 调用，保证可复现、快速。
    """
    dal = _get_dal()
    # 1) 精确匹配
    rows = dal._fetchall(
        "SELECT DISTINCT label FROM vocab WHERE label = ?", (tag,)
    )
    if rows:
        return [r['label'] for r in rows]

    # 2) 模糊匹配：tag 包含在 label 中，或 label 包含在 tag 中
    like = f'%{tag}%'
    rows = dal._fetchall(
        "SELECT DISTINCT label FROM vocab "
        "WHERE label LIKE ? OR ? LIKE '%'||label||'%'",
        (like, tag)
    )
    if rows:
        return [r['label'] for r in rows]
    return []


def _all_vocab_labels() -> List[str]:
    """取 vocab 表中所有去重后的 label，用于 LLM 近义扩展的候选集"""
    dal = _get_dal()
    rows = dal._fetchall("SELECT DISTINCT label FROM vocab ORDER BY label")
    return [r['label'] for r in rows]


def _llm_chat(prompt: str) -> Optional[str]:
    """
    用配置的 LLM（优先 [sql] 节中的快速云模型）做一次性纯文本问答。
    用于近义扩展等辅助推理，支持按优先级降级。
    """
    config = load_config()
    # 近义扩展属于"理解"任务，用 sql 节的快速云模型即可，避免慢速推理模型
    for name in get_llm_priority_list(config, purpose='sql'):
        try:
            provider = create_provider(name, config)
            resp = provider.chat(prompt)
            if resp:
                return resp.strip()
        except Exception as e:
            print(f"    [工具LLM] {name} 调用失败: {e}")
            continue
    return None


def _llm_expand_synonyms(tag: str, all_labels: List[str]) -> List[str]:
    """
    让 LLM 把主题词扩展成 vocab 中相关的近义标签集合。
    只返回【确实存在于 vocab】的标签（取交集），保证后续 SQL 可命中。
    """
    if not all_labels:
        return []
    labels_str = "、".join(all_labels)
    prompt = (
        f'你是诗词标签专家。给定主题词"{tag}"，请从下面的受控标签列表中选出'
        f'语义相关（同义、近义、上下位、常共现）的标签，用于召回相关诗词。\n'
        f'只返回一个 JSON 数组（如 ["月","羁旅"]），不要任何其他文字。\n'
        f'可选标签：{labels_str}'
    )
    resp = _llm_chat(prompt)
    if not resp:
        return []
    # 从返回文本中提取 JSON 数组
    try:
        start = resp.index('[')
        end = resp.rindex(']') + 1
        arr = json.loads(resp[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
    if not isinstance(arr, list):
        return []
    known = set(all_labels)
    return [x for x in arr if x in known]


def _semantic_labels(tag: str) -> List[str]:
    """
    兜底：用 vocab 向量的语义相似度召回相关标签（当 LLM 扩展不可用或返回空时）。
    """
    try:
        from KBCP_RAG_Index import VocabLabelMatcher
        matches = VocabLabelMatcher.get_instance().match(tag, threshold=0.5, top_k=8)
        return [label for _, label, _ in matches]
    except Exception:
        return []


def _resolve_and_expand_labels(tag: str, near_synonym: bool) -> List[str]:
    """
    综合标签解析：
      1) 先做确定性 vocab 映射（必做）；
      2) 若 near_synonym=True，再让 LLM 扩展近义标签；
      3) 若 LLM 扩展仍为空，回退到向量语义匹配。
    """
    labels = _resolve_tag_label(tag)
    if not near_synonym:
        return labels
    # LLM 近义扩展
    extra = _llm_expand_synonyms(tag, _all_vocab_labels())
    combined = list(dict.fromkeys(labels + extra))  # 保序去重
    if combined:
        return combined
    # 兜底：向量语义匹配
    return _semantic_labels(tag)


# ============================================================
#  内部辅助：诗词对象 → 可读 dict
# ============================================================

def _poem_to_dict(p) -> Dict:
    """把 PoemData 转为工具返回用的精简结构化 dict"""
    tags = p.tags or []
    tag_labels = [t.get('label') if isinstance(t, dict) else t for t in tags]
    return {
        "poem_id": p.poem_id,
        "title": p.title,
        "author": p.author_name,
        "dynasty": p.dynasty_name,
        "content": p.content,
        "translation": p.translation,
        "appreciation": p.appreciation,
        "background": p.background,
        "tags": tag_labels,
    }


# ============================================================
#  工具实现
# ============================================================

def search_poem(line: str, author: str = None, near_synonym: bool = False) -> Dict:
    """
    按诗句片段或标题片段查找诗词（找出处）。
    适用：用户给出一句诗、半句诗，或带作者前缀的诗句（如"王之涣（唐）白日依山尽"）。
    """
    dal = _get_dal()
    # 1) 精确片段匹配
    rows = dal.search_poems_exact(line, limit=5)

    # 2) 若提供了作者，先按作者过滤
    if author:
        a = _resolve_author(author)
        if a:
            filtered = [r for r in rows if r.get('author_name') == a.name]
            if filtered:
                rows = filtered
            # 若过滤后为空，保留原结果（可能是作者名不匹配）

    # 3) 若仍为空，做模糊标题/内容搜索
    if not rows:
        rows = dal.search_poems(line, limit=5)

    if not rows:
        return {
            "found": False,
            "line": line,
            "message": f"未找到包含「{line}」的诗句，试试输入更完整的句子。",
        }

    return {
        "found": True,
        "line": line,
        "count": len(rows),
        "poems": [
            {
                "poem_id": r['poem_id'],
                "title": r['title'],
                "author": r.get('author_name', ''),
                "dynasty": r.get('dynasty_name', ''),
                "content": r['content'],
            }
            for r in rows
        ],
    }


def get_poem_full(line_or_title: str, near_synonym: bool = False) -> Dict:
    """
    根据诗句片段、标题或关键词，查找并返回诗词完整全文
    （正文、译文、赏析、背景、作者、朝代、标签）。
    适用：用户问"X的全文/全诗"或想看完整内容。
    """
    dal = _get_dal()
    # 1) 精确诗句片段匹配
    rows = dal.search_poems_exact(line_or_title, limit=5)

    # 2) 按标题精确匹配
    if not rows:
        poems = dal.get_poems_by_title(line_or_title)
        rows = [p.to_dict() for p in poems][:5] if poems else []

    # 3) 模糊搜索兜底
    if not rows:
        rows = dal.search_poems(line_or_title, limit=5)

    if not rows:
        return {
            "found": False,
            "query": line_or_title,
            "message": f"未找到与「{line_or_title}」相关的诗词。",
        }

    poems_detail = []
    for r in rows[:5]:
        detail = dal.get_poem_full_detail(r['poem_id'])
        if detail:
            poems_detail.append(_poem_to_dict(detail))

    return {
        "found": True,
        "count": len(poems_detail),
        "poems": poems_detail,
    }


def get_author(name: str, near_synonym: bool = False) -> Dict:
    """查询诗人基本信息（生平、字号、朝代、文学史定位等）"""
    a = _resolve_author(name)
    if not a:
        return {
            "found": False,
            "name": name,
            "message": f"未找到作者「{name}」。",
        }
    d = a.to_dict()
    return {
        "found": True,
        "author": {
            "name": d.get('name'),
            "dynasty": d.get('dynasty_name'),
            "courtesy_name": d.get('courtesy_name'),
            "art_name": d.get('art_name'),
            "birth_year": d.get('birth_year'),
            "death_year": d.get('death_year'),
            "birth_place": d.get('birth_place'),
            "bio": d.get('bio'),
            "historical_role": d.get('historical_role'),
            "representative_works": d.get('representative_works'),
        },
    }


def count_poems(author: str, near_synonym: bool = False) -> Dict:
    """统计某位诗人被收录的诗词总数"""
    dal = _get_dal()
    a = _resolve_author(author)
    if not a:
        return {
            "found": False,
            "author": author,
            "message": f"未找到作者「{author}」。",
        }
    row = dal._fetchone(
        "SELECT COUNT(*) AS c FROM poem WHERE author_id = ?", (a.author_id,)
    )
    cnt = row['c'] if row else 0
    return {
        "found": True,
        "author": a.name,
        "total_count": cnt,
    }


def count_poems_by_tag(author: str, tag: str, near_synonym: bool = False) -> Dict:
    """
    统计某位诗人包含指定主题标签的诗词数量（按标签精确计数）。
    适用：用户问"X写月亮/思乡/边塞的诗有多少"。
    标签解析：确定性 vocab 映射 +（可选）LLM 近义扩展。
    """
    dal = _get_dal()
    a = _resolve_author(author)
    if not a:
        return {
            "found": False,
            "author": author,
            "message": f"未找到作者「{author}」。",
        }

    labels = _resolve_and_expand_labels(tag, near_synonym)
    if not labels:
        return {
            "found": False,
            "author": a.name,
            "tag": tag,
            "message": f"未找到与「{tag}」相关的标签。",
        }

    placeholders = ','.join('?' for _ in labels)
    rows = dal._fetchall(
        f"""
        SELECT v.label AS label, COUNT(DISTINCT p.poem_id) AS cnt
        FROM poem p
        JOIN poem_tag pt ON p.poem_id = pt.poem_id
        JOIN vocab v ON pt.vocab_id = v.vocab_id
        WHERE p.author_id = ? AND v.label IN ({placeholders})
        GROUP BY v.label
        """,
        [a.author_id, *labels]
    )
    total = sum(r['cnt'] for r in rows)
    return {
        "found": True,
        "author": a.name,
        "tag": tag,
        "resolved_labels": labels,
        "per_label": [{"label": r['label'], "count": r['cnt']} for r in rows],
        "total_count": total,
    }


def compare_by_tag(authors: List[str], tag: str, near_synonym: bool = False) -> Dict:
    """
    对比多位诗人包含指定主题标签的诗词数量。
    适用：用户问"A和B谁写X的诗更多"。
    labels 只解析一次，保证对比口径一致。
    """
    dal = _get_dal()
    labels = _resolve_and_expand_labels(tag, near_synonym)

    per_author = []
    for au in authors:
        a = _resolve_author(au)
        if not a:
            per_author.append({
                "author": au, "found": False,
                "message": f"未找到作者「{au}」",
            })
            continue
        if not labels:
            per_author.append({
                "author": a.name, "found": True, "tag": tag,
                "resolved_labels": [], "total_count": 0, "per_label": [],
            })
            continue
        placeholders = ','.join('?' for _ in labels)
        rows = dal._fetchall(
            f"""
            SELECT v.label AS label, COUNT(DISTINCT p.poem_id) AS cnt
            FROM poem p
            JOIN poem_tag pt ON p.poem_id = pt.poem_id
            JOIN vocab v ON pt.vocab_id = v.vocab_id
            WHERE p.author_id = ? AND v.label IN ({placeholders})
            GROUP BY v.label
            """,
            [a.author_id, *labels]
        )
        total = sum(r['cnt'] for r in rows)
        per_author.append({
            "author": a.name,
            "found": True,
            "tag": tag,
            "resolved_labels": labels,
            "per_label": [{"label": r['label'], "count": r['cnt']} for r in rows],
            "total_count": total,
        })

    # 生成比较结论（只基于找到的作者）
    valid = [p for p in per_author if p.get('found')]
    if len(valid) >= 2:
        mx = max(valid, key=lambda x: x['total_count'])
        conclusion = (f"在主题「{tag}」相关诗词上，"
                      f"{mx['author']}收录更多，共 {mx['total_count']} 首。")
    else:
        conclusion = ""

    return {
        "tag": tag,
        "resolved_labels": labels,
        "comparison": per_author,
        "conclusion": conclusion,
    }


def semantic_search(query: str, top_k: int = 5, near_synonym: bool = False) -> Dict:
    """
    智能化 RAG 语义检索：基于向量 + 标签，返回与问题相关的诗词/作者/标签片段。
    适用：开放性问题（赏析、情感、背景、"写思乡的诗"等不适合精确计数回答的问题）。
    """
    from KBCP_RAG_Index import RAGIndex
    index = RAGIndex()
    chunks = index.semantic_search(query, top_k=top_k)
    if not chunks:
        return {
            "found": False,
            "query": query,
            "message": "语义检索未找到相关内容。",
        }
    return {
        "found": True,
        "query": query,
        "chunks": chunks,
    }


# ============================================================
#  工具名称 → 函数 映射（供 Agent dispatch 使用）
# ============================================================

TOOL_FUNCTIONS = {
    "search_poem": search_poem,
    "get_poem_full": get_poem_full,
    "get_author": get_author,
    "count_poems": count_poems,
    "count_poems_by_tag": count_poems_by_tag,
    "compare_by_tag": compare_by_tag,
    "semantic_search": semantic_search,
}
