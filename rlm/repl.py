# -*- coding: utf-8 -*-
"""
REPL Environment - Agency OS v15
Sub LM: qwen-plus (via config)
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
    """Sub-LLM per queries ricorsive nel REPL."""
    
    def __init__(self, model: str = None):
        self.model = model or QWEN_MODEL_SUB
        from rlm.utils.llm import OpenAIClient
        self.client = OpenAIClient(model=self.model)
    
    def completion(self, prompt, max_tokens: int = 32000) -> str:
        try:
            return self.client.completion(messages=prompt, max_tokens=max_tokens)
        except Exception as e:
            return f"Errore llm_query: {str(e)}"
    
    def cost_summary(self) -> dict:
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
    """Ambiente REPL per esecuzione codice Python con accesso a Sub-LLM e tools."""
    
    def __init__(
        self,
        recursive_model: str = None,
        context_json: Optional[dict | list] = None,
        context_str: Optional[str] = None,
        setup_code: str = None,
    ):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp(prefix="repl_env_")
        self._final_result = None
        
        # Sub-RLM
        self.sub_rlm: RLM = Sub_RLM(model=recursive_model)
        
        # Globals sicuri
        self.globals = {
            '__builtins__': {
                'print': print, 'len': len, 'range': range, 'str': str,
                'int': int, 'float': float, 'bool': bool, 'list': list,
                'dict': dict, 'tuple': tuple, 'set': set, 'type': type,
                'isinstance': isinstance, 'issubclass': issubclass,
                'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter,
                'sorted': sorted, 'reversed': reversed, 'min': min, 'max': max,
                'sum': sum, 'abs': abs, 'round': round, 'any': any, 'all': all,
                'open': open, 'repr': repr, 'hasattr': hasattr, 'getattr': getattr,
                'setattr': setattr, 'delattr': delattr, 'callable': callable,
                'chr': chr, 'ord': ord, 'hex': hex, 'oct': oct, 'bin': bin,
                'format': format, 'id': id, 'hash': hash, 'dir': dir,
                'vars': vars, 'iter': iter, 'next': next, 'slice': slice,
                'staticmethod': staticmethod, 'classmethod': classmethod,
                'property': property, 'super': super, 'object': object,
                '__import__': __import__, 'bytes': bytes, 'bytearray': bytearray,
                'memoryview': memoryview, 'complex': complex, 'frozenset': frozenset,
                'pow': pow, 'divmod': divmod,
                'True': True, 'False': False, 'None': None,
                # Exceptions
                'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
                'KeyError': KeyError, 'IndexError': IndexError, 'AttributeError': AttributeError,
                'FileNotFoundError': FileNotFoundError, 'OSError': OSError, 'IOError': IOError,
                'RuntimeError': RuntimeError, 'NameError': NameError, 'ImportError': ImportError,
                'StopIteration': StopIteration, 'ZeroDivisionError': ZeroDivisionError,
                'OverflowError': OverflowError, 'UnicodeError': UnicodeError,
                'UnicodeDecodeError': UnicodeDecodeError, 'UnicodeEncodeError': UnicodeEncodeError,
                # Blocked
                'input': None, 'eval': None, 'exec': None, 'compile': None,
                'globals': None, 'locals': None,
            }
        }
        self.locals = {}
        self._lock = threading.Lock()

        # Load context
        self.load_context(context_json, context_str)
        
        # llm_query function
        def llm_query(prompt: str) -> str:
            """Query al Sub-LLM."""
            return self.sub_rlm.completion(prompt)
        
        self.globals['llm_query'] = llm_query
        
        # FINAL functions
        def final_answer(value) -> str:
            """Salva come risposta finale."""
            result = str(value)
            self._final_result = result
            preview = result[:500] + "..." if len(result) > 500 else result
            print(f"[FINAL_RESULT]: {preview}")
            return result
        
        def final_var(variable_name) -> str:
            """Restituisce una variabile come risposta finale."""
            if not isinstance(variable_name, str):
                result = str(variable_name)
                self._final_result = result
                print(f"[FINAL_RESULT]: {result[:500]}")
                return result
            
            clean_name = variable_name.strip().strip('"').strip("'").strip()
            
            if clean_name in self.locals:
                result = str(self.locals[clean_name])
            elif clean_name in self.globals:
                result = str(self.globals[clean_name])
            elif len(variable_name) > 100:
                # Probabilmente è il contenuto stesso, non un nome variabile
                result = variable_name
            else:
                return f"Errore: Variabile '{clean_name}' non trovata"
            
            self._final_result = result
            preview = result[:500] + "..." if len(result) > 500 else result
            print(f"[FINAL_RESULT]: {preview}")
            return result
        
        self.globals['FINAL'] = final_answer
        self.globals['FINAL_VAR'] = final_var
        
        if setup_code:
            self.code_execution(setup_code)
    
    def get_final_result(self) -> Optional[str]:
        return self._final_result
    
    def clear_final_result(self):
        self._final_result = None
    
    def load_context(self, context_json=None, context_str=None):
        """Carica il context nel REPL come variabile `context`."""
        if context_json is not None:
            context_path = os.path.join(self.temp_dir, "context.json")
            with open(context_path, "w", encoding="utf-8") as f:
                json.dump(context_json, f, indent=2, ensure_ascii=False)
            self.code_execution(
                f"import json\n"
                f"with open(r'{context_path}', 'r', encoding='utf-8') as f:\n"
                f"    context = json.load(f)"
            )
        
        if context_str is not None:
            context_path = os.path.join(self.temp_dir, "context.txt")
            with open(context_path, "w", encoding="utf-8") as f:
                f.write(context_str)
            self.code_execution(
                f"with open(r'{context_path}', 'r', encoding='utf-8') as f:\n"
                f"    context = f.read()"
            )
    
    def inject_tools(self, tools_dict: dict):
        """Inietta funzioni esterne nel REPL (es. tools Qdrant)."""
        for name, func in tools_dict.items():
            self.globals[name] = func
    
    @contextmanager
    def _capture_output(self):
        """Cattura stdout/stderr in modo thread-safe."""
        with self._lock:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            try:
                sys.stdout = stdout_buffer
                sys.stderr = stderr_buffer
                yield stdout_buffer, stderr_buffer
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
    
    @contextmanager
    def _temp_working_directory(self):
        """Cambia temporaneamente la working directory."""
        old_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            yield
        finally:
            os.chdir(old_cwd)
    
    def code_execution(self, code) -> REPLResult:
        """Esecuzione codice notebook-style nel REPL."""
        start_time = time.time()
        
        with self._capture_output() as (stdout_buffer, stderr_buffer):
            with self._temp_working_directory():
                try:
                    # Separa import dal resto
                    lines = code.split('\n')
                    import_lines = []
                    other_lines = []
                    
                    for line in lines:
                        if line.startswith(('import ', 'from ')) and not line.startswith('#'):
                            import_lines.append(line)
                        else:
                            other_lines.append(line)
                    
                    if import_lines:
                        exec('\n'.join(import_lines), self.globals, self.globals)
                    
                    remaining = '\n'.join(other_lines)
                    if remaining.strip():
                        exec(remaining, self.globals, self.locals)
                    
                except Exception as e:
                    stderr_buffer.write(f"Errore: {str(e)}\n")
        
        execution_time = time.time() - start_time
        
        return REPLResult(
            stdout=stdout_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
            locals=dict(self.locals),
            execution_time=execution_time
        )
    
    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
