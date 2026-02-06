# -*- coding: utf-8 -*-
"""
RLM REPL - Agency OS v14
Root LM: qwen3-coder-plus
Sub LM: qwen-plus
"""

from typing import Dict, List, Optional, Any 

from rlm import RLM
from rlm.repl import REPLEnv
from rlm.utils.llm import OpenAIClient
from rlm.utils.prompts import DEFAULT_QUERY, next_action_prompt, build_system_prompt
import rlm.utils.utils as utils

from rlm.logger.root_logger import ColorfulLogger
from rlm.logger.repl_logger import REPLEnvLogger

# Import config
try:
    from config import QWEN_MODEL_ROOT, QWEN_MODEL_SUB
except ImportError:
    QWEN_MODEL_ROOT = "qwen3-coder-plus"
    QWEN_MODEL_SUB = "qwen-plus"


class RLM_REPL(RLM):
    """
    RLM con REPL environment.
    v14: Root=qwen3-coder-plus, Sub=qwen-plus
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 model: str = None,
                 recursive_model: str = None,
                 max_iterations: int = 20,
                 depth: int = 0,
                 enable_logging: bool = True,
                 max_context_tokens: int = 80000,  # Aumentato per risposte lunghe
                 ):
        self.api_key = api_key
        self.model = model or QWEN_MODEL_ROOT
        self.recursive_model = recursive_model or QWEN_MODEL_SUB
        self.llm = OpenAIClient(api_key, self.model)
        
        self.repl_env = None
        self.depth = depth
        self._max_iterations = max_iterations
        self._max_context_tokens = max_context_tokens
        
        self.logger = ColorfulLogger(enabled=enable_logging)
        self.repl_env_logger = REPLEnvLogger(enabled=enable_logging)
        
        self.messages = []
        self.query = None
        self._iteration_count = 0
    
    def setup_context(self, context: List[str] | str | List[Dict[str, str]], query: Optional[str] = None):
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
        total_text = "".join(m.get("content", "") for m in self.messages)
        estimated_tokens = len(total_text) // 4
        
        if estimated_tokens > self._max_context_tokens:
            self.logger.log_tool_execution("CONTEXT_OVERFLOW", f"Troncamento ({estimated_tokens} tokens)...")
            self.messages = utils.truncate_messages_if_needed(self.messages, self._max_context_tokens)
            return True
        return False

    def completion(self, context: List[str] | str | List[Dict[str, str]], query: Optional[str] = None) -> str:
        self.messages = self.setup_context(context, query)
        self._iteration_count = 0
        
        for iteration in range(self._max_iterations):
            self._iteration_count = iteration + 1
            self._check_context_size()
            
            try:
                response = self.llm.completion(self.messages + [next_action_prompt(query, iteration)])
            except Exception as e:
                error_msg = str(e)
                if "length" in error_msg.lower() or "token" in error_msg.lower():
                    self.messages = utils.truncate_messages_if_needed(self.messages, self._max_context_tokens // 2)
                    try:
                        response = self.llm.completion(self.messages + [next_action_prompt(query, iteration)])
                    except Exception as e2:
                        return f"Errore critico: {str(e2)}"
                else:
                    return f"Errore: {error_msg}"
            
            code_blocks = utils.find_code_blocks(response)
            self.logger.log_model_response(response, has_tool_calls=code_blocks is not None)
            
            if code_blocks is not None:
                self.messages = utils.process_code_execution(
                    response, self.messages, self.repl_env, 
                    self.repl_env_logger, self.logger
                )
            else:
                # NON troncare le risposte - servono complete per analisi dettagliate
                self.messages.append({"role": "assistant", "content": response})
            
            final_answer = utils.check_for_final_answer(response, self.repl_env, self.logger)

            if final_answer:
                self.logger.log_final_response(final_answer)
                return final_answer

        # Max iterations
        self.messages = utils.truncate_messages_if_needed(self.messages, self._max_context_tokens // 2)
        self.messages.append(next_action_prompt(query, iteration, final_answer=True))
        
        try:
            final_answer = self.llm.completion(self.messages)
        except:
            final_answer = "Non sono riuscito a completare l'analisi."
        
        self.logger.log_final_response(final_answer)
        return final_answer
    
    def cost_summary(self) -> Dict[str, Any]:
        return {
            "iterations": self._iteration_count,
            "root_model": self.model,
            "sub_model": self.recursive_model,
            **self.llm.get_usage_stats()
        }

    def reset(self):
        self.repl_env = None
        self.messages = []
        self.query = None
        self._iteration_count = 0
        self.llm.reset_stats()
