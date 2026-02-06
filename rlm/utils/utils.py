# -*- coding: utf-8 -*-
"""
Utility functions per RLM - Agency OS v16
==========================================

Cambio chiave rispetto a v15:
- I limiti di troncamento sono PROPORZIONALI al context window del Root LM
- Con qwen3-max (258k) → output fino a ~50k chars nei messaggi (vs 10k di prima)
- Con qwen-max (30k) → resta conservativo a ~8k chars
- Il troncamento è una SAFETY NET, non il meccanismo primario
- I dati completi restano SEMPRE nelle variabili REPL
"""

import re
from typing import List, Dict, Optional

# Import limiti dal config (con fallback)
try:
    from config import get_safe_context_limit, QWEN_MODEL_ROOT
    _DEFAULT_SAFE_TOKENS = get_safe_context_limit(QWEN_MODEL_ROOT)
except ImportError:
    _DEFAULT_SAFE_TOKENS = 200000  # Fallback per qwen3-max


def find_code_blocks(response: str) -> Optional[List[str]]:
    """Estrae blocchi di codice ```repl``` dalla risposta."""
    pattern = r'```repl\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)
    return matches if matches else None


def find_final_answer(response: str) -> Optional[tuple]:
    """Cerca FINAL() o FINAL_VAR() nella risposta."""
    
    # FINAL_VAR(nome_variabile)
    final_var_match = re.search(r'FINAL_VAR\(([^)]+)\)', response)
    if final_var_match:
        return ('FINAL_VAR', final_var_match.group(1))
    
    # FINAL(risposta) - gestisce contenuto multiriga
    final_match = re.search(r'FINAL\((.*)\)', response, re.DOTALL)
    if final_match:
        content = final_match.group(1).strip()
        # Rimuovi virgolette esterne se presenti
        if (content.startswith("'") and content.endswith("'")) or \
           (content.startswith('"') and content.endswith('"')):
            content = content[1:-1]
        # Gestisci f-string e triple quotes
        if content.startswith("f'''") and content.endswith("'''"):
            content = content[4:-3]
        elif content.startswith("f'") and content.endswith("'"):
            content = content[2:-1]
        elif content.startswith('f"') and content.endswith('"'):
            content = content[2:-1]
        elif content.startswith("'''") and content.endswith("'''"):
            content = content[3:-3]
        elif content.startswith('"""') and content.endswith('"""'):
            content = content[3:-3]
        return ('FINAL', content)
    
    return None


def check_for_final_answer(response: str, repl_env, logger) -> Optional[str]:
    """Controlla se la risposta contiene una risposta finale."""
    
    # Prima controlla se FINAL() è stato chiamato nel REPL
    if hasattr(repl_env, 'get_final_result') and repl_env.get_final_result():
        result = repl_env.get_final_result()
        repl_env.clear_final_result()
        return result
    
    result = find_final_answer(response)
    if result is None:
        return None
    
    answer_type, content = result
    
    if answer_type == 'FINAL':
        return content
    elif answer_type == 'FINAL_VAR':
        try:
            variable_name = content.strip().strip('"').strip("'").strip()
            
            if variable_name in repl_env.locals:
                return str(repl_env.locals[variable_name])
            elif variable_name in repl_env.globals:
                return str(repl_env.globals[variable_name])
            else:
                available_vars = [k for k in repl_env.locals.keys() if not k.startswith('_')]
                error_msg = f"Variabile '{variable_name}' non trovata. Disponibili: {available_vars}"
                logger.log_tool_execution("FINAL_VAR", error_msg)
                return None
        except Exception as e:
            logger.log_tool_execution("FINAL_VAR", f"Errore: {str(e)}")
            return None
    
    return None


def convert_context_for_repl(context):
    """Converte il context nel formato appropriato per il REPL."""
    if isinstance(context, dict):
        return context, None
    elif isinstance(context, str):
        return None, context
    elif isinstance(context, list):
        if len(context) > 0 and isinstance(context[0], dict):
            if "content" in context[0]:
                return [msg.get("content", "") for msg in context], None
            else:
                return context, None
        else:
            return context, None
    else:
        return context, None


