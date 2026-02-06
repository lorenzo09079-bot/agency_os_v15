# -*- coding: utf-8 -*-
"""
REPL Environment for RLM - Agency OS v14
Usa qwen-plus come Sub LM di default
"""

import sys
import io
import threading
import json
import tempfile
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from rlm import RLM

# Import config
try:
    from config import QWEN_MODEL_SUB
except ImportError:
    QWEN_MODEL_SUB = "qwen-plus"


class Sub_RLM(RLM):
    """Sub-LLM per ambiente REPL. Usa qwen-plus per default."""
    
    def __init__(self, model: str = None):
        self.model = model or QWEN_MODEL_SUB
        
        from rlm.utils.llm import OpenAIClient
        self.client = OpenAIClient(model=self.model)
    
    def completion(self, prompt, max_tokens: int = 32000) -> str:
        """
        Esegue completion con max_tokens alto per risposte lunghe.
        Il Sub-LLM può produrre analisi dettagliate senza limiti.
        """
        try:
            return self.client.completion(messages=prompt, max_tokens=max_tokens)
        except Exception as e:
            return f"Error making LLM query: {str(e)}"
    
    def cost_summary(self) -> dict[str, float]:
        return self.client.get_usage_stats()
    
    def reset(self):
        self.client.reset_stats()


@dataclass
class REPLResult:
    stdout: str
    stderr: str
    locals: dict
    execution_time: float

    def __init__(self, stdout: str, stderr: str, locals: dict, execution_time: float = None):
        self.stdout = stdout
        self.stderr = stderr
        self.locals = locals
        self.execution_time = execution_time


