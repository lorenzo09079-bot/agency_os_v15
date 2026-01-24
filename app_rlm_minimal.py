# -*- coding: utf-8 -*-
"""
Agency OS v9.0 - TRUE RLM MINIMAL Integration
============================================

Integrazione VERA di RLM Minimal con il tuo sistema Agency OS.

NOVITÀ v9.0:
- Usa config.py centralizzato per gli IP (modifica lì quando cambiano!)
- RLM Minimal per ragionamento ricorsivo
- Qwen-max come LLM principale
"""

import streamlit as st
import sys
import os
import json
import datetime
from pathlib import Path
from openai import OpenAI

# ============================================
# CONFIGURAZIONE CENTRALIZZATA
# ============================================
try:
    from config import (
        ASUS_IP, ACER_IP, QDRANT_URL, QDRANT_HOST, QDRANT_PORT,
        INGEST_URL, INGEST_ENDPOINT, COLLECTION_NAME,
        QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL_DEFAULT
    )
    print("✅ Config caricato da config.py")
except ImportError:
    # Fallback se config.py non esiste
    print("⚠️ config.py non trovato, uso valori di default")
    ASUS_IP = "192.168.1.6"
    ACER_IP = "192.168.1.8"
    QDRANT_URL = f"http://{ASUS_IP}:6333"
    QDRANT_HOST = ASUS_IP
    QDRANT_PORT = 6333
    INGEST_ENDPOINT = f"http://{ACER_IP}:5000/ingest"
    COLLECTION_NAME = "agenzia_memory"
    QWEN_API_KEY = "sk-96a9773427c649d5a6af2a6842404c88"
    QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL_DEFAULT = "qwen-max"

# Import moduli locali esistenti
import tools
import personas

# --- CHECK RLM MINIMAL ---
RLM_AVAILABLE = False
RLM_ERROR = None

try:
    from rlm.rlm_repl import RLM_REPL
    RLM_AVAILABLE = True
    print("✅ RLM Minimal caricato correttamente")
except ImportError as e:
    RLM_ERROR = str(e)
    print(f"❌ RLM Minimal non disponibile: {e}")

# --- CONFIGURAZIONE STREAMLIT ---
st.set_page_config(
    page_title="Agency OS v9.0 - RLM Minimal",
    layout="wide",
    page_icon="🧠"
)

# Client AI standard (per fallback)
client_ai = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)


# --- FUNZIONI HELPER PER RLM ---

def build_context_for_rlm(query: str, active_client: str = None) -> str:
    """
    Costruisce il contesto da passare a RLM.
    Include i risultati delle ricerche nel vector DB.
    """
    context_parts = []
    
    # 1. Informazioni sul cliente attivo
    if active_client:
        context_parts.append(f"=== CLIENTE ATTIVO: {active_client.upper()} ===")
        context_parts.append(f"Priorità ricerca: CLIENT_{active_client.upper()}, CHAT_{active_client.upper()}")
        context_parts.append("")
    
    # 2. Ricerca principale
    context_parts.append("=== RISULTATI RICERCA PRINCIPALE ===")
    
    # Prima cerca con filtro cliente se specificato
    if active_client:
        client_results = tools.search_memory(query, f"CLIENT_{active_client.upper()}")
        if "Nessun dato trovato" not in client_results:
            context_parts.append(f"[Dati cliente {active_client}]")
            context_parts.append(client_results)
        
        # Cerca anche nelle chat
        chat_results = tools.search_memory(query, f"CHAT_{active_client.upper()}")
        if "Nessun dato trovato" not in chat_results:
            context_parts.append(f"[Chat {active_client}]")
            context_parts.append(chat_results)
    
    # Ricerca globale
    global_results = tools.search_memory(query, None)
    context_parts.append("[Ricerca globale]")
    context_parts.append(global_results)
    
    # 3. Aggiungi istruzioni per RLM
    context_parts.append("")
    context_parts.append("=== ISTRUZIONI ===")
    context_parts.append("Usa il contesto sopra per rispondere alla query dell'utente.")
    context_parts.append("Se i dati non sono sufficienti, indica cosa manca.")
    context_parts.append("Cita sempre le fonti (nome file) quando usi informazioni dal contesto.")
    
    return "\n".join(context_parts)


