# -*- coding: utf-8 -*-
"""
REPL Environment - Agency OS v16 (Multi-Persona)
=================================================
ARCHITETTURA MULTI-PERSONA:
- Ogni specialista ha la sua funzione nel REPL: ask_ads_strategist(), ask_copywriter(), etc.
- Ogni chiamata inietta: ANTI-ALLUCINAZIONE + MEGA-PROMPT specifico + DATI
- Root LM decide AUTONOMAMENTE chi chiamare in base alla query
- llm_query() resta come generico (senza persona specifica)
- validate_content() per verificare file prima dell'analisi
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
from typing import Optional, Dict

from rlm import RLM

try:
    from config import QWEN_MODEL_SUB
except ImportError:
    QWEN_MODEL_SUB = "qwen-plus"


_ANTI_HALLUCINATION_PREFIX = """ISTRUZIONE CRITICA: Basa la tua analisi ESCLUSIVAMENTE sui dati forniti nel testo qui sotto.
- Se il testo contiene "non trovato", "ERRORE:", o è vuoto → rispondi SOLO: "ERRORE: Nessun dato disponibile per l'analisi."
- NON inventare dati, metriche, statistiche o informazioni non presenti nel testo.
- Se i dati sono insufficienti, dì chiaramente cosa manca.
- Quando integri con conoscenza generale, etichetta esplicitamente: [CONOSCENZA GENERALE: ...]

