# -*- coding: utf-8 -*-
"""
OpenAI-compatible Client per Qwen (DashScope) - Agency OS v14
"""

import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Import config (con fallback)
try:
    from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL_ROOT, QWEN_MODEL_SUB
except ImportError:
    QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-c6cdd02fbdb14232a22a589b94a18d14")
    QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL_ROOT = "qwen3-coder-plus"
    QWEN_MODEL_SUB = "qwen-plus"


class OpenAIClient:
    """Client compatibile con RLM che usa Qwen via DashScope."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or QWEN_API_KEY
        self.base_url = base_url or QWEN_BASE_URL
        self.model = model or QWEN_MODEL_ROOT
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
    
    def completion(
        self,
        messages: list[dict[str, str]] | str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        try:
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            elif isinstance(messages, dict):
                messages = [messages]

            call_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                call_params["max_completion_tokens"] = max_tokens

            response = self.client.chat.completions.create(**call_params)
            
            if hasattr(response, 'usage') and response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens
                self.total_calls += 1
            
            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"Errore completion: {str(e)}")
    
    def get_usage_stats(self) -> dict:
        prices = {
            "qwen3-coder-plus": {"input": 1.0, "output": 5.0},
            "qwen-plus": {"input": 0.4, "output": 1.2},
            "qwen-flash": {"input": 0.05, "output": 0.4},
        }
        model_prices = prices.get(self.model, {"input": 1.0, "output": 5.0})
        cost = (self.total_input_tokens / 1_000_000) * model_prices["input"] + \
               (self.total_output_tokens / 1_000_000) * model_prices["output"]
        
        return {
            "calls": self.total_calls,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "model": self.model,
            "cost_usd": round(cost, 4)
        }
    
    def reset_stats(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0


def create_root_client(api_key: Optional[str] = None) -> OpenAIClient:
    """Client per Root LM (codice)."""
    return OpenAIClient(api_key=api_key, model=QWEN_MODEL_ROOT)


def create_sub_client(api_key: Optional[str] = None) -> OpenAIClient:
    """Client per Sub LM (testi)."""
    return OpenAIClient(api_key=api_key, model=QWEN_MODEL_SUB)
