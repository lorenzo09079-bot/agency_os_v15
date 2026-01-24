# -*- coding: utf-8 -*-
"""
Agency OS v7.0 - BRAIN MODE
Sistema di Intelligence con Cross-Reference Multi-Fonte

NOVITA v7.0:
- Brain Mode: ragionamento multi-fonte automatico
- Cross-reference tra clienti diversi
- Confronto automatico con best practice
- Piu iterazioni per risposte complete
- Analisi Excel migliorata
"""
import streamlit as st
import os
import sys
import requests
import json
import datetime
from pathlib import Path
from openai import OpenAI

# Setup paths
rlm_path = Path("./rlm")
if rlm_path.exists():
    sys.path.insert(0, str(rlm_path))

# Import moduli
import tools
import personas

# Import RLM + Excel
RLM_AVAILABLE = False
EXCEL_AVAILABLE = False
RLM_ERROR = None

try:
    from rlm_qwen_client import QwenClient
    from rlm_memory_tools import (
        CombinedToolsExecutor,
        get_rlm_tools_definitions
    )
    RLM_AVAILABLE = True
    
    try:
        from excel_analyzer import DATA_FILES_DIR
        EXCEL_AVAILABLE = True
    except ImportError:
        DATA_FILES_DIR = Path("./data_files")
        
except ImportError as e:
    RLM_ERROR = str(e)
    DATA_FILES_DIR = Path("./data_files")

DATA_FILES_DIR.mkdir(exist_ok=True)

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Agency OS v7.0 - Brain", layout="wide", page_icon="🧠")

API_KEY = "sk-96a9773427c649d5a6af2a6842404c88"
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
IP_ACER_INGEST = "http://192.168.1.6:5000/ingest"