"""

# Mapping persona_key → nome funzione nel REPL
_FUNCTION_NAMES = {
    "Ads Strategist": "ask_ads_strategist",
    "Creative Copywriter": "ask_copywriter",
    "Blog Editor": "ask_blog_editor",
    "Social Media Manager": "ask_smm",
    "Data Scientist": "ask_data_scientist",
    "General Analyst": "ask_analyst",
}


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


def _check_error_signals(prompt: str) -> Optional[str]:
    """Controlla se il prompt contiene segnali di errore."""
    error_signals = ["non trovato nel database", "ERRORE:", "File '' non trovato"]
    for signal in error_signals:
        if signal.lower() in prompt.lower()[:500]:
            return (
                "ERRORE: Il contenuto indica che il file non è stato trovato. "
                "Non è possibile analizzare dati inesistenti. "
                "Verifica il nome del file con list_files_by_tag()."
            )
    if len(prompt) < 150:
        return (
            f"ATTENZIONE: Testo troppo breve ({len(prompt)} chars). "
            "Potrebbe essere un errore. Verifica il contenuto del file."
        )
    return None


class REPLEnv:
    """
    Ambiente REPL Multi-Persona con Sub-LLM + Anti-Allucinazione.
    
    Il Root LM ha accesso a funzioni specialista nel REPL:
    - ask_ads_strategist(dati)  → analisi con prompt Ads Strategist completo
    - ask_copywriter(dati)      → analisi con prompt Creative Copywriter completo
    - ask_blog_editor(dati)     → analisi con prompt Blog Editor completo
    - ask_smm(dati)             → analisi con prompt Social Media Manager
    - ask_data_scientist(dati)  → analisi con prompt Data Scientist
    - llm_query(dati)           → Sub-LM generico (anti-allucinazione, no persona)
    - llm_query_raw(dati)       → Sub-LM senza prefix (sintesi finali)
    - validate_content(content, filename) → verifica validità file
    """
    
    def __init__(
        self,
        recursive_model: str = None,
        context_json: Optional[dict | list] = None,
        context_str: Optional[str] = None,
        personas_prompts: Dict[str, str] = None,
        setup_code: str = None,
    ):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp(prefix="repl_env_")
        self._final_result = None
        
        # Sub-RLM
        self.sub_rlm: RLM = Sub_RLM(model=recursive_model)
        
        # Personas: dict di {persona_key: mega_prompt_completo}
        self._personas_prompts = personas_prompts or {}
        
        # Pre-build prefix per ogni persona
        self._persona_prefixes: Dict[str, str] = {}
        for key, prompt in self._personas_prompts.items():
            self._persona_prefixes[key] = (
                _ANTI_HALLUCINATION_PREFIX +
                "=== IL TUO RUOLO E KNOWLEDGE BASE ===\n\n" +
                prompt +
                "\n\n=== DATI DA ANALIZZARE ===\n\n"
            )
        
        # Prefix generico
        self._generic_prefix = _ANTI_HALLUCINATION_PREFIX + "DATI DA ANALIZZARE:\n\n"
        
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
                'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
                'KeyError': KeyError, 'IndexError': IndexError, 'AttributeError': AttributeError,
                'FileNotFoundError': FileNotFoundError, 'OSError': OSError, 'IOError': IOError,
                'RuntimeError': RuntimeError, 'NameError': NameError, 'ImportError': ImportError,
                'StopIteration': StopIteration, 'ZeroDivisionError': ZeroDivisionError,
                'OverflowError': OverflowError, 'UnicodeError': UnicodeError,
                'UnicodeDecodeError': UnicodeDecodeError, 'UnicodeEncodeError': UnicodeEncodeError,
                'input': None, 'eval': None, 'exec': None, 'compile': None,
                'globals': None, 'locals': None,
            }
        }
        self.locals = {}
        self._lock = threading.Lock()

        # Load context
        self.load_context(context_json, context_str)
        
        # ============================================================
        # REGISTRA FUNZIONI SPECIALISTA
        # ============================================================
        
        available_specialists = []
        
        for persona_key, prefix in self._persona_prefixes.items():
            func_name = _FUNCTION_NAMES.get(
                persona_key,
                f"ask_{persona_key.lower().replace(' ', '_')}"
            )
            
            # Closure factory per catturare prefix correttamente
            def _make_fn(p_key, p_prefix, f_name):
                def persona_query(prompt: str) -> str:
                    error = _check_error_signals(prompt)
                    if error:
                        return error
                    return self.sub_rlm.completion(p_prefix + prompt)
                persona_query.__name__ = f_name
                persona_query.__doc__ = f"Query al Sub-LLM come {p_key}."
                return persona_query
            
            fn = _make_fn(persona_key, prefix, func_name)
            self.globals[func_name] = fn
            available_specialists.append(f"- {func_name}(dati) → {persona_key}")
        
        self._available_specialists_str = "\n".join(available_specialists)
        
        # llm_query generico
        def llm_query(prompt: str) -> str:
            """Query al Sub-LLM generico (anti-allucinazione, no persona specifica)."""
            error = _check_error_signals(prompt)
            if error:
                return error
            return self.sub_rlm.completion(self._generic_prefix + prompt)
        
        def llm_query_raw(prompt: str) -> str:
            """Query al Sub-LLM SENZA prefix. Per sintesi su dati già validati."""
            return self.sub_rlm.completion(prompt)
        
        def validate_content(content: str, filename: str = "") -> bool:
            """Verifica se get_file_content() ha restituito dati validi."""
            if not content or len(content) < 100:
                print(f"⚠️ CONTENUTO NON VALIDO: '{filename}' — solo {len(content) if content else 0} chars")
                return False
            for indicator in ["ERRORE:", "non trovato", "non disponibile"]:
                if indicator.lower() in content[:200].lower():
                    print(f"⚠️ FILE NON TROVATO: '{filename}' — {content[:150]}")
                    return False
            print(f"✅ FILE VALIDO: '{filename}' — {len(content)} chars")
            return True
        
        self.globals['llm_query'] = llm_query
        self.globals['llm_query_raw'] = llm_query_raw
        self.globals['validate_content'] = validate_content
        
        # FINAL functions
        def final_answer(value) -> str:
            result = str(value)
            self._final_result = result
            print(f"[FINAL_RESULT]: {result[:500]}{'...' if len(result)>500 else ''}")
            return result
        
        def final_var(variable_name) -> str:
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
                result = variable_name
            else:
                return f"Errore: Variabile '{clean_name}' non trovata"
            self._final_result = result
            print(f"[FINAL_RESULT]: {result[:500]}{'...' if len(result)>500 else ''}")
            return result
        
        self.globals['FINAL'] = final_answer
        self.globals['FINAL_VAR'] = final_var
        
        if setup_code:
            self.code_execution(setup_code)
    
    @property
    def available_specialists(self) -> str:
        return self._available_specialists_str
    
    def get_final_result(self) -> Optional[str]:
        return self._final_result
    
    def clear_final_result(self):
        self._final_result = None
    
    def load_context(self, context_json=None, context_str=None):
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
        for name, func in tools_dict.items():
            self.globals[name] = func
    
    @contextmanager
    def _capture_output(self):
        with self._lock:
            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
            try:
                sys.stdout, sys.stderr = stdout_buf, stderr_buf
                yield stdout_buf, stderr_buf
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
        with self._capture_output() as (stdout_buf, stderr_buf):
            with self._temp_working_directory():
                try:
                    lines = code.split('\n')
                    import_lines = [l for l in lines if l.startswith(('import ', 'from ')) and not l.startswith('#')]
                    other_lines = [l for l in lines if not (l.startswith(('import ', 'from ')) and not l.startswith('#'))]
                    if import_lines:
                        exec('\n'.join(import_lines), self.globals, self.globals)
                    remaining = '\n'.join(other_lines)
                    if remaining.strip():
                        exec(remaining, self.globals, self.locals)
                except Exception as e:
                    stderr_buf.write(f"Errore: {str(e)}\n")
        
        return REPLResult(
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
            locals=dict(self.locals),
            execution_time=time.time() - start_time
        )
    
    def __del__(self):
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