def get_system_prompt_for_rlm(persona: str, active_client: str = None) -> str:
    """
    Costruisce un system prompt ottimizzato per RLM.
    """
    client_note = ""
    if active_client:
        client_note = f"\nCLIENTE FOCUS: {active_client.upper()} - dai priorità ai suoi dati ma confronta con altri."
    
    return f"""{persona}

=== AGENCY OS - SISTEMA RLM ===

Sei un AI strategist per un'agenzia di marketing. Hai accesso a:
- Database vettoriale con ricerche, documenti, chat passate
- Capacità di ragionamento ricorsivo tramite REPL
{client_note}

COME USARE IL REPL:
1. Esamina sempre `context` per vedere i dati disponibili
2. Usa `llm_query(prompt)` per analisi complesse su porzioni di contesto
3. Quando hai la risposta, usa FINAL(risposta) o FINAL_VAR(variabile)

IMPORTANTE:
- Cita sempre le fonti quando usi dati dal contesto
- Se mancano informazioni, dillo chiaramente
- Per domande complesse, decomponi in sub-analisi con llm_query()
"""


# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Agency OS v9.0")
    
    # Status RLM
    if RLM_AVAILABLE:
        st.success("RLM Minimal: ✅ Attivo")
    else:
        st.error(f"RLM Minimal: ❌ {RLM_ERROR}")
        st.info("Usa modalità Standard come fallback")
    
    # Status connessioni
    with st.expander("🔌 Stato Connessioni"):
        st.text(f"Qdrant (Asus): {ASUS_IP}")
        st.text(f"Ingest (Acer): {ACER_IP}")
        st.caption("Modifica config.py per cambiare IP")
    
    st.divider()
    
    # Modalità
    st.subheader("⚡ Modalità")
    
    if RLM_AVAILABLE:
        execution_mode = st.radio(
            "Motore AI",
            ["🚀 RLM Minimal (Ricorsivo)", "⚡ Standard (Veloce)"],
            help=(
                "RLM: Ragionamento ricorsivo multi-step\n"
                "Standard: Risposta single-pass"
            )
        )
        use_rlm = "RLM" in execution_mode
    else:
        st.warning("RLM non disponibile")
        use_rlm = False
    
    # Config RLM
    if use_rlm:
        with st.expander("🔧 Config RLM"):
            max_iterations = st.slider(
                "Max Iterazioni", 5, 20, 10,
                help="Numero massimo di cicli REPL"
            )
            show_logs = st.checkbox("Mostra Log", value=True)
            recursive_model = st.selectbox(
                "Modello Sub-LLM",
                ["qwen-plus", "qwen-turbo", "qwen-max"],
                help="Modello per le chiamate ricorsive (più economico = più veloce)"
            )
    else:
        max_iterations = 10
        show_logs = False
        recursive_model = "qwen-plus"
    
    st.divider()
    
    # Cliente focus
    st.subheader("🎯 Cliente Focus")
    active_client = st.text_input(
        "Cliente principale",
        help="L'AI darà priorità ai dati di questo cliente"
    )
    if active_client:
        st.info(f"Focus: {active_client.upper()}")
    
    st.divider()
    
    # Specialista
    st.subheader("🎭 Specialista")
    try:
        available_roles = list(personas.PERSONA_MAP.keys())
    except:
        available_roles = ["General Analyst"]
    selected_mode = st.selectbox("Ruolo", available_roles)
    
    st.divider()
    
    # Upload documenti
    st.subheader("📂 Carica Documenti")
    uploaded_files = st.file_uploader(
        "File",
        type=["pdf", "txt", "docx", "xlsx", "csv", "md"],
        accept_multiple_files=True
    )
    
    client_tag = st.text_input("Tag", value=f"CLIENT_{active_client.upper()}" if active_client else "GENERALE")
    doc_type = st.selectbox("Tipo", ["Strategia", "Ricerca", "Report", "Chat", "Meeting"])
    
    if st.button("📤 Carica", use_container_width=True):
        if uploaded_files:
            import requests
            progress = st.progress(0)
            for i, f in enumerate(uploaded_files):
                try:
                    f.seek(0)
                    files = {"file": (f.name, f, f.type)}
                    data = {"client_name": client_tag, "doc_type": doc_type}
                    requests.post(INGEST_ENDPOINT, files=files, data=data, timeout=120)
                except Exception as e:
                    st.error(f"{f.name}: {e}")
                progress.progress((i + 1) / len(uploaded_files))
            st.success(f"Caricati {len(uploaded_files)} file")
    
    st.divider()
    
    # Stats
    with st.expander("📊 Statistiche"):
        if "total_cost" not in st.session_state:
            st.session_state.total_cost = 0.0
        if "total_queries" not in st.session_state:
            st.session_state.total_queries = 0
        
        col1, col2 = st.columns(2)
        col1.metric("Query", st.session_state.total_queries)
        col2.metric("Costo", f"${st.session_state.total_cost:.3f}")
        
        if st.button("Reset", use_container_width=True):
            st.session_state.total_cost = 0.0
            st.session_state.total_queries = 0
            st.session_state.history = []
            st.rerun()


