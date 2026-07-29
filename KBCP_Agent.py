# -*- coding: utf-8 -*-
"""
KBCP_Agent.py - 智能问答 Agent 中枢
====================================
把 LLM 当作"大脑"来理解自然语言，把 KBCP_Tools 中的能力当作"手脚"来调用。
LLM 负责：理解意图 / 清洗参数 / 多步推理 / 指代消解 / 生成自然语言回答；
工具内部用 SQLiteDAL / RAGIndex 保证数字与事实的精确。

流程：
    run_agent(query, history, near_synonym)
      → 构造 system + 历史 + 当前问题（messages）
      → 循环：chat_with_tools → 有 tool_calls 则执行并回灌结果 → 无则返回 content
      → 设 MAX_TURNS 防死循环；provider 按 [agent] 配置顺序，失败降级下一个
"""
import json
from typing import List, Dict, Optional

from KBCP_LLM_Provider import (
    load_config, get_llm_priority_list, create_provider,
)
from KBCP_Tools import TOOL_FUNCTIONS

# 最大推理轮数（防止工具调用死循环）
MAX_TURNS = 5


# ============================================================
#  System Prompt：教导 LLM 如何理解与调用工具
# ============================================================

AGENT_SYSTEM_PROMPT = """你是一位精通中华诗词的智能助手，负责理解用户用自然语言提出的问题，并调用合适的工具来回答。

【核心原则】
1. 先理解，再行动：先判断用户真实意图，再决定调用哪个工具、传什么参数。
2. 清洗输入：用户问题常带噪音，你需要主动提取关键信息：
   - 形如"王之涣（唐）白日依山尽"：拆成 author="王之涣"、line="白日依山尽"，调用 search_poem；
   - "X的全文/全诗"：调用 get_poem_full；
   - "谁写X的诗更多 / A和B谁的诗多"：调用 compare_by_tag；
   - "X有多少/共几首"：调用 count_poems；
   - "X是谁/介绍X"：调用 get_author；
   - 赏析、情感、背景，或"写某主题的诗"这类开放问题：调用 semantic_search。
3. 多步推理：必要时连续调用多个工具（如先 search_poem 找到诗词，再 get_poem_full 取全文）。
4. 指代消解：结合对话历史理解"他""这首诗"等代词（历史已在消息中提供）。
5. 工具无结果时：先尝试换参数或更宽松的查询再试（如 search_poem 用更短片段），仍无果才如实告知。
6. 最终回答：综合工具返回的结构化结果，用自然流畅的中文回答，不要原样罗列 JSON。只依据工具结果，绝不编造事实。
7. 严禁凭记忆作答：你不得依赖自身参数记忆来回答任何事实性问题（作者、朝代、诗句原文、收录数量、出处、生平简介等）。所有事实必须来自工具返回的结果。若工具无结果，如实告知"未查到相关内容"，绝不可凭记忆补全或臆测。
8. 只回答当前问题：聚焦于用户本轮提出的单一问题，用工具结果直接作答，不要引申、不要联想无关内容、不要输出与问题无关的背景知识。"""


# ============================================================
#  工具 Schema（OpenAI 格式，供 LLM 阅读）
# ============================================================

