# -*- coding: utf-8 -*-
"""
Utility functions per RLM - Agency OS v16
=========================================
CHANGELOG v16:
- Migliorata format_execution_result: stdout NON troncato
- add_execution_result_to_messages: limiti più generosi
- check_for_final_answer: supporto per FINAL() chiamato nel REPL
"""

import re
from typing import List, Dict, Optional


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


def add_execution_result_to_messages(messages, code, result, max_length=200000):
    """Aggiunge risultato esecuzione ai messaggi."""
    if len(result) > max_length:
        half = max_length // 2 - 100
        result = result[:half] + f"\n\n...[TRONCATO - {len(result) - max_length} chars omessi]...\n\n" + result[-half:]
    
    code_display = code[:15000] if len(code) > 15000 else code
    
    messages.append({
        "role": "user", 
        "content": f"Codice eseguito:\n```python\n{code_display}\n```\n\nOutput REPL:\n{result}"
    })
    return messages


def format_execution_result(stdout, stderr, locals_dict, truncate_var_preview=500):
    """Formatta risultato esecuzione. stdout NON troncato per preservare output Sub-LLM."""
    parts = []
    
    if stdout:
        parts.append(stdout)
    
    if stderr:
        parts.append(f"STDERR: {stderr}")
    
    # Mostra variabili disponibili (compatto)
    vars_info = []
    for k, v in locals_dict.items():
        if not k.startswith('_') and not callable(v):
            if isinstance(v, str):
                preview = f"str({len(v)} chars)"
            elif isinstance(v, (list, dict)):
                preview = f"{type(v).__name__}({len(v)} items)"
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


def truncate_messages_if_needed(messages, max_tokens=80000):
    """Tronca i messaggi più vecchi mantenendo system prompt e ultimi messaggi."""
    total_text = "".join(m.get("content", "") for m in messages)
    estimated_tokens = len(total_text) // 4
    
    if estimated_tokens <= max_tokens:
        return messages
    
    # Mantieni: system prompt (primo) + ultimi N messaggi
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]
    
    # Rimuovi dal centro, tieni primi 2 e ultimi 6
    if len(other_msgs) > 8:
        kept = other_msgs[:2] + other_msgs[-6:]
        return system_msgs + kept
    
    return messages
