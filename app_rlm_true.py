# -*- coding: utf-8 -*-
"""
Agency OS v8.0 - TRUE RLM Integration
Usa il framework RLM reale con ragionamento ricorsivo

ARCHITETTURA:
- RLM Framework (dalla repo ufficiale)
- Qwen-max come backend LLM
- LocalREPL come ambiente di esecuzione
- Funzioni custom per accesso a Qdrant nel REPL
- Ragionamento ricorsivo con llm_query()
"""
import streamlit as st
import os
import sys
import time
import json
import datetime
from pathlib import Path

# Aggiungi cartella rlm al path
rlm_path = Path("./rlm")
if rlm_path.exists():
    sys.path.insert(0, str(rlm_path))

# --- CHECK RLM FRAMEWORK ---
RLM_FRAMEWORK_AVAILABLE = False
RLM_ERROR = None

try:
    from rlm import RLM
    from rlm.logger import RLMLogger
    RLM_FRAMEWORK_AVAILABLE = True
    print("✅ RLM Framework caricato")
except ImportError as e:
    RLM_ERROR = str(e)
    print(f"❌ RLM Framework non disponibile: {e}")

# Import client Qwen
try:
    from rlm_qwen_client import QwenRLMClient, create_qwen_client
    QWEN_CLIENT_AVAILABLE = True
except ImportError:
    QWEN_CLIENT_AVAILABLE = False
    print("❌ QwenRLMClient non disponibile")

# Import moduli locali
try:
    import personas
    PERSONAS_AVAILABLE = True
except ImportError:
    PERSONAS_AVAILABLE = False
    personas = None

# --- CONFIGURAZIONE ---
st.set_page_config(
    page_title="Agency OS v8.0 - True RLM",
    layout="wide",
    page_icon="🧠"
)

API_KEY = "sk-96a9773427c649d5a6af2a6842404c88"
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# Leggi il setup code per il REPL
REPL_SETUP_CODE = ""
setup_file = Path("./rlm_repl_setup.py")
if setup_file.exists():
    with open(setup_file, "r", encoding="utf-8") as f:
        REPL_SETUP_CODE = f.read()


# --- CUSTOM SYSTEM PROMPT ---
def get_agency_system_prompt(persona: str = "", active_client: str = None) -> str:
    """
    System prompt personalizzato per Agency OS.
    Estende il prompt RLM base con istruzioni specifiche per l'agenzia.
    """
    client_context = ""
    if active_client:
        client_context = f"""
CLIENTE ATTIVO: {active_client.upper()}
- Dai priorità ai dati di questo cliente
- Cerca in CLIENT_{active_client.upper()}, CHAT_{active_client.upper()}, DATA_{active_client.upper()}
- MA cerca anche in altri clienti per confronto e best practice
"""

    return f"""{persona}

=== AGENCY OS - SISTEMA DI INTELLIGENCE ===

Sei un assistente AI per un'agenzia di marketing digitale. Hai accesso a:

1. DATABASE MEMORIA (Qdrant):
   - Ricerche e studi (RESEARCH_ADS, RESEARCH_SOCIAL, RESEARCH_COPY, etc.)
   - Documenti clienti (CLIENT_*)
   - Chat e conversazioni passate (CHAT_*)
   - Report e dati (DATA_*)

2. FILE EXCEL/CSV per analisi dati

3. CAPACITÀ DI RAGIONAMENTO RICORSIVO:
   - Puoi chiamare llm_query() per analizzare porzioni di contesto
   - Puoi usare llm_query_batched() per query parallele
   - Puoi iterare sui dati e costruire risposte complesse

{client_context}

=== FUNZIONI DISPONIBILI NEL REPL ===

MEMORIA:
- search_memory(query, tag=None, top_k=7) → Ricerca semantica
- list_tags() → Mostra tutti i tag disponibili
- search_by_tag(tag, query=None) → Cerca per tag specifico
- get_document(filename) → Recupera documento completo

EXCEL/CSV:
- list_data_files() → Mostra file dati disponibili
- analyze_excel(filename) → Analizza struttura file
- excel_query(filename, operation, column, group_by=None) → Query specifiche

LLM RICORSIVO:
- llm_query(prompt) → Chiama LLM per analisi complesse
- llm_query_batched(prompts) → Query parallele

=== STRATEGIA DI RAGIONAMENTO ===

1. ESPLORA: Prima usa list_tags() e list_data_files() per capire cosa c'è
2. RACCOGLI: Cerca informazioni rilevanti con search_memory()
3. CROSS-REFERENCE: Confronta dati da fonti diverse
4. ANALIZZA: Usa llm_query() per analizzare grandi quantità di testo
5. SINTETIZZA: Combina tutto in una risposta strutturata

=== IMPORTANTE ===

- Fai SEMPRE ricerche nel database prima di rispondere
- Cita SEMPRE le fonti delle informazioni
- Se non trovi dati, dillo chiaramente
- Per domande complesse, usa ragionamento ricorsivo con llm_query()
"""


# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Agency OS v8.0")
    
    # Status
    if RLM_FRAMEWORK_AVAILABLE:
        st.success("RLM Framework: ✅ Attivo")
    else:
        st.error(f"RLM Framework: ❌ {RLM_ERROR}")
    
    st.divider()
    
    # Configurazione RLM
    st.subheader("Configurazione RLM")
    
    max_depth = st.slider(
        "Max Depth (ricorsione)",
        min_value=1,
        max_value=3,
        value=1,
        help="Profondità massima delle chiamate ricorsive"
    )
    
    max_iterations = st.slider(
        "Max Iterations",
        min_value=5,
        max_value=50,
        value=30,
        help="Numero massimo di iterazioni RLM"
    )
    
    verbose_mode = st.checkbox("Verbose Output", value=True)
    
    st.divider()
    
    # Cliente attivo
    st.subheader("Cliente Focus")
    active_client = st.text_input(
        "Cliente principale",
        help="L'AI darà priorità a questo cliente"
    )
    
    st.divider()
    
    # Specialista
    st.subheader("Specialista")
    if PERSONAS_AVAILABLE:
        available_roles = list(dict.fromkeys(personas.PERSONA_MAP.keys()))
    else:
        available_roles = ["General Analyst"]
    selected_mode = st.selectbox("Ruolo", available_roles)
    
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
        
        if st.button("Reset Stats"):
            st.session_state.total_cost = 0.0
            st.session_state.total_queries = 0
            st.session_state.history = []
            st.rerun()


# --- MAIN ---
st.title("🧠 Agency OS - True RLM")

if active_client:
    st.caption(f"Cliente: {active_client} | Ragionamento ricorsivo attivo")
else:
    st.caption("Ragionamento ricorsivo con accesso alla memoria dell'agenzia")

# History
if "history" not in st.session_state:
    st.session_state.history = []

# Mostra history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
prompt = st.chat_input("Chiedi qualsiasi cosa...")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state.total_queries += 1
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        response_container = st.empty()
        
        if RLM_FRAMEWORK_AVAILABLE:
            response_container.info("🧠 RLM: Avvio ragionamento ricorsivo...")
            
            try:
                # Prepara persona
                if PERSONAS_AVAILABLE:
                    persona = personas.PERSONA_MAP.get(selected_mode, "")
                else:
                    persona = "Sei un assistente professionale per marketing digitale."
                
                # System prompt personalizzato
                custom_system_prompt = get_agency_system_prompt(persona, active_client)
                
                # Crea directory logs se non esiste
                log_dir = Path("./logs")
                log_dir.mkdir(exist_ok=True)
                
                # Setup RLM logger
                logger = RLMLogger(log_dir=str(log_dir), file_name="agency_os")
                
                # Progress indicator
                with st.status("🧠 RLM in esecuzione...", expanded=verbose_mode) as status:
                    
                    status.write("Inizializzazione RLM...")
                    
                    # Crea istanza RLM con Qwen
                    rlm = RLM(
                        backend="openai",  # Usa OpenAI-compatible API
                        backend_kwargs={
                            "api_key": API_KEY,
                            "base_url": BASE_URL,
                            "model_name": "qwen-max",
                        },
                        environment="local",
                        environment_kwargs={},
                        max_depth=max_depth,
                        max_iterations=max_iterations,
                        custom_system_prompt=custom_system_prompt,
                        logger=logger,
                        verbose=verbose_mode,
                    )
                    
                    status.write("Esecuzione query...")
                    
                    # Costruisci context con setup code + prompt
                    full_context = f"""
{REPL_SETUP_CODE}

# ============================================================
# QUERY UTENTE
# ============================================================

user_query = \"\"\"{prompt}\"\"\"
print(f"Query ricevuta: {{user_query[:100]}}...")
"""
                    
                    start_time = time.time()
                    
                    # Esegui RLM completion
                    result = rlm.completion(
                        prompt=full_context,
                        root_prompt=prompt  # Passa il prompt originale
                    )
                    
                    elapsed = time.time() - start_time
                    
                    status.update(label="✅ Completato", state="complete")
                
                # Mostra risposta
                answer = result.response
                response_container.markdown(answer)
                
                # Mostra metriche
                usage = result.usage_summary
                
                st.divider()
                
                cols = st.columns(4)
                cols[0].metric("Tempo", f"{elapsed:.1f}s")
                cols[1].metric("Execution", f"{result.execution_time:.1f}s")
                
                # Calcola token totali
                total_input = sum(
                    m.total_input_tokens 
                    for m in usage.model_usage_summaries.values()
                )
                total_output = sum(
                    m.total_output_tokens 
                    for m in usage.model_usage_summaries.values()
                )
                total_calls = sum(
                    m.total_calls 
                    for m in usage.model_usage_summaries.values()
                )
                
                cols[2].metric("Token", f"{total_input + total_output:,}")
                cols[3].metric("LLM Calls", total_calls)
                
                # Calcola costo (approssimativo per Qwen)
                cost = (total_input / 1000 * 0.004) + (total_output / 1000 * 0.012)
                st.session_state.total_cost += cost
                
                st.caption(f"Costo stimato: ${cost:.4f}")
                
                # Log file
                if verbose_mode:
                    with st.expander("📋 Log File"):
                        st.caption(f"Log salvato in: {logger.log_file_path}")
                        try:
                            with open(logger.log_file_path, "r") as f:
                                log_content = f.read()
                            st.code(log_content, language="json")
                        except:
                            st.caption("Log non disponibile")
                
                st.session_state.history.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                import traceback
                response_container.error(f"Errore RLM: {e}")
                st.code(traceback.format_exc())
        
        else:
            # Fallback senza RLM
            response_container.warning("RLM Framework non disponibile. Usando modalità semplice.")
            
            try:
                from openai import OpenAI
                client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
                
                response = client.chat.completions.create(
                    model="qwen-max",
                    messages=[
                        {"role": "system", "content": "Sei un assistente per marketing digitale."},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                answer = response.choices[0].message.content
                response_container.markdown(answer)
                
                st.session_state.history.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                response_container.error(f"Errore: {e}")

st.divider()
st.caption("Agency OS v8.0 - True RLM | Ragionamento Ricorsivo | Qwen + Qdrant")
