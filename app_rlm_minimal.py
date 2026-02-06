# -*- coding: utf-8 -*-
"""
Agency OS v14.0 - QWEN/DASHSCOPE
================================

Changelog da v13:
- MIGRATO: Da RouteWay.ai a DashScope International (Singapore)
- ROOT LM: qwen3-coder-plus (specializzato codice Python REPL)
- SUB LM: qwen-plus (analisi testi, ragionamento)
- API: OpenAI-compatible via DashScope
- COSTO: ~$3/mese per uso moderato (+ 1M token free per 90gg)

FILOSOFIA (invariata):
- Lo storico COMPLETO viene passato all'AI
- L'AI DECIDE cosa è rilevante in base alla richiesta attuale
- Non limitiamo artificialmente - lasciamo che l'intelligenza capisca
"""

import streamlit as st
import sys
import os
import time
import requests
from pathlib import Path

# Path setup
project_path = Path(__file__).parent
if str(project_path) not in sys.path:
    sys.path.insert(0, str(project_path))

# Import locali
import tools
import personas
from config import (
    QWEN_API_KEY, QWEN_BASE_URL, 
    QWEN_MODEL_ROOT, QWEN_MODEL_SUB,
    ACER_IP, ACER_PORT, API_KEY, BASE_URL
)

# Import RLM
from rlm.rlm_repl import RLM_REPL
from rlm.utils.prompts import DEFAULT_QUERY, next_action_prompt, build_system_prompt
import rlm.utils.utils as utils

# --- CONFIG ---
st.set_page_config(page_title="Agency OS v14.0", layout="wide", page_icon="🧠")

INGEST_URL = f"http://{ACER_IP}:{ACER_PORT}/ingest"

# Modelli disponibili (DashScope)
AVAILABLE_MODELS = {
    "Root LM (Codice)": [
        ("qwen3-coder-plus", "Qwen3 Coder Plus - Best per codice"),
        ("qwen-plus", "Qwen Plus - Generale bilanciato"),
        ("qwen-flash", "Qwen Flash - Veloce ed economico"),
        ("qwen-max", "Qwen Max - Più potente ma costoso")
    ],
    "Sub LM (Testi)": [
        ("qwen-plus", "Qwen Plus - Best per analisi"),
        ("qwen-flash", "Qwen Flash - Veloce ed economico"),
        ("qwen3-coder-plus", "Qwen3 Coder Plus - Se serve codice"),
    ]
}


# ============================================
# TOOLS
# ============================================

def get_tools_for_injection() -> dict:
    return {
        'list_all_tags': tools.list_all_tags,
        'find_related_tags': tools.find_related_tags,
        'list_files_by_tag': tools.list_files_by_tag,
        'get_file_content': tools.get_file_content,
        'get_database_stats': tools.get_database_stats,
        'search_semantic': tools.search_semantic,
        'search_by_keyword': tools.search_by_keyword,
        'search_memory': tools.search_memory,
    }


# ============================================
# CONTEXT BUILDER - STORICO COMPLETO
# ============================================

def build_full_context(chat_history: list, active_client: str = None) -> str:
    """
    Costruisce il contesto con TUTTO lo storico.
    L'AI decide cosa è rilevante.
    """
    parts = []
    
    # Cliente attivo (se specificato)
    if active_client:
        parts.append(f"=== FOCUS CLIENTE: {active_client.upper()} ===")
        parts.append(f"Tag probabili: DATI_{active_client.upper()}_*, CLIENTE_{active_client.upper()}")
        parts.append("")
    
    # STORICO COMPLETO (l'AI capisce cosa serve)
    if chat_history and len(chat_history) > 1:
        parts.append("=== STORICO CONVERSAZIONE COMPLETO ===")
        parts.append("(Usa questo per capire il contesto, ma rispondi alla richiesta ATTUALE)")
        parts.append("")
        
        for i, msg in enumerate(chat_history[:-1], 1):
            role = "UTENTE" if msg["role"] == "user" else "ASSISTENTE"
            content = msg["content"]
            
            if len(content) > 1000:
                content = content[:1000] + "... [troncato]"
            
            parts.append(f"[{i}. {role}]:")
            parts.append(content)
            parts.append("")
        
        parts.append("=== FINE STORICO ===")
        parts.append("")
        parts.append("IMPORTANTE: Rispondi alla richiesta ATTUALE dell'utente.")
    else:
        parts.append("Nessun messaggio precedente.")
    
    return "\n".join(parts)


# ============================================
# RLM EXECUTION
# ============================================

