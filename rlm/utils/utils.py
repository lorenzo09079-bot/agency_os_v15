# -*- coding: utf-8 -*-
"""
Utility functions for RLM REPL Client.
v14.1 - Limiti aumentati per risposte dettagliate
"""

import re
from typing import List, Dict, Optional, Tuple, Any


def find_code_blocks(text: str) -> Optional[List[str]]:
    """Trova blocchi ```repl``` nel testo."""
    pattern = r'```repl\s*\n(.*?)\n```'
    results = [match.group(1).strip() for match in re.finditer(pattern, text, re.DOTALL) if match.group(1).strip()]
    return results if results else None


def find_final_answer(text: str) -> Optional[Tuple[str, str]]:
    """Trova FINAL() o FINAL_VAR() nella risposta."""
    # FINAL_VAR con nome variabile
    for pattern in [r'FINAL_VAR\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)', 
                    r'FINAL_VAR\s*\(\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']\s*\)']:
        match = re.search(pattern, text)
        if match:
            return ('FINAL_VAR', match.group(1).strip())
    
    # FINAL con contenuto - pattern più permissivo per catturare tutto
    match = re.search(r'FINAL\s*\(\s*(.+?)\s*\)(?:\s*$|\s*\n|\s*```)', text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # Rimuovi quote esterne se presenti
        if (content.startswith('"') and content.endswith('"')) or \
           (content.startswith("'") and content.endswith("'")):
            content = content[1:-1]
        # Se sembra un nome variabile, trattalo come FINAL_VAR
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', content):
            return ('FINAL_VAR', content)
        return ('FINAL', content)
    
    return None


def check_for_final_answer(response: str, repl_env, logger) -> Optional[str]:
    """
    Estrae la risposta finale.
    
    PRIORITÀ:
    1. Se FINAL() è stato eseguito nel REPL, usa quel risultato (variabili espanse!)
    2. Altrimenti cerca FINAL() nel testo della risposta
    """
    # PRIMA: Controlla se FINAL() è stato eseguito nel REPL
    if repl_env and hasattr(repl_env, 'get_final_result'):
        final_from_repl = repl_env.get_final_result()
        if final_from_repl:
            logger.log_tool_execution("FINAL_FROM_REPL", f"Risultato REPL: {len(final_from_repl)} chars")
            repl_env.clear_final_result()  # Reset per prossima iterazione
            return final_from_repl
    
    # FALLBACK: Cerca FINAL() nel testo della risposta (per casi senza esecuzione)
    result = find_final_answer(response)
    if result is None:
        return None
    
    answer_type, content = result
    
    if answer_type == 'FINAL':
        final_content = content.strip()
        
        # Avvisa se sembra f-string non espansa
        if '{' in final_content and '}' in final_content:
            logger.log_tool_execution("FINAL_WARNING", 
                "Possibile f-string non espansa - controlla che FINAL sia stato eseguito nel REPL")
        
        # Avvisa se troppo generico
        generic_phrases = ["ho trovato un file", "il file contiene", "i dati mostrano"]
        generic_count = sum(1 for p in generic_phrases if p in final_content.lower())
        if generic_count >= 2 and len(final_content) < 500:
            logger.log_tool_execution("FINAL_WARNING", 
                f"Risposta potrebbe essere troppo generica ({generic_count} frasi vaghe)")
        
        return final_content
    
    elif answer_type == 'FINAL_VAR':
        if repl_env is None or not hasattr(repl_env, 'locals'):
            return "Errore: ambiente REPL non disponibile"
        
        variable_name = content.strip()
        
        # Cerca la variabile nel REPL
        if variable_name in repl_env.locals:
            value = repl_env.locals[variable_name]
            if not callable(value):
                return str(value)
        
        # Cerca alternative
        available_vars = [k for k, v in repl_env.locals.items() 
                        if not k.startswith('_') and not callable(v)]
        
        for keyword in ['final', 'answer', 'result', 'report', 'analysis', 'summary', 'risposta']:
            for var in available_vars:
                if keyword in var.lower():
                    value = repl_env.locals[var]
                    if isinstance(value, str) and len(value) > 50:
                        logger.log_tool_execution("FINAL_VAR_FALLBACK", f"Usando '{var}'")
                        return value
        
        # Ultima risorsa: stringa lunga
        for var in available_vars:
            value = repl_env.locals.get(var)
            if isinstance(value, str) and len(value) > 200:
                logger.log_tool_execution("FINAL_VAR_RESCUE", f"Usando '{var}' ({len(value)} chars)")
                return value
        
        return f"Variabile '{variable_name}' non trovata. Disponibili: {available_vars}"
    
    return None


def add_execution_result_to_messages(messages, code, result, max_length=200000):
    """
    Aggiunge risultato esecuzione ai messaggi.
    Limite aumentato a 200k caratteri per supportare risposte dettagliate.
    """
    if len(result) > max_length:
        half = max_length // 2 - 100
        result = result[:half] + "\n\n...[TRONCATO per limiti contesto - " + \
                 f"{len(result) - max_length} caratteri omessi]...\n\n" + result[-half:]
    
    # Codice limitato a 15k (dovrebbe bastare)
    code_display = code[:15000] if len(code) > 15000 else code
    
    messages.append({
        "role": "user", 
        "content": f"Codice eseguito:\n```python\n{code_display}\n```\n\nOutput REPL:\n{result}"
    })
    return messages


def format_execution_result(stdout, stderr, locals_dict, truncate_var_preview=500):
    """
    Formatta risultato esecuzione.
    stdout NON viene troncato - il modello deve vedere tutto per dare risposte complete.
    """
    parts = []
    
    if stdout:
        # NON troncare stdout - serve completo per analisi dettagliate
        parts.append(stdout)
    
    if stderr:
        parts.append(f"STDERR: {stderr}")
    
    # Mostra variabili disponibili (ma non il contenuto completo)
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
        parts.append(f"\nVariabili REPL: {vars_info[:20]}")
    
    return "\n".join(parts) or "Nessun output"


def execute_code(repl_env, code, repl_env_logger, logger):
    """Esegue codice nel REPL e restituisce risultato formattato."""
    try:
        result = repl_env.code_execution(code)
        formatted = format_execution_result(result.stdout, result.stderr, result.locals)
        
        repl_env_logger.log_execution(code, result.stdout, result.stderr, result.execution_time)
        repl_env_logger.display_last()
        
        # Log breve per console (ma il risultato completo va ai messaggi)
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
            result = execute_code(repl_env, code, repl_env_logger, logger)
            messages = add_execution_result_to_messages(messages, code, result)
    return messages


def convert_context_for_repl(context):
    """Converte il contesto nel formato appropriato per REPL."""
    if isinstance(context, dict):
        return context, None
    elif isinstance(context, str):
        return None, context
    elif isinstance(context, list):
        if context and isinstance(context[0], dict) and "content" in context[0]:
            return [msg.get("content", "") for msg in context], None
        return context, None
    return context, None


def truncate_messages_if_needed(messages, max_tokens=50000):
    """
    Tronca history se supera limite token.
    Limite aumentato a 50k token per supportare conversazioni più lunghe.
    """
    total = sum(len(m.get("content", "")) for m in messages) // 4
    if total <= max_tokens or len(messages) <= 7:
        return messages
    
    system = messages[0] if messages[0].get("role") == "system" else None
    recent = messages[-8:]  # Mantieni più messaggi recenti
    notice = {"role": "user", "content": "[...messaggi precedenti omessi per limiti contesto...]"}
    
    return ([system] if system else []) + [notice] + recent


def estimate_tokens(text: str) -> int:
    """Stima approssimativa dei token."""
    return len(text) // 4
