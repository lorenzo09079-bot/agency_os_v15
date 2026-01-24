# -*- coding: utf-8 -*-
"""
RLM Client per Qwen (via DashScope OpenAI-compatible API)
Integrazione con il framework RLM ufficiale

Questo client permette di usare Qwen-max come backend per RLM.
"""
import os
from collections import defaultdict
from typing import Any

from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

# Prova a importare i tipi RLM, altrimenti definiscili localmente
try:
    from rlm.clients.base_lm import BaseLM
    from rlm.core.types import ModelUsageSummary, UsageSummary
    RLM_AVAILABLE = True
except ImportError:
    RLM_AVAILABLE = False
    # Fallback se RLM non è installato come package
    from abc import ABC, abstractmethod
    from dataclasses import dataclass
    
    @dataclass
    class ModelUsageSummary:
        total_calls: int
        total_input_tokens: int
        total_output_tokens: int
        
        def to_dict(self):
            return {
                "total_calls": self.total_calls,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
            }
    
    @dataclass
    class UsageSummary:
        model_usage_summaries: dict
        
        def to_dict(self):
            return {
                "model_usage_summaries": {
                    k: v.to_dict() for k, v in self.model_usage_summaries.items()
                }
            }
    
    class BaseLM(ABC):
        def __init__(self, model_name: str, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs
        
        @abstractmethod
        def completion(self, prompt: str | dict[str, Any]) -> str:
            raise NotImplementedError
        
        @abstractmethod
        async def acompletion(self, prompt: str | dict[str, Any]) -> str:
            raise NotImplementedError
        
        @abstractmethod
        def get_usage_summary(self) -> UsageSummary:
            raise NotImplementedError
        
        @abstractmethod
        def get_last_usage(self) -> ModelUsageSummary:
            raise NotImplementedError

load_dotenv()

# Configurazione DashScope (Qwen)
DEFAULT_QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-96a9773427c649d5a6af2a6842404c88")
DEFAULT_QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class QwenRLMClient(BaseLM):
    """
    Client RLM per Qwen via DashScope API (OpenAI-compatible).
    
    Supporta:
    - qwen-max (più potente, per ragionamento complesso)
    - qwen-plus (più veloce, per sub-calls)
    - qwen-turbo (economico, per task semplici)
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "qwen-max",
        base_url: str | None = None,
        **kwargs,
    ):
        super().__init__(model_name=model_name, **kwargs)
        
        self.api_key = api_key or DEFAULT_QWEN_API_KEY
        self.base_url = base_url or DEFAULT_QWEN_BASE_URL
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Tracking usage
        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)
        
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
    
    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        """Esegue una completion sincrona."""
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        elif isinstance(prompt, list) and all(isinstance(item, dict) for item in prompt):
            messages = prompt
        else:
            raise ValueError(f"Invalid prompt type: {type(prompt)}")
        
        model = model or self.model_name
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
        )
        
        self._track_usage(response, model)
        return response.choices[0].message.content
    
    async def acompletion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        """Esegue una completion asincrona."""
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        elif isinstance(prompt, list) and all(isinstance(item, dict) for item in prompt):
            messages = prompt
        else:
            raise ValueError(f"Invalid prompt type: {type(prompt)}")
        
        model = model or self.model_name
        
        response = await self.async_client.chat.completions.create(
            model=model,
            messages=messages,
        )
        
        self._track_usage(response, model)
        return response.choices[0].message.content
    
    def _track_usage(self, response, model: str):
        """Traccia l'uso dei token."""
        self.model_call_counts[model] += 1
        
        usage = getattr(response, "usage", None)
        if usage:
            self.model_input_tokens[model] += usage.prompt_tokens
            self.model_output_tokens[model] += usage.completion_tokens
            self.model_total_tokens[model] += usage.total_tokens
            
            self.last_prompt_tokens = usage.prompt_tokens
            self.last_completion_tokens = usage.completion_tokens
    
    def get_usage_summary(self) -> UsageSummary:
        """Ritorna il riepilogo dell'uso."""
        summaries = {}
        for model in self.model_call_counts:
            summaries[model] = ModelUsageSummary(
                total_calls=self.model_call_counts[model],
                total_input_tokens=self.model_input_tokens[model],
                total_output_tokens=self.model_output_tokens[model],
            )
        return UsageSummary(model_usage_summaries=summaries)
    
    def get_last_usage(self) -> ModelUsageSummary:
        """Ritorna l'uso dell'ultima chiamata."""
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self.last_prompt_tokens,
            total_output_tokens=self.last_completion_tokens,
        )


# Funzione helper per creare il client
def create_qwen_client(
    model: str = "qwen-max",
    api_key: str | None = None
) -> QwenRLMClient:
    """
    Crea un client Qwen per RLM.
    
    Args:
        model: Nome del modello (qwen-max, qwen-plus, qwen-turbo)
        api_key: API key (opzionale, usa env var se non specificato)
    
    Returns:
        QwenRLMClient configurato
    """
    return QwenRLMClient(
        api_key=api_key,
        model_name=model
    )


# Test
if __name__ == "__main__":
    print("Test QwenRLMClient...")
    print(f"RLM Framework disponibile: {RLM_AVAILABLE}")
    
    client = create_qwen_client("qwen-max")
    
    response = client.completion("Dimmi 'ciao' in 3 lingue diverse.")
    print(f"Risposta: {response}")
    
    usage = client.get_usage_summary()
    print(f"Usage: {usage.to_dict()}")
