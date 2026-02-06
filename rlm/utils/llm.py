# -*- coding: utf-8 -*-
"""
OpenAI-compatible Client per Qwen (DashScope) - Agency OS v15
"""

import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Import config (con fallback robusto)
try:
    from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL_ROOT, QWEN_MODEL_SUB
except ImportError:
    QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL_ROOT = "qwen-max"
    QWEN_MODEL_SUB = "qwen-plus"


class OpenAIClient:
    """Client compatibile OpenAI per Qwen via DashScope."""
    
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
        
        # Token tracking
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
            raise RuntimeError(f"Errore completion ({self.model}): {str(e)}")
    
    def get_usage_stats(self) -> dict:
        """Statistiche uso e costo stimato."""
        prices = {
            "qwen-max":         {"input": 2.0,  "output": 8.0},
            "qwen3-coder-plus": {"input": 1.0,  "output": 5.0},
            "qwen-plus":        {"input": 0.4,  "output": 1.2},
            "qwen-flash":       {"input": 0.05, "output": 0.4},
        }
        p = prices.get(self.model, {"input": 2.0, "output": 8.0})
        cost = (self.total_input_tokens / 1_000_000) * p["input"] + \
               (self.total_output_tokens / 1_000_000) * p["output"]
        
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