def _get_max_result_chars(safe_tokens: int = None) -> int:
    """
    Calcola il limite di caratteri per singolo risultato REPL nei messaggi.
    
    Logica: ogni iterazione RLM aggiunge ~1 messaggio ai messaggi.
    Con 15 iterazioni max, ogni messaggio può occupare safe_tokens/20 token.
    1 token ≈ 4 chars.
    
    qwen3-max (safe ~206k tokens): ~41k chars per messaggio → generoso
    qwen-max (safe ~24k tokens):   ~4.8k chars per messaggio → stretto
    """
    if safe_tokens is None:
        safe_tokens = _DEFAULT_SAFE_TOKENS
    chars_per_message = (safe_tokens // 20) * 4
    # Minimo 5000, massimo 80000
    return max(5000, min(80000, chars_per_message))


def add_execution_result_to_messages(messages, code, result, max_length=None):
    """
    Aggiunge risultato esecuzione ai messaggi del Root LM.
    
    Il limite è adattivo al modello:
    - qwen3-max (258k context): ~40k chars per risultato
    - qwen-max (30k context): ~5k chars per risultato
    
    I dati completi restano SEMPRE nelle variabili REPL.
    """
    if max_length is None:
        max_length = _get_max_result_chars()
    
    if len(result) > max_length:
        # Mantieni inizio (più informativo) e coda (per contesto)
        head_size = int(max_length * 0.7)
        tail_size = int(max_length * 0.2)
        result = (
            result[:head_size] +
            f"\n\n... [TRONCATO nei messaggi: {len(result):,} chars totali]\n"
            f"... [I dati COMPLETI sono nelle variabili REPL]\n"
            f"... [Usa llm_query(variabile) per analisi completa]\n\n" +
            result[-tail_size:]
        )
    
    code_display = code[:8000] if len(code) > 8000 else code
    
    messages.append({
        "role": "user", 
        "content": f"Codice eseguito:\n```python\n{code_display}\n```\n\nOutput REPL:\n{result}"
    })
    return messages


def format_execution_result(stdout, stderr, locals_dict, max_stdout=None):
    """
    Formatta risultato esecuzione per i MESSAGGI del Root LM.
    
    Il limite stdout è adattivo al modello. I dati completi
    restano nelle variabili REPL.
    """
    if max_stdout is None:
        max_stdout = _get_max_result_chars()
    
    parts = []
    
    if stdout:
        if len(stdout) > max_stdout:
            head = int(max_stdout * 0.7)
            tail = int(max_stdout * 0.2)
            parts.append(stdout[:head])
            parts.append(
                f"\n... [OUTPUT TRONCATO nei messaggi: {len(stdout):,} chars totali]"
                f"\n... [Dati completi nelle variabili REPL — usa llm_query() per analizzarli]"
            )
            parts.append(stdout[-tail:])
        else:
            parts.append(stdout)
    
    if stderr:
        parts.append(f"STDERR: {stderr}")
    
    # Mostra variabili disponibili
    vars_info = []
    for k, v in locals_dict.items():
        if not k.startswith('_') and not callable(v):
            if isinstance(v, str):
                preview = f"str({len(v):,} chars)"
            elif isinstance(v, (list, dict)):
                preview = f"{type(v).__name__}({len(v)} items)"
            elif hasattr(v, 'shape'):
                preview = f"DataFrame{v.shape}"
            else:
                preview = type(v).__name__
            vars_info.append(f"{k}={preview}")
    
    if vars_info:
        parts.append(f"\nVariabili REPL disponibili: {vars_info[:20]}")
    
    return "\n".join(parts) or "Nessun output"


def execute_code(repl_env, code, repl_env_logger, logger):
    """Esegue codice nel REPL e restituisce risultato formattato."""
    try:
        result = repl_env.code_execution(code)
        formatted = format_execution_result(result.stdout, result.stderr, result.locals)
        
        repl_env_logger.log_execution(code, result.stdout, result.stderr, result.execution_time)
        repl_env_logger.display_last()
        
        log_preview = formatted[:800] + "..." if len(formatted) > 800 else formatted
        logger.log_tool_execution("CODE", log_preview)
        
        return formatted
    except Exception as e:
        error_msg = f"Errore esecuzione: {str(e)}"
        logger.log_tool_execution("CODE_ERROR", error_msg)
        return error_msg


def process_code_execution(response, messages, repl_env, repl_env_logger, logger):
    """Processa tutti i blocchi di codice nella risposta."""
    code_blocks = find_code_blocks(response)
    
    if code_blocks:
        for code in code_blocks:
            execution_result = execute_code(repl_env, code, repl_env_logger, logger)
            messages = add_execution_result_to_messages(messages, code, execution_result)
    
    return messages


def truncate_messages_if_needed(messages, max_tokens=None):
    """
    Safety net: gestione intelligente del contesto del Root LM.
    
    Strategia:
    1. Se pochi messaggi ma troppo lunghi → comprimi i singoli contenuti
    2. Se molti messaggi → mantieni system + primi 2 + ultimi 10, rimuovi il centro
    
    Con qwen3-max (258k) questo dovrebbe accadere raramente.
    Con qwen-max (30k) è più frequente.
    """
    if max_tokens is None:
        max_tokens = _DEFAULT_SAFE_TOKENS
    
    total_text = "".join(m.get("content", "") for m in messages)
    estimated_tokens = len(total_text) // 4
    
    if estimated_tokens <= max_tokens:
        return messages
    
    # Separa system prompt dal resto
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]
    
    if len(other_msgs) <= 12:
        # Pochi messaggi ma troppo lunghi → comprimi i contenuti più grandi
        # Calcola quanto dobbiamo tagliare
        target_chars = max_tokens * 4
        system_chars = sum(len(m.get("content", "")) for m in system_msgs)
        available_chars = target_chars - system_chars
        per_msg_limit = max(3000, available_chars // len(other_msgs))
        
        for msg in other_msgs:
            content = msg.get("content", "")
            if len(content) > per_msg_limit:
                head = int(per_msg_limit * 0.6)
                tail = int(per_msg_limit * 0.3)
                msg["content"] = (
                    content[:head] +
                    f"\n\n... [Compresso: {len(content):,} → {per_msg_limit:,} chars]"
                    f"\n... [Dati completi nelle variabili REPL]\n\n" +
                    content[-tail:]
                )
        return system_msgs + other_msgs
    
    # Molti messaggi → mantieni primi 2 e ultimi 10
    kept_start = other_msgs[:2]
    kept_end = other_msgs[-10:]
    removed_count = len(other_msgs) - 12
    
    summary = [{
        "role": "user",
        "content": (
            f"[... {removed_count} messaggi intermedi omessi per limiti contesto. "
            f"I dati completi sono nelle variabili REPL — "
            f"usa print() o llm_query() per accedervi ...]"
        )
    }]
    
    return system_msgs + kept_start + summary + kept_end