# --- MAIN ---
mode_label = "🚀 RLM" if use_rlm else "⚡ STD"
st.title(f"{mode_label} Agency OS • {selected_mode}")

if active_client:
    st.caption(f"Cliente focus: {active_client} | Ragionamento {'ricorsivo' if use_rlm else 'standard'}")

# History
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
prompt = st.chat_input(f"Chiedi a {selected_mode}...")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state.total_queries += 1
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        container = st.empty()
        
        # ==========================================
        # MODALITÀ RLM MINIMAL
        # ==========================================
        if use_rlm and RLM_AVAILABLE:
            container.info("🧠 RLM Minimal: Avvio ragionamento ricorsivo...")
            
            try:
                # 1. Costruisci contesto
                context = build_context_for_rlm(prompt, active_client)
                
                # 2. Prepara persona
                persona = personas.PERSONA_MAP.get(selected_mode, "Sei un assistente professionale.")
                
                # 3. Crea istanza RLM
                with st.status("🔄 RLM in esecuzione...", expanded=show_logs) as status:
                    
                    status.write("Inizializzazione RLM_REPL...")
                    
                    # Imposta variabili ambiente per RLM Minimal
                    os.environ["OPENAI_API_KEY"] = QWEN_API_KEY
                    os.environ["OPENAI_BASE_URL"] = QWEN_BASE_URL
                    
                    rlm = RLM_REPL(
                        model=QWEN_MODEL_DEFAULT,      # Root model
                        recursive_model=recursive_model,  # Sub-LLM model
                        max_iterations=max_iterations,
                        enable_logging=show_logs
                    )
                    
                    status.write(f"Context size: {len(context)} caratteri")
                    status.write("Esecuzione completion...")
                    
                    import time
                    start_time = time.time()
                    
                    result = rlm.completion(
                        context=context,
                        query=prompt
                    )
                    
                    elapsed = time.time() - start_time
                    
                    status.update(label=f"✅ Completato in {elapsed:.1f}s", state="complete")
                
                # Mostra risposta
                answer = result
                container.markdown(answer)
                
                # Metriche
                st.divider()
                cols = st.columns(3)
                cols[0].metric("Tempo", f"{elapsed:.1f}s")
                cols[1].metric("Iterazioni", f"≤{max_iterations}")
                
                estimated_cost = elapsed * 0.01
                st.session_state.total_cost += estimated_cost
                cols[2].metric("Costo ≈", f"${estimated_cost:.3f}")
                
                st.session_state.history.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                import traceback
                container.error(f"Errore RLM: {e}")
                st.code(traceback.format_exc())
                st.warning("Tentativo fallback a modalità standard...")
                use_rlm = False
        
        # ==========================================
        # MODALITÀ STANDARD (Fallback)
        # ==========================================
        if not use_rlm or not RLM_AVAILABLE:
            container.info("⚡ Elaborazione standard...")
            
            try:
                # Ricerca memoria
                suggested_filter = personas.FILTER_MAP.get(selected_mode, None)
                
                if active_client:
                    retrieved_data = tools.search_memory(prompt, f"CLIENT_{active_client.upper()}")
                    if "Nessun dato trovato" in retrieved_data:
                        retrieved_data = tools.search_memory(prompt, None)
                else:
                    retrieved_data = tools.search_memory(prompt, suggested_filter)
                    if "Nessun dato trovato" in retrieved_data:
                        retrieved_data = tools.search_memory(prompt, None)
                
                # Genera risposta
                persona = personas.PERSONA_MAP.get(selected_mode, "Sei un assistente utile.")
                
                final_prompt = f"""
{persona}

[QUERY UTENTE]
{prompt}

[DATI DALLA MEMORIA]
{retrieved_data}

[ISTRUZIONI]
- Rispondi in modo completo e professionale
- Cita le fonti se usi dati dalla memoria
- Se mancano informazioni, chiedi chiarimenti
"""
                
                response = client_ai.chat.completions.create(
                    model=QWEN_MODEL_DEFAULT,
                    messages=[{"role": "user", "content": final_prompt}],
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                
                # Metriche
                usage = response.usage
                cost = ((usage.prompt_tokens/1000)*0.004) + ((usage.completion_tokens/1000)*0.012)
                st.session_state.total_cost += cost
                
                container.markdown(answer)
                st.caption(f"📊 Token: {usage.total_tokens} | Costo: ${cost:.5f}")
                
                st.session_state.history.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                container.error(f"Errore: {e}")

# Footer
st.divider()
st.caption(f"Agency OS v9.0 - RLM Minimal | Qdrant: {ASUS_IP} | Ingest: {ACER_IP}")