client_ai = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# --- LOGGER ---
class RLMLogger:
    def __init__(self):
        self.logs = []
        self.start_time = None
    
    def start(self):
        self.logs = []
        self.start_time = datetime.datetime.now()
    
    def log(self, cat: str, msg: str, data: dict = None):
        elapsed = (datetime.datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        self.logs.append({"time": f"{elapsed:.2f}s", "cat": cat, "msg": msg, "data": data})
    
    def get_logs(self):
        return self.logs

if "rlm_logger" not in st.session_state:
    st.session_state.rlm_logger = RLMLogger()


# --- BRAIN MODE PROMPT ---
def get_brain_mode_prompt(persona: str, active_client: str = None) -> str:
    """
    Prompt di sistema per Brain Mode:
    - Cross-reference automatico
    - Ragionamento multi-fonte
    - Confronto tra clienti
    - Best practice sempre
    """
    
    client_context = ""
    if active_client:
        client_context = f"""
CLIENTE PRINCIPALE: {active_client.upper()}
- Dai priorita ai dati di {active_client.upper()}, ma NON limitarti solo a lui
- Cerca SEMPRE anche dati di altri clienti per confronto
- Usa le lezioni apprese da altri clienti per consigliare {active_client.upper()}
"""
    
    return f"""{persona}

╔══════════════════════════════════════════════════════════════╗
║                    🧠 BRAIN MODE ATTIVO 🧠                    ║
║         Sistema di Intelligence Multi-Fonte                  ║
╚══════════════════════════════════════════════════════════════╝

{client_context}

=== I TUOI STRUMENTI ===

RICERCA DOCUMENTI:
• search_memory(query, client_filter, top_k) - Cerca in documenti, chat, strategie
• multi_tag_search(query, tags, top_k) - Cerca in piu categorie insieme
• list_available_filters() - Vedi TUTTO quello che c'e nel database

ANALISI DATI EXCEL/CSV:
• list_data_files() - SEMPRE usalo PRIMA di analizzare dati
• get_file_info(filename) - Vedi struttura file (colonne, tipi)
• analyze_data(filename, group_by, sort_by, ...) - Analisi con aggregazioni
• calculate(filename, operation, column) - Calcoli (sum, mean, min, max)

=== COME DEVI RAGIONARE (OBBLIGATORIO) ===

Per OGNI domanda, segui SEMPRE questi step:

**STEP 1 - ESPLORA IL DATABASE**
Prima di qualsiasi altra cosa:
- Usa list_available_filters() per vedere TUTTI i tag/clienti disponibili
- Usa list_data_files() per vedere TUTTI i file Excel/CSV
- Questo ti da la mappa di tutto cio che sai

**STEP 2 - RACCOGLI INFORMAZIONI DAL CLIENTE PRINCIPALE**
Se c'e un cliente attivo o menzionato:
- Cerca in CLIENT_[nome], CHAT_[nome], DATA_[nome]
- Analizza i file Excel/CSV del cliente
- Recupera strategie, decisioni passate, performance

**STEP 3 - CROSS-REFERENCE CON ALTRI CLIENTI (CRITICO!)**
Questa e la parte piu importante:
- Cerca dati SIMILI da ALTRI clienti (stessa industry, stessi problemi)
- Confronta metriche: il cliente X ha CPA migliore? Perche?
- Cerca nelle CHAT di altri clienti: abbiamo risolto problemi simili?
- Cosa ha funzionato per altri che potrebbe funzionare qui?

**STEP 4 - CONSULTA LE BEST PRACTICE**
SEMPRE cerca in:
- RESEARCH_ADS per strategie advertising
- RESEARCH_SOCIAL per social media
- RESEARCH_COPY per copywriting
- RESEARCH_BLOG, RESEARCH_SEO, etc.
- Confronta quello che fa il cliente con le best practice

**STEP 5 - SINTETIZZA E RAGIONA**
Prima di rispondere, ragiona esplicitamente:
- "I dati mostrano che..."
- "Rispetto agli altri clienti..."
- "Le best practice suggeriscono..."
- "Quindi raccomando..."

=== REGOLE FONDAMENTALI ===

1. FAI MOLTE RICERCHE: Minimo 4-5 tool calls per domande complesse
   - Non fermarti alla prima ricerca!
   - Se non trovi con un filtro, prova senza filtro
   - Se cerchi un cliente, cerca ANCHE altri clienti per confronto

2. PER FILE EXCEL/CSV:
   - SEMPRE list_data_files() prima
   - SEMPRE get_file_info() per vedere le colonne esatte
   - Usa i NOMI COLONNE ESATTI dal file, non inventarli
   - Se una query fallisce, prova un approccio diverso

3. CROSS-REFERENCE E OBBLIGATORIO:
   - MAI rispondere basandoti su un solo cliente/fonte
   - SEMPRE confrontare con altri dati disponibili
   - SEMPRE menzionare da dove vengono le informazioni

4. CITA LE FONTI:
   - "Secondo [documento]..."
   - "I dati di [cliente] mostrano..."
   - "Nelle chat con [cliente] avevamo discusso..."

5. AMMETTI I LIMITI:
   - Se non trovi dati sufficienti, dillo
   - Se i dati sono incompleti, segnalalo
   - Suggerisci quali dati servirebbero

=== ESEMPI DI RAGIONAMENTO ===

DOMANDA: "Come migliorare le ads di Nike?"

TUO PROCESSO MENTALE:
1. list_available_filters() → Vedo: CLIENT_NIKE, CLIENT_ADIDAS, CLIENT_PUMA, RESEARCH_ADS...
2. list_data_files() → Vedo: nike_report.csv, adidas_q3.xlsx...
3. search_memory("performance ads", "CLIENT_NIKE") → Trovo dati Nike
4. get_file_info("nike_report.csv") → Vedo colonne: Campaign, Spend, CPA, ROAS
5. analyze_data("nike_report.csv", group_by="Campaign", sort_by="CPA") → CPA per campagna
6. search_memory("performance ads", "CLIENT_ADIDAS") → Confronto con Adidas
7. analyze_data("adidas_q3.xlsx"...) → CPA Adidas
8. search_memory("ottimizzazione CPA", "RESEARCH_ADS") → Best practice
9. search_memory("cosa ha funzionato", "CHAT_ADIDAS") → Lezioni da Adidas

RISPOSTA:
"Analizzando i dati di Nike e confrontandoli con gli altri clienti e le best practice:

**Situazione Nike:**
- CPA medio: €15 (da nike_report.csv)
- Campagna migliore: Brand Awareness (CPA €10)
- Campagna peggiore: Retargeting (CPA €22)

**Confronto con altri clienti:**
- Adidas ha CPA medio di €8 (adidas_q3.xlsx)
- Nelle chat con Adidas avevamo notato che [insight]

**Best practice (da RESEARCH_ADS):**
- Il benchmark CPA per questo settore e €10-12
- Le ricerche suggeriscono di [strategia]

**Raccomandazioni:**
1. [Azione specifica basata sui dati]
2. [Azione basata su cosa ha funzionato per Adidas]
3. [Azione basata sulle best practice]"

=== RICORDA ===

Tu sei un CERVELLO che ha accesso a TUTTA la conoscenza dell'agenzia.
Non sei limitato a un solo cliente o una sola fonte.
Il tuo valore sta nel CONNETTERE informazioni da fonti diverse.
Piu connessioni fai, migliore e la risposta.

Ora inizia!
"""


# --- FUNZIONI RLM ---
def init_rlm_client():
    if not RLM_AVAILABLE:
        return None
    return QwenClient(api_key=API_KEY, base_url=BASE_URL, model_name="qwen-max")


def execute_rlm_with_tools(
    prompt: str,
    system_prompt: str,
    tools_executor,
    max_iterations: int = 10,
    logger = None
) -> dict:
    if logger:
        logger.start()
        logger.log("START", "Brain Mode attivato")
    
    client = init_rlm_client()
    if not client:
        return {"response": "RLM non disponibile", "error": True}
    
    tools_defs = get_rlm_tools_definitions()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    iterations = 0
    tools_used = []
    tool_details = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    while iterations < max_iterations:
        iterations += 1
        
        if logger:
            logger.log("ITER", f"Iterazione {iterations}/{max_iterations}")
        
        result = client.completion(messages=messages, tools=tools_defs, temperature=0.7)
        
        if result.get("usage"):
            for k in total_usage:
                total_usage[k] += result["usage"].get(k, 0)
        
        if not result.get("tool_calls"):
            if logger:
                logger.log("END", f"Completato dopo {iterations} iterazioni")
            return {
                "response": result["response"],
                "iterations": iterations,
                "tools_used": tools_used,
                "tool_details": tool_details,
                "usage": total_usage,
                "error": False
            }
        
        # Log partial response if any
        if result.get("response") and logger:
            logger.log("THINK", result["response"][:100] + "...")
        
        assistant_msg = {
            "role": "assistant",
            "content": result["response"] or "",
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": tc["function"]}
                for tc in result["tool_calls"]
            ]
        }
        messages.append(assistant_msg)
        
        for tc in result["tool_calls"]:
            tool_name = tc["function"]["name"]
            tools_used.append(tool_name)
            
            try:
                args = json.loads(tc["function"]["arguments"])
            except:
                args = {"raw": tc["function"]["arguments"]}
            
            if logger:
                # Log piu descrittivo
                if tool_name == "search_memory":
                    desc = f"Cerca: '{args.get('query', '')[:30]}' in {args.get('client_filter', 'tutto')}"
                elif tool_name == "list_data_files":
                    desc = "Elenca file dati"
                elif tool_name == "get_file_info":
                    desc = f"Info file: {args.get('filename', '')}"
                elif tool_name == "analyze_data":
                    desc = f"Analizza: {args.get('filename', '')} (group: {args.get('group_by', '-')})"
                elif tool_name == "calculate":
                    desc = f"Calcola {args.get('operation', '')} di {args.get('column', '')}"
                else:
                    desc = str(args)[:50]
                logger.log("TOOL", f"{tool_name}: {desc}")
            
            tool_result = tools_executor.execute_from_tool_call(tc)
            
            if logger:
                # Conta risultati se ricerca
                if "Trovati:" in tool_result:
                    count = tool_result.split("Trovati:")[1].split()[0] if "Trovati:" in tool_result else "?"
                    logger.log("FOUND", f"{count} risultati")
                elif "ERRORE" in tool_result:
                    logger.log("ERROR", tool_result[:100])
                else:
                    logger.log("OK", f"Dati ricevuti ({len(tool_result)} chars)")
            
            tool_details.append({
                "iteration": iterations,
                "tool": tool_name,
                "arguments": args,
                "result": tool_result
            })
            
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result
            })
    
    # Max iterations - chiedi sintesi finale
    if logger:
        logger.log("MAX", f"Raggiunto limite {max_iterations} iterazioni")
    
    messages.append({
        "role": "user", 
        "content": (
            "Hai raccolto molte informazioni. Ora fornisci una risposta COMPLETA e BEN STRUTTURATA. "
            "Includi: 1) Sintesi dei dati trovati, 2) Confronti tra fonti, 3) Raccomandazioni concrete. "
            "Cita sempre le fonti."
        )
    })
    
    final_result = client.completion(messages=messages, temperature=0.7)
    
    if final_result.get("usage"):
        for k in total_usage:
            total_usage[k] += final_result["usage"].get(k, 0)
    
    return {
        "response": final_result["response"],
        "iterations": iterations,
        "tools_used": tools_used,
        "tool_details": tool_details,
        "usage": total_usage,
        "error": False
    }


# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Agency OS v7.0")
    st.caption("Brain Mode - Intelligence Multi-Fonte")
    
    st.divider()
    
    # Modalita
    st.subheader("Motore AI")
    if RLM_AVAILABLE:
        execution_mode = st.radio(
            "Modalita",
            ["Standard", "🧠 Brain Mode"],
            index=1,
            help="Brain Mode fa cross-reference automatico tra tutte le fonti"
        )
        use_rlm = "Brain" in execution_mode
    else:
        use_rlm = False
        st.warning("RLM non disponibile")
    
    if use_rlm:
        with st.expander("Config Brain Mode"):
            max_iterations = st.slider(
                "Max Iterazioni", 5, 20, 12,
                help="Piu iterazioni = analisi piu approfondita"
            )
            show_logs = st.checkbox("Mostra Processo Mentale", True)
            show_details = st.checkbox("Mostra Dettagli Tool", False)
    else:
        max_iterations = 5
        show_logs = False
        show_details = False
    
    st.divider()
    
    # Cliente focus
    st.subheader("Cliente Focus")
    active_client = st.text_input(
        "Cliente principale",
        help="L'AI dara priorita a questo cliente ma cerchera anche altri per confronto"
    )
    if active_client:
        st.info(f"Focus: {active_client.upper()}\n+ Cross-ref con altri clienti")
    
    st.divider()
    
    # Specialista
    st.subheader("Specialista")
    available_roles = list(dict.fromkeys(personas.PERSONA_MAP.keys()))
    selected_mode = st.selectbox("Ruolo", available_roles)
    
    st.divider()
    
    # === UPLOAD ===
    st.subheader("Carica Documenti")
    
    uploaded_files = st.file_uploader(
        "File", 
        type=["pdf", "txt", "docx", "xlsx", "xls", "csv", "md"],
        accept_multiple_files=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        tag_type = st.selectbox("Tipo", ["RESEARCH_", "CLIENT_", "CHAT_", "DATA_"])
    with col2:
        tag_suffix = st.text_input("Nome", value=active_client.upper() if active_client else "")
    
    full_tag = f"{tag_type}{tag_suffix.upper()}" if tag_suffix else tag_type
    
    doc_type = st.selectbox("Tipo Doc", ["Ricerca", "Strategia", "Report Dati", "Meeting", "Chat"])
    
    has_data = uploaded_files and any(f.name.endswith(('.xlsx', '.xls', '.csv')) for f in uploaded_files)
    save_for_analysis = st.checkbox("Salva per analisi dati", value=has_data) if has_data else False
    
    if st.button("📤 Carica", use_container_width=True):
        if uploaded_files and tag_suffix:
            progress = st.progress(0)
            
            for i, f in enumerate(uploaded_files):
                try:
                    f.seek(0)
                    content = f.read()
                    f.seek(0)
                    
                    # Indicizzazione semantica
                    files = {"file": (f.name, f, f.type)}
                    data = {"client_name": full_tag, "doc_type": doc_type}
                    
                    try:
                        res = requests.post(IP_ACER_INGEST, files=files, data=data, timeout=120)
                    except:
                        pass
                    
                    # Salva per analisi Excel
                    if save_for_analysis and f.name.endswith(('.xlsx', '.xls', '.csv')):
                        save_path = DATA_FILES_DIR / f.name
                        if save_path.exists():
                            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                            save_path = DATA_FILES_DIR / f"{save_path.stem}_{ts}{save_path.suffix}"
                        with open(save_path, 'wb') as out:
                            out.write(content)
                    
                except Exception as e:
                    st.error(f"{f.name}: {e}")
                
                progress.progress((i + 1) / len(uploaded_files))
            
            st.success(f"Caricati come {full_tag}")
        else:
            st.warning("Inserisci nome tag")
    
    st.divider()
    
    # File dati
    with st.expander("📊 File Dati Disponibili"):
        files = list(DATA_FILES_DIR.glob("*.xlsx")) + list(DATA_FILES_DIR.glob("*.csv"))
        if files:
            for f in files:
                st.text(f"• {f.name}")
        else:
            st.caption("Nessun file")
    
    st.divider()
    
    # Salva chat
    st.subheader("Salva Chat")
    chat_name = st.text_input("Nome chat", active_client if active_client else "")
    
    if st.button("💾 Salva", use_container_width=True):
        if "history" in st.session_state and st.session_state.history and chat_name:
            try:
                text = f"CHAT: {chat_name}\n{datetime.datetime.now()}\n\n"
                for m in st.session_state.history:
                    text += f"[{'USER' if m['role']=='user' else 'AI'}]:\n{m['content']}\n\n---\n\n"
                
                tag = f"CHAT_{chat_name.upper().replace(' ', '_')}"
                files = {"file": (f"chat_{chat_name}.txt", text.encode(), "text/plain")}
                requests.post(IP_ACER_INGEST, files=files, data={"client_name": tag, "doc_type": "Chat"}, timeout=60)
                st.success(f"Salvata: {tag}")
            except Exception as e:
                st.error(str(e))
    
    st.divider()
    
    # Stats
    with st.expander("📈 Statistiche"):
        if "total_cost" not in st.session_state:
            st.session_state.total_cost = 0.0
        if "total_queries" not in st.session_state:
            st.session_state.total_queries = 0
        
        c1, c2 = st.columns(2)
        c1.metric("Query", st.session_state.total_queries)
        c2.metric("Costo", f"${st.session_state.total_cost:.3f}")
        
        if st.button("Reset", use_container_width=True):
            st.session_state.total_cost = 0.0
            st.session_state.total_queries = 0
            st.session_state.history = []
            st.rerun()


# --- MAIN ---
st.title(f"🧠 Agency OS - {selected_mode}")
if active_client:
    st.caption(f"Focus: {active_client} | + Cross-reference automatico con altri clienti e ricerche")
elif use_rlm:
    st.caption("Brain Mode: Cross-reference multi-fonte attivo")

if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Chiedi qualsiasi cosa...")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state.total_queries += 1
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        container = st.empty()
        
        if use_rlm and RLM_AVAILABLE:
            container.info("🧠 Brain Mode: Analisi multi-fonte in corso...")
            
            try:
                persona = personas.PERSONA_MAP.get(selected_mode, "Sei un assistente professionale.")
                system_prompt = get_brain_mode_prompt(persona, active_client)
                
                logger = st.session_state.rlm_logger
                tools_executor = CombinedToolsExecutor()
                
                # Processo con spinner dettagliato
                with st.status("🧠 Ragionamento in corso...", expanded=show_logs) as status:
                    result = execute_rlm_with_tools(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        tools_executor=tools_executor,
                        max_iterations=max_iterations,
                        logger=logger
                    )
                    
                    # Mostra log durante elaborazione
                    if show_logs:
                        for log in logger.get_logs():
                            icon = {
                                "START": "🟢", "ITER": "🔄", "TOOL": "🔧",
                                "FOUND": "📊", "OK": "✅", "ERROR": "❌",
                                "THINK": "💭", "MAX": "⚠️", "END": "🏁"
                            }.get(log["cat"], "📝")
                            status.write(f"{icon} `{log['time']}` **{log['cat']}**: {log['msg']}")
                    
                    status.update(label="✅ Analisi completata", state="complete")
                
                if result.get("error"):
                    raise Exception(result.get("response"))
                
                answer = result["response"]
                container.markdown(answer)
                
                # Metriche
                usage = result.get("usage", {})
                iterations = result.get("iterations", 0)
                tools_used = result.get("tools_used", [])
                
                if usage:
                    cost = (usage.get("prompt_tokens", 0) / 1000 * 0.004) + \
                           (usage.get("completion_tokens", 0) / 1000 * 0.012)
                    st.session_state.total_cost += cost
                    
                    st.divider()
                    cols = st.columns(5)
                    cols[0].metric("Iterazioni", iterations)
                    cols[1].metric("Ricerche", len([t for t in tools_used if 'search' in t]))
                    cols[2].metric("Analisi", len([t for t in tools_used if t in ['analyze_data', 'calculate', 'get_file_info']]))
                    cols[3].metric("Token", f"{usage.get('total_tokens', 0):,}")
                    cols[4].metric("Costo", f"${cost:.4f}")
                
                # Dettagli tool (opzionale)
                if show_details and result.get("tool_details"):
                    with st.expander("🔍 Dettagli Ricerche"):
                        for i, d in enumerate(result["tool_details"], 1):
                            st.markdown(f"**{i}. {d['tool']}**")
                            st.json(d['arguments'])
                            if len(d['result']) < 2000:
                                st.text(d['result'])
                            else:
                                st.text(d['result'][:2000] + "\n... (troncato)")
                            st.divider()
                
                st.session_state.history.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                container.error(f"Errore: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        # Standard mode
        else:
            container.info("Elaborazione...")
            try:
                data = tools.search_memory(prompt, None)
                persona = personas.PERSONA_MAP.get(selected_mode, "")
                
                response = client_ai.chat.completions.create(
                    model="qwen-max",
                    messages=[{"role": "user", "content": f"{persona}\n\nDomanda: {prompt}\n\nDati:\n{data}"}],
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                container.markdown(answer)
                
                st.session_state.history.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                container.error(str(e))

st.divider()
st.caption("Agency OS v7.0 - Brain Mode | Cross-Reference Intelligence | Qwen + Qdrant")
