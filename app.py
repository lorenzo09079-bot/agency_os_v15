# -*- coding: utf-8 -*-
"""
Agency OS v16.0 - Multi-Persona Collaboration
===============================================
ARCHITETTURA:
- TUTTI gli specialisti sono sempre disponibili
- Root LM decide autonomamente chi chiamare (uno o più)
- Sub LM riceve mega-prompt fresco ad ogni chiamata
- Anti-allucinazione a 3 livelli (prompt, REPL, tools)

Lancia con: streamlit run app.py
"""

import streamlit as st
import sys
import os
import time
import uuid
from pathlib import Path
from datetime import datetime

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
    QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME,
    ENCODER_MODEL, DATA_FILES_DIR,
    CHUNK_SIZE, CHUNK_OVERLAP,
)

# Import RLM
from rlm.rlm_repl import RLM_REPL
from rlm.utils.prompts import DEFAULT_QUERY, next_action_prompt, build_system_prompt
import rlm.utils.utils as utils

# --- PAGE CONFIG ---
st.set_page_config(page_title="Agency OS v16", layout="wide", page_icon="🧠")


# ============================================
# INGESTER LOCALE
# ============================================

def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    if ext == 'pdf':
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            return "[ERRORE: PyMuPDF non installato]"
    elif ext == 'docx':
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return "[ERRORE: python-docx non installato]"
    elif ext in ('xlsx', 'xls', 'csv'):
        try:
            import pandas as pd
            import io
            df = pd.read_csv(io.BytesIO(file_bytes)) if ext == 'csv' else pd.read_excel(io.BytesIO(file_bytes))
            return df.to_string(index=False)
        except ImportError:
            return "[ERRORE: pandas non installato]"
    elif ext in ('txt', 'md'):
        try:
            return file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return file_bytes.decode('latin-1')
    else:
        return f"[Formato .{ext} non supportato]"


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    words = text.split()
    if len(words) <= chunk_size:
        return [text] if text.strip() else []
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def ingest_file(file_bytes: bytes, filename: str, tag: str, doc_type: str) -> dict:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    from sentence_transformers import SentenceTransformer
    try:
        qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=30)
    except Exception as e:
        return {"success": False, "error": f"Connessione Qdrant fallita: {e}"}
    enc = SentenceTransformer(ENCODER_MODEL)
    tag = tag.strip().upper().replace(" ", "_")
    raw_text = extract_text(file_bytes, filename)
    if not raw_text or len(raw_text) < 10:
        return {"success": False, "error": "File vuoto o non leggibile"}
    chunks = chunk_text(raw_text)
    if not chunks:
        return {"success": False, "error": "Nessun chunk generato"}
    timestamp = datetime.now()
    points = []
    for i, chunk in enumerate(chunks):
        vector = enc.encode(chunk).tolist()
        points.append(qmodels.PointStruct(
            id=str(uuid.uuid4()), vector=vector,
            payload={"text": chunk, "filename": filename, "client_name": tag,
                     "doc_type": doc_type, "chunk_index": i,
                     "total_chunks": len(chunks), "date": timestamp.isoformat()}
        ))
    try:
        for batch_start in range(0, len(points), 100):
            qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points[batch_start:batch_start+100])
        return {"success": True, "filename": filename, "tag": tag, "chunks": len(chunks), "chars": len(raw_text)}
    except Exception as e:
        return {"success": False, "error": f"Upload Qdrant fallito: {e}"}


def save_data_file(file_bytes: bytes, filename: str):
    data_dir = Path(DATA_FILES_DIR)
    data_dir.mkdir(exist_ok=True)
    (data_dir / filename).write_bytes(file_bytes)


# ============================================
# TOOLS PER REPL
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
# ALL PERSONAS (caricati una volta)
# ============================================

def get_all_personas_prompts() -> dict:
    """Restituisce dict {persona_key: sub_lm_prompt} per TUTTI gli specialisti."""
    return {
        key: personas.get_sub_lm_prompt(key)
        for key in personas.list_personas()
    }


# ============================================
# CONTEXT BUILDER (LEAN)
# ============================================