def build_tool_schemas() -> List[Dict]:
    """构造 LLM 可见的工具说明书"""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_poem",
                "description": "根据诗句片段或标题片段查找诗词（找出处/作者）。当用户给出一句诗、半句诗、或带有作者前缀的诗句（如'王之涣（唐）白日依山尽'）时使用。可传 author 缩小范围。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "line": {"type": "string",
                                 "description": "诗句片段或标题片段，如'白日依山尽'"},
                        "author": {"type": "string",
                                    "description": "可选作者名，如'王之涣'，用于缩小范围"},
                    },
                    "required": ["line"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_poem_full",
                "description": "根据诗句片段、标题或关键词，查找并返回该诗词的完整全文（正文、译文、赏析、背景、作者、朝代）。当用户问'X的全文/全诗'或想看完整内容时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "line_or_title": {"type": "string",
                                          "description": "诗句片段、标题或关键词，如'两个黄鹂鸣翠柳'或'静夜思'"},
                    },
                    "required": ["line_or_title"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_author",
                "description": "查询某位诗人的生平、字号、朝代、文学史定位等基本信息。当用户问'X是谁'、'介绍一下X'时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "作者名，如'李白'"},
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "count_poems",
                "description": "统计某位诗人被收录的诗词总数。当用户问'X有多少首诗'、'X共几首'时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "author": {"type": "string", "description": "作者名，如'李白'"},
                    },
                    "required": ["author"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "count_poems_by_tag",
                "description": "统计某位诗人包含指定主题标签的诗词数量（按标签精确计数）。当用户问'X写月亮/思乡/边塞的诗有多少'时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "author": {"type": "string", "description": "作者名，如'李白'"},
                        "tag": {"type": "string", "description": "主题/意象词，如'月'、'思乡'、'边塞'"},
                    },
                    "required": ["author", "tag"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_by_tag",
                "description": "对比多位诗人包含指定主题标签的诗词数量。当用户问'A和B谁写X的诗更多'时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "authors": {"type": "array", "items": {"type": "string"},
                                    "description": "作者名列表，如['李白','杜甫']"},
                        "tag": {"type": "string", "description": "主题/意象词，如'月'"},
                    },
                    "required": ["authors", "tag"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "semantic_search",
                "description": "基于语义向量检索，返回与问题相关的诗词、作者或标签片段。用于开放性问题（赏析、情感、背景、'写思乡的诗'等不适合精确计数回答的问题）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "语义检索的问题或描述"},
                        "top_k": {"type": "integer", "description": "返回条数，默认5"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]


# ============================================================
#  Provider 选择（顺序来自 [agent] 配置，不写死）
# ============================================================

def select_agent_provider(config):
    """
    按 [agent].llm_provider 的顺序产出支持 function calling 的 provider。
    顺序完全来自配置；本地 ollama/deepseek-r1 不支持 tools，会被自动过滤，
    但不改变配置顺序。上一个不可用则降级下一个（由 run_agent 的循环驱动）。
    """
    for name in get_llm_priority_list(config, purpose='agent'):
        provider = create_provider(name, config)
        if provider.supports_tools():
            yield provider
        else:
            print(f"    [Agent] 跳过不支持工具的提供者: {provider.name}")


# ============================================================
#  近义理解开关读取（web 优先，CLI 回退 ini）
# ============================================================

def get_near_synonym_flag() -> bool:
    """
    读取近义理解开关：
      优先 KBCP_web/config.py 的 Config.LLM_NEAR_SYNONYM（Web 模式主设置）；
      读不到则回退 KBCP_LLM_config.ini 的 [agent].llm_near_synonym（CLI 兜底）。
    """
    # 1) 尝试从 web 配置读取（主设置）
    for import_path in ("KBCP_web.config", "config"):
        try:
            mod = __import__(import_path, fromlist=["Config"])
            if hasattr(mod, "Config") and hasattr(mod.Config, "LLM_NEAR_SYNONYM"):
                return bool(mod.Config.LLM_NEAR_SYNONYM)
        except Exception:
            continue

    # 2) 回退到 ini 的 [agent].llm_near_synonym
    try:
        config = load_config()
        if 'agent' in config:
            raw = config['agent'].get('llm_near_synonym', '').strip().lower()
            if raw in ('true', '1', 'yes', 'on'):
                return True
            if raw in ('false', '0', 'no', 'off'):
                return False
    except Exception:
        pass

    # 3) 默认开启
    return True


# ============================================================
#  消息构造
# ============================================================

def _build_messages(query: str, history: list = None,
                    near_synonym: bool = False) -> List[Dict]:
    """
    构造 OpenAI 格式消息：
      system（含是否开启近义理解提示）
      + 历史（user/assistant 交替）
      + 当前用户问题
    history 元素格式：{"q": str, "a": str, "entity": str}
    """
    system_text = AGENT_SYSTEM_PROMPT
    if near_synonym:
        system_text += "\n\n[提示] 当前已开启「主题词近义理解」：涉及主题标签查询时，可信任工具会一并召回近义标签的作品。"
    else:
        system_text += "\n\n[提示] 当前未开启「主题词近义理解」：主题标签查询仅按 vocab 确定性映射（如 月亮→月）。"

    messages = [{"role": "system", "content": system_text}]

    if history:
        for entry in history:
            q = entry.get('q', '') if isinstance(entry, dict) else str(entry)
            a = entry.get('a', '') if isinstance(entry, dict) else ''
            if q:
                messages.append({"role": "user", "content": q})
            if a:
                messages.append({"role": "assistant", "content": a})

    messages.append({"role": "user", "content": query})
    return messages


# ============================================================
#  工具分发
# ============================================================

def dispatch_tool(name: str, arguments: Dict, near_synonym: bool = False) -> Dict:
    """根据工具名分发执行，统一返回结构化 dict。"""
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return {"error": f"未知工具: {name}"}
    try:
        return func(near_synonym=near_synonym, **(arguments or {}))
    except TypeError as e:
        # 某些工具没有 near_synonym 参数，去掉后重试
        try:
            return func(**(arguments or {}))
        except Exception as e2:
            return {"error": f"工具 {name} 调用失败: {e2}"}
    except Exception as e:
        return {"error": f"工具 {name} 执行异常: {e}"}


def _assistant_message_with_tools(resp: Dict) -> Dict:
    """把中枢返回的 tool_calls 重建成 OpenAI 格式的 assistant 消息（供下一轮回灌）"""
    tool_calls = []
    for tc in resp.get('tool_calls', []):
        tool_calls.append({
            "id": tc.get('id', ''),
            "type": "function",
            "function": {
                "name": tc.get('name', ''),
                "arguments": json.dumps(tc.get('arguments', {}),
                                        ensure_ascii=False),
            },
        })
    return {
        "role": "assistant",
        "content": resp.get('content') or None,
        "tool_calls": tool_calls,
    }


# ============================================================
#  Agent 主循环
# ============================================================

def _local_fallback(query: str, near_synonym: bool = False) -> Optional[str]:
    """
    云模型全部不可用时的本地确定性兜底：直接调用 SQLiteDAL 处理
    作者/诗句/计数类问题，保证离线也能回答基础问题（不依赖记忆/云端）。
    返回回答文本；无法处理返回 None。
    """
    try:
        from KBCP_Assistant import (
            _try_deterministic_count, _handle_entity_author,
            _handle_entity_poem, _handle_find_poem,
        )
        from KBCP_AliasMapper import AliasMapper
        mapper = AliasMapper()
        alias_result = mapper.resolve(query)

        # 1) 计数类（最确定）
        det = _try_deterministic_count(query, alias_result)
        if det:
            return det

        # 2) 《》标题
        if '《' in query:
            return _handle_entity_poem(query, alias_result, None)

        # 3) 作者类
        if alias_result.get('matches'):
            for _, std, etype, _ in alias_result['matches']:
                if etype == 'author':
                    return _handle_entity_author(query, alias_result, None)

        # 4) 诗句/出处
        return _handle_find_poem(query, alias_result, None)
    except Exception as e:
        print(f"    [本地兜底异常] {e}")
        return None


def run_agent(query: str, history: list = None,
              near_synonym: bool = False) -> str:
    """
    Agent 中枢主入口。
    参数:
        query: 用户当前问题
        history: 对话历史（用于指代消解与上下文），格式见 _build_messages
        near_synonym: 是否开启主题词近义理解（来自 config）
    返回: LLM 生成的自然语言回答
    """
    if not query or not query.strip():
        return "请输入问题。"

    tools = build_tool_schemas()
    messages = _build_messages(query, history, near_synonym)
    config = load_config()

    last_error = None
    for provider in select_agent_provider(config):
        try:
            for _ in range(MAX_TURNS):
                resp = provider.chat_with_tools(messages, tools)
                if not resp or not resp.get('tool_calls'):
                    # 无工具调用 → 直接返回自然语言回答
                    return (resp.get('content') or '').strip() or "（模型未返回内容）"

                # 有工具调用 → 回灌助手消息，再依次执行工具
                messages.append(_assistant_message_with_tools(resp))
                for tc in resp['tool_calls']:
                    result = dispatch_tool(tc['name'], tc['arguments'], near_synonym)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc['id'],
                        "content": json.dumps(result, ensure_ascii=False,
                                              default=str),
                    })
            # 达到最大轮数仍未结束
            return "已达到最大推理轮数，请简化问题后重试。"
        except Exception as e:
            last_error = f"{provider.name} 调用失败: {e}"
            print(f"    [Agent降级] {last_error}")
            continue

    if last_error:
        fb = _local_fallback(query, near_synonym)
        if fb:
            return fb
        return f"所有 Agent 模型均不可用：{last_error}"
    return "未配置支持工具调用的 LLM（请检查 KBCP_LLM_config.ini 的 [agent] 节）。"