def run_rlm(
    query: str,
    chat_history: list,
    active_client: str = None,
    model: str = None,
    recursive_model: str = None,
    max_iterations: int = 15,
    show_logs: bool = False
) -> dict:
    """
    Esegue RLM con Qwen via DashScope.
    Root: qwen3-coder-plus (codice)
    Sub: qwen-plus (testi)
    """
    start_time = time.time()
    
    # Default ai modelli config
    model = model or QWEN_MODEL_ROOT
    recursive_model = recursive_model or QWEN_MODEL_SUB
    
    try:
        # Setta env vars per OpenAI client
        os.environ["OPENAI_API_KEY"] = QWEN_API_KEY
        os.environ["OPENAI_BASE_URL"] = QWEN_BASE_URL
        
        # 1. Crea RLM
        rlm = RLM_REPL(
            model=model,
            recursive_model=recursive_model,
            max_iterations=max_iterations,
            enable_logging=show_logs
        )
        
        # 2. Costruisci contesto COMPLETO
        context = build_full_context(chat_history, active_client)
        
        # 3. Setup
        rlm.setup_context(context=context, query=query)
        
        # 4. Inietta tools nel REPL
        if hasattr(rlm, 'repl_env') and rlm.repl_env:
            rlm.repl_env.inject_tools(get_tools_for_injection())
        
        if show_logs:
            print(f"[DEBUG] Root: {model}, Sub: {recursive_model}")
            print(f"[DEBUG] Tools: {list(get_tools_for_injection().keys())}")
        
        # 5. Loop RLM
        for iteration in range(max_iterations):
            try:
                response = rlm.llm.completion(
                    rlm.messages + [next_action_prompt(query, iteration)]
                )
            except Exception as e:
                if "length" in str(e).lower() or "token" in str(e).lower():
                    rlm.messages = utils.truncate_messages_if_needed(rlm.messages, 15000)
                    response = rlm.llm.completion(
                        rlm.messages + [next_action_prompt(query, iteration)]
                    )
                else:
                    raise
            
            code_blocks = utils.find_code_blocks(response)
            rlm.logger.log_model_response(response, has_tool_calls=code_blocks is not None)
            
            if code_blocks:
                rlm.messages = utils.process_code_execution(
                    response, rlm.messages, rlm.repl_env,
                    rlm.repl_env_logger, rlm.logger
                )
            else:
                if len(response) > 5000:
                    response = response[:5000] + "..."
                rlm.messages.append({"role": "assistant", "content": response})
            
            final_answer = utils.check_for_final_answer(response, rlm.repl_env, rlm.logger)
            
            if final_answer:
                rlm.logger.log_final_response(final_answer)
                
                # Calcola costo stimato
                stats = rlm.llm.get_usage_stats() if hasattr(rlm.llm, 'get_usage_stats') else {}
                
                return {
                    "success": True,
                    "response": final_answer,
                    "time": time.time() - start_time,
                    "iterations": iteration + 1,
                    "model": model,
                    "cost": stats.get("cost_usd", 0)
                }
        
        # Max iterations
        rlm.messages.append(next_action_prompt(query, max_iterations, final_answer=True))
        final_response = rlm.llm.completion(rlm.messages)
        
        stats = rlm.llm.get_usage_stats() if hasattr(rlm.llm, 'get_usage_stats') else {}
        
        return {
            "success": True,
            "response": final_response,
            "time": time.time() - start_time,
            "iterations": max_iterations,
            "model": model,
            "cost": stats.get("cost_usd", 0)
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "response": f"Errore: {str(e)}",
            "time": time.time() - start_time,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ============================================
# UI HELPERS
# ============================================

def get_available_clients() -> list:
    try:
        tags = tools.list_all_tags()
        clients = set()
        for tag in tags.keys():
            for prefix in ['CLIENT_', 'CLIENTE_', 'DATA_', 'DATI_', 'CHAT_']:
                if tag.startswith(prefix):
                    clients.add(tag[len(prefix):].split('_')[0])
                    break
        return sorted(clients)
    except:
        return []


def test_api_connection() -> tuple[bool, str]:
    """Testa connessione API Qwen."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)
        response = client.chat.completions.create(
            model="qwen-flash",  # Più economico per test
            messages=[{"role": "user", "content": "OK"}],
            max_tokens=5
        )
        return True, "OK"
    except Exception as e:
        return False, str(e)[:50]


# ============================================
# SIDEBAR
# ============================================

with st.sidebar:
    st.title("🧠 Agency OS v14.0")
    st.caption("Qwen + DashScope")
    
    st.divider()
    
    # Status
    col1, col2 = st.columns(2)
    col1.success("RLM ✅")
    
    try:
        stats = tools.get_database_stats()
        col2.success("DB ✅")
        st.metric("Documenti", stats.get("total_files", 0))
        st.metric("Tag", stats.get("total_tags", 0))
    except:
        col2.error("DB ❌")
    
    st.divider()
    
    # Modelli
    st.subheader("⚙️ Modelli")
    
    root_options = AVAILABLE_MODELS["Root LM (Codice)"]
    root_model = st.selectbox(
        "Root LM (Codice)",
        options=[m[0] for m in root_options],
        format_func=lambda x: next((m[1] for m in root_options if m[0] == x), x),
        index=0
    )
    
    sub_options = AVAILABLE_MODELS["Sub LM (Testi)"]
    recursive_model = st.selectbox(
        "Sub LM (Testi)",
        options=[m[0] for m in sub_options],
        format_func=lambda x: next((m[1] for m in sub_options if m[0] == x), x),
        index=0
    )
    
    max_iter = st.slider("Max Iterazioni", 5, 20, 10)
    show_logs = st.checkbox("🔍 Mostra Log", value=False)
    
    st.divider()
    
    # Focus cliente
    st.subheader("🎯 Focus")
    clients = get_available_clients()
    opts = ["(Tutti i clienti)"] + clients
    sel = st.selectbox("Cliente", range(len(opts)), format_func=lambda i: opts[i])
    active_client = None if sel == 0 else opts[sel]
    
    st.divider()
    
    # Upload
    st.subheader("📤 Upload")
    files = st.file_uploader(
        "File", 
        type=["pdf", "txt", "docx", "xlsx", "csv", "md"], 
        accept_multiple_files=True, 
        label_visibility="collapsed"
    )
    tag = st.text_input("Tag", value=f"DATI_{active_client.upper()}" if active_client else "GENERALE")
    dtype = st.selectbox("Tipo", ["Report Dati", "Strategia", "Ricerca", "Chat", "Meeting"])
    
    if st.button("📤 Carica", use_container_width=True) and files:
        for f in files:
            try:
                f.seek(0)
                res = requests.post(
                    INGEST_URL, 
                    files={"file": (f.name, f)}, 
                    data={"client_name": tag, "doc_type": dtype}, 
                    timeout=120
                )
                if res.status_code == 200:
                    st.success(f"✅ {f.name}")
                else:
                    st.error(f"❌ {f.name}")
            except Exception as e:
                st.error(f"❌ {f.name}: {e}")
    
    st.divider()
    
    # Session stats
    if "total_cost" not in st.session_state:
        st.session_state.total_cost = 0.0
    
    col1, col2 = st.columns(2)
    col1.metric("Queries", len([m for m in st.session_state.get("history", []) if m["role"] == "user"]))
    col2.metric("Costo", f"${st.session_state.total_cost:.4f}")
    
    if st.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.total_cost = 0.0
        st.rerun()


# ============================================
# MAIN AREA
# ============================================

st.title("🧠 Agency OS v14.0")
st.caption(f"Focus: **{active_client or 'Tutti'}** | Root: {root_model} | Sub: {recursive_model}")

# History
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
prompt = st.chat_input("Chiedi qualcosa...")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        container = st.empty()
        container.info("🔄 Elaborazione con RLM...")
        
        with st.status("🧠 RLM in esecuzione...", expanded=show_logs) as status:
            status.write(f"Root LM: {root_model}")
            status.write(f"Sub LM: {recursive_model}")
            
            result = run_rlm(
                query=prompt,
                chat_history=st.session_state.history,
                active_client=active_client,
                model=root_model,
                recursive_model=recursive_model,
                max_iterations=max_iter,
                show_logs=show_logs
            )
            
            if result["success"]:
                status.update(label=f"✅ Completato in {result['time']:.1f}s", state="complete")
            else:
                status.update(label="❌ Errore", state="error")
        
        if result["success"]:
            container.markdown(result["response"])
            
            # Stats
            cost = result.get("cost", 0)
            st.session_state.total_cost += cost
            
            st.caption(
                f"⏱️ {result['time']:.1f}s | "
                f"🔄 {result.get('iterations', '?')} iter | "
                f"💰 ${cost:.4f}"
            )
            
            st.session_state.history.append({"role": "assistant", "content": result["response"]})
        else:
            container.error(result.get("error", "Errore sconosciuto"))
            if show_logs and "traceback" in result:
                st.code(result["traceback"])

# Footer
st.divider()
st.caption("Agency OS v14.0 | RLM + Qwen + Qdrant | DashScope International")