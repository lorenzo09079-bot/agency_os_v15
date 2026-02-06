# -*- coding: utf-8 -*-
"""
RLM REPL - Agency OS v16
=========================

Root LM: qwen3-max (258k context — no più troncamenti aggressivi)
Sub LM: qwen-plus (fino a 1M context — analizza documenti interi)

Cambio chiave rispetto a v15:
- max_context_tokens è ADATTIVO, basato sul modello scelto
- Con qwen3-max (258k) il sistema ha margine sufficiente per 15+ iterazioni
- Troncamento solo come safety net, non come meccanismo primario
"""

from typing import Dict, List, Optional, Any

from rlm import RLM
from rlm.repl import REPLEnv
from rlm.utils.llm import OpenAIClient
from rlm.utils.prompts import DEFAULT_QUERY, next_action_prompt, build_system_prompt
import rlm.utils.utils as utils

from rlm.logger.root_logger import ColorfulLogger
from rlm.logger.repl_logger import REPLEnvLogger

try:
    from config import QWEN_MODEL_ROOT, QWEN_MODEL_SUB, get_safe_context_limit
except ImportError:
    QWEN_MODEL_ROOT = "qwen3-max"
    QWEN_MODEL_SUB = "qwen-plus"
    def get_safe_context_limit(model=None):
        return 200000  # Fallback sicuro per qwen3-max


class RLM_REPL(RLM):
    """
    Recursive Language Model con REPL environment.
    
    Root LM orchestra il processo (esplora, delega, sintetizza).
    Sub LM analizza i documenti (riceve il contenuto completo).
    Tools Qdrant vengono iniettati nel REPL.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
        recursive_model: str = None,
        max_iterations: int = 20,
        depth: int = 0,
        enable_logging: bool = True,
        max_context_tokens: int = None,  # None = adattivo dal modello
    ):
        self.api_key = api_key
        self.model = model or QWEN_MODEL_ROOT
        self.recursive_model = recursive_model or QWEN_MODEL_SUB
        self.llm = OpenAIClient(api_key, self.model)
        
        self.repl_env = None
        self.depth = depth
        self._max_iterations = max_iterations
        
        # Limite contesto ADATTIVO basato sul modello
        if max_context_tokens is not None:
            self._max_context_tokens = max_context_tokens
        else:
            self._max_context_tokens = get_safe_context_limit(self.model)
        
        self.logger = ColorfulLogger(enabled=enable_logging)
        self.repl_env_logger = REPLEnvLogger(enabled=enable_logging)
        
        self.messages = []
        self.query = None
        self._iteration_count = 0
    
    def setup_context(self, context: List[str] | str | List[Dict[str, str]], query: Optional[str] = None):
        """Inizializza il contesto per l'analisi RLM."""
        if query is None:
            query = DEFAULT_QUERY

        self.query = query
        self.logger.log_query_start(query)

        self.messages = build_system_prompt()
        self.logger.log_initial_messages(self.messages)
        
        context_data, context_str = utils.convert_context_for_repl(context)
        
        self.repl_env = REPLEnv(
            context_json=context_data,
            context_str=context_str,
            recursive_model=self.recursive_model,
        )
        
        return self.messages

    def _check_context_size(self) -> bool:
        """
        Safety net: tronca messaggi solo se il contesto supera il limite.
        Con qwen3-max (258k) questo dovrebbe accadere raramente.
        """
        total_text = "".join(m.get("content", "") for m in self.messages)
        estimated_tokens = len(total_text) // 4
        
        if estimated_tokens > self._max_context_tokens:
            self.logger.log_tool_execution(
                "CONTEXT_OVERFLOW", 
                f"Contesto {estimated_tokens:,} tokens > limite {self._max_context_tokens:,}. Troncamento..."
            )
            self.messages = utils.truncate_messages_if_needed(
                self.messages, self._max_context_tokens
            )
            return True
        return False

    def completion(self, context: List[str] | str | List[Dict[str, str]], query: Optional[str] = None) -> str:
        """
        Dato un contesto e una query, usa il REPL ricorsivamente per esplorare
        il contesto e produrre una risposta.
        """
        self.messages = self.setup_context(context, query)
        self._iteration_count = 0
        
        for iteration in range(self._max_iterations):
            self._iteration_count = iteration + 1
            self._check_context_size()
            
            # Query al Root LM
            try:
                response = self.llm.completion(
                    self.messages + [next_action_prompt(query, iteration)]
                )
            except Exception as e:
                error_msg = str(e)
                # Errore di contesto troppo lungo: tronca aggressivamente e riprova
                if any(kw in error_msg.lower() for kw in ["length", "token", "30720", "258048"]):
                    self.logger.log_tool_execution(
                        "CONTEXT_ERROR",
                        f"Errore contesto: {error_msg[:200]}. Troncamento aggressivo..."
                    )
                    self.messages = utils.truncate_messages_if_needed(
                        self.messages, self._max_context_tokens // 2
                    )
                    try:
                        response = self.llm.completion(
                            self.messages + [next_action_prompt(query, iteration)]
                        )
                    except Exception as e2:
                        return f"Errore critico dopo troncamento: {str(e2)}"
                else:
                    return f"Errore: {error_msg}"
            
            # Processa la risposta
            code_blocks = utils.find_code_blocks(response)
            self.logger.log_model_response(response, has_tool_calls=code_blocks is not None)
            
            if code_blocks:
                self.messages = utils.process_code_execution(
                    response, self.messages, self.repl_env,
                    self.repl_env_logger, self.logger
                )
            else:
                self.messages.append({"role": "assistant", "content": response})
            
            # Controlla risposta finale
            final_answer = utils.check_for_final_answer(
                response, self.repl_env, self.logger
            )
            
            if final_answer:
                self.logger.log_final_response(final_answer)
                return final_answer
        
        # Max iterations raggiunto: forza risposta finale
        self.messages = utils.truncate_messages_if_needed(
            self.messages, self._max_context_tokens // 2
        )
        self.messages.append(next_action_prompt(query, iteration, final_answer=True))
        
        try:
            final_answer = self.llm.completion(self.messages)
        except:
            final_answer = "Non sono riuscito a completare l'analisi entro il numero massimo di iterazioni."
        
        self.logger.log_final_response(final_answer)
        return final_answer
    
    def cost_summary(self) -> Dict[str, Any]:
        """Statistiche costo Root + Sub LM."""
        root_stats = self.llm.get_usage_stats()
        sub_stats = {}
        if self.repl_env and hasattr(self.repl_env, 'sub_rlm'):
            sub_stats = self.repl_env.sub_rlm.cost_summary()
        
        return {
            "root": root_stats,
            "sub": sub_stats,
            "iterations": self._iteration_count
        }

    def reset(self):
        """Reset environment e cronologia."""
        if self.repl_env:
            del self.repl_env
        self.repl_env = None
        self.messages = []
        self.query = None
        self._iteration_count = 0
