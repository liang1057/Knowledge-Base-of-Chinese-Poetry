# -*- coding: utf-8 -*-
"""
KBCP_LLM_Provider.py - 大语言模型提供者抽象层
支持: Ollama(本地), DeepSeek(云端), 智谱GLM(云端)
OpenAI 兼容格式封装，统一调用接口
"""

import requests
import configparser
from pathlib import Path
from typing import Optional


# ============================================================
#  抽象基类
# ============================================================
class LLMProvider:
    """所有提供者需实现的接口"""

    def chat(self, prompt: str) -> Optional[str]:
        """发送 prompt 给模型，返回文本内容，失败返回 None"""
        raise NotImplementedError

    @property
    def name(self) -> str:
        """返回模型标识名（用于日志/auto_tag_log.model 字段）"""
        raise NotImplementedError

    def __str__(self) -> str:
        return f"<Provider: {self.name}>"


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
                                 json=payload, timeout=120)
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
            resp = requests.post(self.base_url, headers=headers, json=data, timeout=120)
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