class REPLEnv:
    def __init__(
        self,
        recursive_model: str = None,
        context_json: Optional[dict | list] = None,
        context_str: Optional[str] = None,
        setup_code: str = None,
    ):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp(prefix="repl_env_")
        
        # Sub-RLM usa qwen-plus di default
        self.sub_rlm: RLM = Sub_RLM(model=recursive_model or QWEN_MODEL_SUB)
        
        # Builtins sicuri
        self.globals = {
            '__builtins__': {
                'print': print, 'len': len, 'str': str, 'int': int, 'float': float,
                'list': list, 'dict': dict, 'set': set, 'tuple': tuple, 'bool': bool,
                'type': type, 'isinstance': isinstance, 'enumerate': enumerate,
                'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted,
                'min': min, 'max': max, 'sum': sum, 'abs': abs, 'round': round,
                'chr': chr, 'ord': ord, 'hex': hex, 'bin': bin, 'oct': oct,
                'repr': repr, 'ascii': ascii, 'format': format,
                '__import__': __import__, 'open': open,
                'any': any, 'all': all, 'hasattr': hasattr, 'getattr': getattr,
                'setattr': setattr, 'delattr': delattr, 'dir': dir, 'vars': vars,
                'range': range, 'reversed': reversed, 'slice': slice,
                'iter': iter, 'next': next, 'pow': pow, 'divmod': divmod,
                'complex': complex, 'bytes': bytes, 'bytearray': bytearray,
                'hash': hash, 'id': id, 'callable': callable,
                'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
                'KeyError': KeyError, 'IndexError': IndexError, 'AttributeError': AttributeError,
                'FileNotFoundError': FileNotFoundError, 'RuntimeError': RuntimeError,
                'StopIteration': StopIteration,
                'input': None, 'eval': None, 'exec': None, 'compile': None,
            }
        }
        self.locals = {}
        self._lock = threading.Lock()

        self.load_context(context_json, context_str)
        
        # Funzione llm_query
        def llm_query(prompt: str) -> str:
            return self.sub_rlm.completion(prompt)
        
        self.globals['llm_query'] = llm_query
        
        # Variabile per catturare il risultato di FINAL
        self._final_result = None
        
        # FINAL functions - salvano il risultato in _final_result
        def final_answer(value) -> str:
            """Marca la risposta finale. Il valore viene salvato e restituito."""
            result = str(value)
            self._final_result = result  # Salva per recupero esterno
            print(f"[FINAL_RESULT]: {result[:500]}..." if len(result) > 500 else f"[FINAL_RESULT]: {result}")
            return result
        
        def final_var(variable_name) -> str:
            """Restituisce una variabile come risposta finale."""
            if not isinstance(variable_name, str):
                result = str(variable_name)
                self._final_result = result
                print(f"[FINAL_RESULT]: {result[:500]}..." if len(result) > 500 else f"[FINAL_RESULT]: {result}")
                return result
            
            clean_name = variable_name.strip().strip('"').strip("'").strip()
            
            if clean_name in self.locals:
                result = str(self.locals[clean_name])
                self._final_result = result
                print(f"[FINAL_RESULT]: {result[:500]}..." if len(result) > 500 else f"[FINAL_RESULT]: {result}")
                return result
            elif clean_name in self.globals:
                result = str(self.globals[clean_name])
                self._final_result = result
                print(f"[FINAL_RESULT]: {result[:500]}..." if len(result) > 500 else f"[FINAL_RESULT]: {result}")
                return result
            
            if len(variable_name) > 100:
                self._final_result = variable_name
                print(f"[FINAL_RESULT]: {variable_name[:500]}...")
                return variable_name
            
            return f"Error: Variable '{clean_name}' not found"
        
        self.globals['FINAL'] = final_answer
        self.globals['FINAL_VAR'] = final_var
        
        if setup_code:
            self.code_execution(setup_code)
    
    def get_final_result(self) -> Optional[str]:
        """Restituisce il risultato di FINAL() se è stato chiamato."""
        return self._final_result
    
    def clear_final_result(self):
        """Resetta il risultato finale."""
        self._final_result = None
    
    def load_context(self, context_json=None, context_str=None):
        if context_json is not None:
            context_path = os.path.join(self.temp_dir, "context.json")
            with open(context_path, "w", encoding="utf-8") as f:
                json.dump(context_json, f, indent=2, ensure_ascii=False)
            self.code_execution(f"import json\nwith open(r'{context_path}', 'r', encoding='utf-8') as f:\n    context = json.load(f)")
        
        if context_str is not None:
            context_path = os.path.join(self.temp_dir, "context.txt")
            with open(context_path, "w", encoding="utf-8") as f:
                f.write(context_str)
            self.code_execution(f"with open(r'{context_path}', 'r', encoding='utf-8') as f:\n    context = f.read()")
    
    def inject_tools(self, tools_dict: dict):
        """Inietta tools esterni nel REPL."""
        for name, func in tools_dict.items():
            self.globals[name] = func
            self.locals[name] = func
    
    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    @contextmanager
    def _capture_output(self):
        with self._lock:
            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout_buffer, stderr_buffer = io.StringIO(), io.StringIO()
            try:
                sys.stdout, sys.stderr = stdout_buffer, stderr_buffer
                yield stdout_buffer, stderr_buffer
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
    
    @contextmanager
    def _temp_working_directory(self):
        old_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            yield
        finally:
            os.chdir(old_cwd)
    
    def code_execution(self, code) -> REPLResult:
        start_time = time.time()
        with self._capture_output() as (stdout_buffer, stderr_buffer):
            with self._temp_working_directory():
                try:
                    lines = code.split('\n')
                    import_lines = [l for l in lines if l.strip().startswith(('import ', 'from ')) and not l.strip().startswith('#')]
                    other_lines = [l for l in lines if not (l.strip().startswith(('import ', 'from ')) and not l.strip().startswith('#'))]
                    
                    if import_lines:
                        exec('\n'.join(import_lines), self.globals, self.globals)
                    
                    if other_lines:
                        combined = {**self.globals, **self.locals}
                        exec('\n'.join(other_lines), combined, combined)
                        for k, v in combined.items():
                            if k not in self.globals:
                                self.locals[k] = v
                    
                    stdout_content = stdout_buffer.getvalue()
                    stderr_content = stderr_buffer.getvalue()
                except Exception as e:
                    stderr_content = stderr_buffer.getvalue() + str(e)
                    stdout_content = stdout_buffer.getvalue()
        
        return REPLResult(stdout_content, stderr_content, self.locals.copy(), time.time() - start_time)