def build_full_context(chat_history: list, active_client: str = None) -> str:
    """Costruisce il contesto con lo storico. Nessuna persona qui."""
    parts = []
    if active_client:
        parts.append(f"=== FOCUS CLIENTE: {active_client.upper()} ===")
        parts.append(f"Tag probabili: DATI_{active_client.upper()}_*, CLIENT_{active_client.upper()}")
        parts.append("")
    if chat_history and len(chat_history) > 1:
        parts.append("=== STORICO CONVERSAZIONE ===")
        parts.append("(Rispondi alla richiesta ATTUALE, usa lo storico come contesto)")
        parts.append("")
        for i, msg in enumerate(chat_history[:-1], 1):
            role = "UTENTE" if msg["role"] == "user" else "ASSISTENTE"
            content = msg["content"]
            if len(content) > 1500:
                content = content[:1500] + "... [troncato]"
            parts.append(f"[{i}. {role}]: {content}")
            parts.append("")
        parts.append("=== FINE STORICO ===\n")
    return "\n".join(parts) if parts else "Prima conversazione."


# ============================================
# RLM EXECUTION (MULTI-PERSONA)
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
    Esegue una query RLM con TUTTI gli specialisti disponibili.
    Il Root LM decide autonomamente chi chiamare.
    """
    start_time = time.time()
    model = model or QWEN_MODEL_ROOT
    recursive_model = recursive_model or QWEN_MODEL_SUB
    
    # Carica TUTTI i mega-prompt
    all_personas = get_all_personas_prompts()
    
    try:
        os.environ["OPENAI_API_KEY"] = QWEN_API_KEY
        os.environ["OPENAI_BASE_URL"] = QWEN_BASE_URL
        
        # Crea RLM con TUTTI gli specialisti
        rlm = RLM_REPL(
            model=model,
            recursive_model=recursive_model,
            max_iterations=max_iterations,
            enable_logging=show_logs,
            personas_prompts=all_personas,
        )
        
        # Contesto LEAN
        context = build_full_context(chat_history, active_client)
        
        # Setup (crea REPL con tutti gli ask_*)
        rlm.setup_context(context=context, query=query)
        
        # Inietta tools Qdrant
        if rlm.repl_env:
            rlm.repl_env.inject_tools(get_tools_for_injection())
        
        # Loop RLM
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
                rlm.messages.append({"role": "assistant", "content": response})
            
            final_answer = utils.check_for_final_answer(response, rlm.repl_env, rlm.logger)
            
            if final_answer:
                rlm.logger.log_final_response(final_answer)
                stats = rlm.llm.get_usage_stats()
                return {
                    "success": True,
                    "response": final_answer,
                    "time": time.time() - start_time,
                    "iterations": iteration + 1,
                    "model": model,
                    "cost": stats.get("cost_usd", 0)
                }
        
        # Max iterations: forza risposta
        rlm.messages.append(next_action_prompt(query, max_iterations, final_answer=True))
        final_response = rlm.llm.completion(rlm.messages)
        stats = rlm.llm.get_usage_stats()
        
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
            "error": str(e),
            "traceback": traceback.format_exc(),
            "time": time.time() - start_time,
        }


# ============================================
# SIDEBAR
# ============================================

with st.sidebar:
    st.title("🧠 Agency OS v16")
    
    # Cliente
    st.subheader("👤 Cliente")
    known_clients = ["Euroitalia", "Nike", "Test"]
    opts = ["— Tutti —"] + known_clients
    sel = st.selectbox("Focus", range(len(opts)), format_func=lambda i: opts[i])
    active_client = None if sel == 0 else opts[sel]
    
    st.divider()
    
    # Team specialisti (informativo, non selezione)
    st.subheader("🎭 Team Specialisti")
    st.caption("Il Root LM sceglie automaticamente chi consultare.")
    
    specialist_names = {
        "Ads Strategist": "📊 Ads Strategist",
        "Creative Copywriter": "✍️ Copywriter",
        "Blog Editor": "📝 Blog Editor",
        "Social Media Manager": "📱 SMM",
        "Data Scientist": "🔬 Data Scientist",
        "General Analyst": "🧠 General",
    }
    
    cols = st.columns(2)
    for i, (key, label) in enumerate(specialist_names.items()):
        cols[i % 2].markdown(f"<small>{label}</small>", unsafe_allow_html=True)
    
    st.caption("💡 Puoi chiedere uno specifico specialista nella query, es: *\"Come copywriter, scrivi...\"*")
    
    st.divider()
    
    # Upload & Ingest
    st.subheader("📤 Carica Documenti")
    uploaded_files = st.file_uploader(
        "File", type=["pdf", "txt", "docx", "xlsx", "xls", "csv", "md"],
        accept_multiple_files=True, label_visibility="collapsed"
    )
    tag = st.text_input("Tag", value=f"DATI_{active_client.upper()}" if active_client else "GENERALE")
    doc_type = st.selectbox("Tipo", ["Report Dati", "Strategia", "Ricerca", "Chat", "Meeting"])
    
    has_data_files = uploaded_files and any(f.name.lower().endswith(('.xlsx', '.xls', '.csv')) for f in uploaded_files)
    save_local = st.checkbox("Salva anche per analisi locale", value=True) if has_data_files else False
    
    if st.button("📤 Carica", use_container_width=True) and uploaded_files and tag:
        progress = st.progress(0)
        for i, f in enumerate(uploaded_files):
            try:
                f.seek(0)
                file_bytes = f.read()
                result = ingest_file(file_bytes, f.name, tag, doc_type)
                if result["success"]:
                    st.success(f"✅ {f.name} ({result['chunks']} chunks)")
                    if save_local and f.name.lower().endswith(('.xlsx', '.xls', '.csv')):
                        save_data_file(file_bytes, f.name)
                else:
                    st.error(f"❌ {f.name}: {result['error']}")
            except Exception as e:
                st.error(f"❌ {f.name}: {e}")
            progress.progress((i + 1) / len(uploaded_files))
    
    st.divider()
    
    # Impostazioni avanzate
    with st.expander("⚙️ Impostazioni"):
        root_model = st.selectbox("Root LM", ["qwen-max", "qwen-plus", "qwen-flash"], index=0)
        sub_model = st.selectbox("Sub LM", ["qwen-plus", "qwen-flash"], index=0)
        max_iter = st.slider("Max iterazioni", 3, 25, 15)
        show_logs = st.checkbox("Mostra log REPL", value=False)
    
    st.divider()
    
    # Stats
    if "total_cost" not in st.session_state:
        st.session_state.total_cost = 0.0
    col1, col2 = st.columns(2)
    n_queries = len([m for m in st.session_state.get("history", []) if m["role"] == "user"])
    col1.metric("Queries", n_queries)
    col2.metric("Costo", f"${st.session_state.total_cost:.4f}")
    
    if st.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.total_cost = 0.0
        st.rerun()


# ============================================
# MAIN
# ============================================

st.title("🧠 Agency OS v16")
st.caption(
    f"Focus: **{active_client or 'Tutti'}** | "
    f"Team: **6 specialisti** | "
    f"Root: {root_model} | Sub: {sub_model}"
)

if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Chiedi qualcosa...")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        container = st.empty()
        container.info("🔄 Elaborazione con RLM Multi-Persona...")
        
        with st.status("🧠 RLM in esecuzione...", expanded=show_logs) as status:
            status.write(f"Root: {root_model} | Sub: {sub_model} | Team: 6 specialisti")
            
            result = run_rlm(
                query=prompt,
                chat_history=st.session_state.history,
                active_client=active_client,
                model=root_model,
                recursive_model=sub_model,
                max_iterations=max_iter,
                show_logs=show_logs
            )
            
            if result["success"]:
                status.update(label=f"✅ {result['time']:.1f}s | {result.get('iterations', '?')} iter", state="complete")
            else:
                status.update(label="❌ Errore", state="error")
        
        if result["success"]:
            container.markdown(result["response"])
            cost = result.get("cost", 0)
            st.session_state.total_cost += cost
            st.caption(f"⏱️ {result['time']:.1f}s | 🔄 {result.get('iterations', '?')} iter | 💰 ${cost:.4f}")
            st.session_state.history.append({"role": "assistant", "content": result["response"]})
        else:
            container.error(f"Errore: {result.get('error', 'Sconosciuto')}")
            if show_logs and "traceback" in result:
                st.code(result["traceback"])

# Footer
st.divider()
qdrant_status = "✅" if tools.qdrant else "❌"
st.caption(f"Agency OS v16 Multi-Persona | Qdrant {qdrant_status} | {QDRANT_HOST}:{QDRANT_PORT}")
