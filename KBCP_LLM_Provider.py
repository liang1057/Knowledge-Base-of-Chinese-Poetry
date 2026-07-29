# -*- coding: utf-8 -*-
"""
KBCP_LLM_Provider.py - 大语言模型提供者抽象层
支持: Ollama(本地), DeepSeek(云端), 智谱GLM(云端)
OpenAI 兼容格式封装，统一调用接口
"""

import json
import requests
import configparser
from pathlib import Path
from typing import Optional, List, Dict

# 统一的外呼代理设置：设为 None 表示直连、绕过系统代理
# （公司网络下系统代理会拦截 api.deepseek.com 等 HTTPS 请求，导致 ProxyError）
API_PROXIES = {"http": None, "https": None}


# ============================================================
#  抽象基类
# ============================================================
class LLMProvider:
    """所有提供者需实现的接口"""

    def chat(self, prompt: str) -> Optional[str]:
        """发送 prompt 给模型，返回文本内容，失败返回 None"""
        raise NotImplementedError

    def supports_tools(self) -> bool:
        """
        是否支持 function calling（工具调用）。
        本地推理模型（如 ollama/deepseek-r1）不支持，返回 False；
        云模型（deepseek-chat / zhipu glm）支持，返回 True。
        默认 False，子类按需重写。
        """
        return False

    def chat_with_tools(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """
        Agent 中枢核心接口：带工具定义的对话。
        参数:
            messages: OpenAI 格式消息列表
                      [{"role":"system"/"user"/"assistant"/"tool", "content":...}]
            tools:    OpenAI 格式工具定义列表（由 KBCP_Agent.build_tool_schemas 生成）
        返回统一结构:
            {
                "content": str,                      # 模型文本（可能为空）
                "tool_calls": [                       # 需要调用的工具列表，无则为空
                    {"id": str, "name": str, "arguments": dict}
                ]
            }
        子类若不重写则抛 NotImplementedError。
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        """返回模型标识名（用于日志/auto_tag_log.model 字段）"""
        raise NotImplementedError

    def __str__(self) -> str:
        return f"<Provider: {self.name}>"


def _parse_tool_calls_from_message(message: dict) -> List[Dict]:
    """
    从 OpenAI 兼容的 message 中解析 tool_calls，统一为
    [{"id", "name", "arguments"(dict)}] 结构。
    兼容 deepseek / zhipu 的返回格式。
    """
    tool_calls = []
    raw_calls = message.get("tool_calls") or []
    for tc in raw_calls:
        fn = tc.get("function", {}) if isinstance(tc, dict) else {}
        raw_args = fn.get("arguments", "{}")
        # arguments 可能是 JSON 字符串，也可能是已解析的 dict
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args) if raw_args.strip() else {}
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args or {}
        tool_calls.append({
            "id": tc.get("id", ""),
            "name": fn.get("name", ""),
            "arguments": args,
        })
    return tool_calls


# ============================================================
#  Ollama 本地提供者
# ============================================================
class OllamaProvider(LLMProvider):
    def __init__(self, config_section):
        self.url = config_section.get('url', 'http://localhost:11434/api/chat')
        self.model = config_section.get('model', 'deepseek-r1:8b')

    @property
    def name(self) -> str:
        return f"ollama/{self.model}"

    def chat(self, prompt: str) -> Optional[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 2000
            }
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=600)
            if resp.status_code != 200:
                return None
            return resp.json().get("message", {}).get("content", "")
        except Exception as e:
            print(f"    [Ollama异常] {e}")
            return None


# ============================================================
#  OpenAI 兼容格式基类 (DeepSeek / 智谱GLM 共用)
# ============================================================
class OpenAILikeProvider(LLMProvider):
    """OpenAI Chat Completions 格式的云端 API"""

    def __init__(self, config_section):
        self.api_key = config_section.get('api_key', '').strip()
        self.model = config_section.get('model', '')
        self.base_url = config_section.get('base_url', '').rstrip('/')

    def chat(self, prompt: str) -> Optional[str]:
        if not self.api_key:
            print(f"    [错误] {self.name} 未配置 api_key")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2000,
            "stream": False
        }
        try:
            resp = requests.post(self.base_url, headers=headers,
                                 json=payload, timeout=120,
                                 proxies=API_PROXIES)
            if resp.status_code != 200:
                print(f"    [API错误] HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            print("    [API超时] 请求超时")
            return None
        except KeyError as e:
            print(f"    [API解析错误] 响应格式异常: {e}")
            return None
        except Exception as e:
            print(f"    [API异常] {e}")
            return None

    def supports_tools(self) -> bool:
        """OpenAI 兼容云模型（deepseek-chat 等）支持 function calling"""
        return True

    def chat_with_tools(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """
        Agent 中枢调用：发送带 tools 的消息，返回统一结构。
        使用 OpenAI Chat Completions 兼容接口。
        """
        if not self.api_key:
            raise ValueError(f"{self.name} 未配置 api_key")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",     # 由模型自行决定是否调用工具
            "temperature": 0.3,
            "max_tokens": 2000,
            "stream": False
        }
        try:
            resp = requests.post(self.base_url, headers=headers,
                                 json=payload, timeout=120,
                                 proxies=API_PROXIES)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            tool_calls = _parse_tool_calls_from_message(message)
            return {"content": content, "tool_calls": tool_calls}
        except requests.exceptions.Timeout:
            print("    [API超时] 工具调用请求超时")
            raise
        except Exception as e:
            print(f"    [API异常] 工具调用失败: {e}")
            raise


class DeepSeekProvider(OpenAILikeProvider):
    @property
    def name(self) -> str:
        return f"deepseek/{self.model}"


class ZhipuProvider(LLMProvider):
    """智谱 GLM 提供者 — 优先使用官方 zhipuai SDK，不可用时回退到 HTTP 请求"""

    # 默认 API 端点
    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def __init__(self, config_section):
        self.api_key = config_section.get('api_key', '').strip()
        self.model = config_section.get('model', 'glm-4.7-flash')
        self.base_url = config_section.get('base_url', self.DEFAULT_BASE_URL)

    @property
    def name(self) -> str:
        return f"zhipu/{self.model}"

    def chat(self, prompt: str) -> Optional[str]:
        if not self.api_key:
            print(f"    [错误] ZhipuProvider 未配置 api_key")
            return None

        # 方法一：尝试使用官方 SDK
        result = self._chat_with_sdk(prompt)
        if result is not None:
            return result

        # 方法二：SDK 不可用时回退到 HTTP 请求
        return self._chat_with_http(prompt)

    def _chat_with_sdk(self, prompt: str) -> Optional[str]:
        """使用官方 zhipuai SDK 调用"""
        print("    [信息] zhipuai SDK 未安装(需要python3.11以上的版本才行)，尝试 使用 HTTP")
        return None
        try:
            from zhipuai import ZhipuAI
            client = ZhipuAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10000,
                stream=False,
            )
            return response.choices[0].message.content
        except ImportError:
            print("    [信息] zhipuai SDK 未安装，尝试 HTTP 回退")
            return None
        except Exception as e:
            print(f"    [智谱SDK异常] {e}，尝试 HTTP 回退")
            return None

    def _chat_with_http(self, prompt: str) -> Optional[str]:
        """通用 HTTP 请求回退方案"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 10000,
            "stream": False
        }
        try:
            resp = requests.post(self.base_url, headers=headers, json=data,
                                 timeout=120, proxies=API_PROXIES)
            if resp.status_code != 200:
                print(f"    [智谱HTTP错误] {resp.status_code}: {resp.text[:200]}")
                return None
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            try:
                resp = requests.post(
                    self.base_url, headers=headers, json=data,
                    timeout=120, proxies={"http": None, "https": None}
                )
                if resp.status_code != 200:
                    print(f"    [智谱HTTP错误] {resp.status_code}: {resp.text[:200]}")
                    return None
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"    [智谱HTTP异常] {e}")
                return None

    def supports_tools(self) -> bool:
        """智谱 GLM（OpenAI 兼容端点）支持 function calling"""
        return True

    def chat_with_tools(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """
        Agent 中枢调用：发送带 tools 的消息，返回统一结构。
        智谱 v4 端点兼容 OpenAI 工具调用格式。
        """
        if not self.api_key:
            raise ValueError(f"{self.name} 未配置 api_key")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 2000,
            "stream": False,
        }
        try:
            resp = requests.post(self.base_url, headers=headers,
                                 json=payload, timeout=120,
                                 proxies=API_PROXIES)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            tool_calls = _parse_tool_calls_from_message(message)
            return {"content": content, "tool_calls": tool_calls}
        except requests.exceptions.Timeout:
            print("    [智谱HTTP超时] 工具调用请求超时")
            raise
        except Exception as e:
            print(f"    [智谱HTTP异常] 工具调用失败: {e}")
            raise


