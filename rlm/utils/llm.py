# -*- coding: utf-8 -*-
"""
OpenAI-compatible Client per Qwen (DashScope)
Per RLM Minimal - Agency OS

QUESTO FILE SOSTITUISCE rlm/utils/llm.py
"""

import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configurazione Qwen via DashScope
DEFAULT_API_KEY = os.getenv("QWEN_API_KEY", "sk-96a9773427c649d5a6af2a6842404c88")
DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class OpenAIClient:
    """
    Client compatibile con RLM Minimal che usa Qwen via DashScope.
    L'API DashScope è compatibile con il formato OpenAI.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = "qwen-max",
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or DEFAULT_API_KEY
        self.base_url = base_url or DEFAULT_BASE_URL
        
        if not self.api_key:
            raise ValueError(
                "API key richiesta. Imposta QWEN_API_KEY come variabile ambiente "
                "o passa api_key come parametro."
            )
        
        self.model = model
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # Per tracking costi (opzionale)
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
        """
        Esegue una completion.
        
        Args:
            messages: Lista di messaggi o stringa singola
            max_tokens: Limite token output
            temperature: Creatività (0-1)
            **kwargs: Altri parametri passati all'API
        
        Returns:
            Testo della risposta
        """
        try:
            # Normalizza input
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            elif isinstance(messages, dict):
                messages = [messages]

            # Prepara parametri chiamata
            call_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                call_params["max_completion_tokens"] = max_tokens
            
            # Aggiungi altri kwargs (escludendo quelli non supportati)
            for key, value in kwargs.items():
                if key not in ["timeout"]:  # timeout gestito separatamente
                    call_params[key] = value

            # Esegui chiamata
            response = self.client.chat.completions.create(**call_params)
            
            # Tracking usage
            if hasattr(response, 'usage') and response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens
                self.total_calls += 1
            
            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"Errore generazione completion: {str(e)}")
    
    def get_usage_stats(self) -> dict:
        """Ritorna statistiche di utilizzo."""
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost": self._calculate_cost()
        }
    
    def _calculate_cost(self) -> float:
        """Calcola costo stimato (prezzi Qwen approssimativi)."""
        # Qwen-max: ~$0.004/1K input, $0.012/1K output
        input_cost = (self.total_input_tokens / 1000) * 0.004
        output_cost = (self.total_output_tokens / 1000) * 0.012
        return input_cost + output_cost
    
    def reset_stats(self):
        """Reset statistiche."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0


# Test
if __name__ == "__main__":
    print("Test OpenAIClient (Qwen)...")
    
    client = OpenAIClient(model="qwen-max")
    
    response = client.completion("Dimmi 'ciao' in 3 lingue.")
    print(f"Risposta: {response}")
    
    stats = client.get_usage_stats()
    print(f"Stats: {stats}")