# ============================================================
#  配置文件加载
# ============================================================

DEFAULT_CONFIG_PATH = Path(__file__).parent / "KBCP_LLM_config.ini"

# 默认配置（无 ini 文件时使用的兜底值）
FALLBACK_CONFIG = {
    'provider': {'default': 'ollama'},
    'ollama': {
        'url': 'http://localhost:11434/api/chat',
        'model': 'deepseek-r1:8b',
    },
    'deepseek': {
        'api_key': '',
        'model': 'deepseek-chat',
        'base_url': 'https://api.deepseek.com/v1/chat/completions',
    },
    'zhipu': {
        'api_key': '',
        'model': 'glm-4-flash',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    },
    'common': {
        'request_interval': '0.3',
        'max_content_len': '600',
    },
}


def load_config(config_path=None) -> configparser.SectionProxy:
    """
    加载配置文件，返回 ConfigParser 对象。
    如果文件不存在，基于 FALLBACK_CONFIG 创建。
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config = configparser.ConfigParser()

    if config_path.exists():
        config.read(str(config_path), encoding='utf-8')
    else:
        # 用默认配置写一个初始文件
        config.read_dict(FALLBACK_CONFIG)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(config_path), 'w', encoding='utf-8') as f:
            config.write(f)
        print(f"[信息] 已创建默认配置文件: {config_path}")
        print(f"       请编辑该文件填写 API Key 后重新运行")

    return config


def create_provider(provider_name: str, config) -> LLMProvider:
    """
    提供者工厂函数。
    provider_name: 'ollama', 'deepseek', 'zhipu'
    config: ConfigParser 对象
    """
    provider_map = {
        'ollama': OllamaProvider,
        'deepseek': DeepSeekProvider,
        'zhipu': ZhipuProvider,
    }

    cls = provider_map.get(provider_name)
    if not cls:
        raise ValueError(f"不支持的提供者: {provider_name}，可选: {list(provider_map.keys())}")

    section = config[provider_name] if provider_name in config else {}
    return cls(section)


def get_llm_priority_list(config, purpose: str = '') -> list:
    """
    获取 LLM 提供者的优先级列表（按优先级从高到低）。
    
    参数:
        purpose: 'sql'  时优先使用 [sql] 节的配置（非推理模型）
                 'agent'时优先使用 [agent] 节的配置（必须支持 function calling 的云模型）
                 空字符串时使用默认的 [assistant] 配置
    
    数据来源（优先级从高到低）：
      1. [agent] 节的 llm_provider（仅 purpose='agent' 时）
      2. [sql] 节的 llm_provider（仅 purpose='sql' 时）
      3. [assistant] 节的 llm_provider 字段（支持逗号分隔）
      4. [provider] 节的 default 字段
      5. 已配置了节名的已知提供者（ollama, deepseek, zhipu）
    
    返回: 提供者名称列表，如 ['deepseek', 'zhipu']
    注: 本函数只负责返回【配置中的顺序】，不负责过滤 supports_tools，
        过滤在调用方（select_agent_provider）完成。
    """
    known_providers = ['ollama', 'deepseek', 'zhipu']
    
    # 来源0: purpose='agent' 时优先使用 [agent] 节的配置
    if purpose == 'agent' and 'agent' in config:
        raw = config['agent'].get('llm_provider', '').strip()
        if raw:
            candidates = [p.strip() for p in raw.split(',') if p.strip()]
            candidates = [p for p in candidates if p in known_providers]
            if candidates:
                return candidates
    
    # 来源1: purpose='sql' 时优先使用 [sql] 节的配置
    if purpose == 'sql' and 'sql' in config:
        raw = config['sql'].get('llm_provider', '').strip()
        if raw:
            candidates = [p.strip() for p in raw.split(',') if p.strip()]
            candidates = [p for p in candidates if p in known_providers]
            if candidates:
                return candidates
    
    # 来源1: [assistant] 节的 llm_provider
    if 'assistant' in config:
        raw = config['assistant'].get('llm_provider', '').strip()
        if raw:
            candidates = [p.strip() for p in raw.split(',') if p.strip()]
            # 只保留已知提供者
            candidates = [p for p in candidates if p in known_providers]
            if candidates:
                return candidates
    
    # 来源2: [provider] 节的 default
    if 'provider' in config:
        default = config['provider'].get('default', '').strip()
        if default and default in known_providers:
            return [default]
    
    # 来源3: 兜底，返回所有已知提供者
    return list(known_providers)
