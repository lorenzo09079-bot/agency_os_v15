import streamlit as st
import os
import requests
import json
import datetime
from openai import OpenAI
import tools
import personas  # Importa i tuoi Mega-Prompt

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Agency OS v4.0", layout="wide")

API_KEY = "sk-96a9773427c649d5a6af2a6842404c88"
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# IP DELL'ACER (WORKER)
IP_ACER_INGEST = "http://192.168.1.6:5000/ingest"

client_ai = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# --- SIDEBAR: CONTROLLI & INGESTIONE ---
with st.sidebar:
    st.title("🎛️ Agency OS")
    st.caption("Protocollo 'Red Pill' Attivo")
    
    # 1. SELETTORE PERSONA
    st.subheader("🎭 Attiva Specialista")
    
    try:
        available_roles = list(personas.PERSONA_MAP.keys())
        index_default = 0
        if "General Analyst" in available_roles:
            index_default = available_roles.index("General Analyst")
    except AttributeError:
        available_roles = ["General Analyst"]
        index_default = 0
        st.error("⚠️ Errore lettura personas.py")

    selected_mode = st.selectbox("Chi deve eseguire il task?", available_roles, index=index_default)
    
    st.info(f"🧠 Modalità attiva: **{selected_mode}**")
    st.divider()
    
    # 2. CARICAMENTO DOCUMENTI (BULK ENABLED)
    st.subheader("📂 Ingestione Massiva")
    st.caption("Trascina qui più file contemporaneamente.")
    
    uploaded_files = st.file_uploader(
        "Seleziona file (PDF, Word, Excel, TXT...)", 
        type=["pdf", "txt", "docx", "xlsx", "csv", "md"],
        accept_multiple_files=True
    )
    
    client_tag = st.text_input("Tag Cliente/Argomento (es. RESEARCH_ADS)", value="Generale")
    doc_type = st.selectbox("Tipo Doc", ["Strategia", "Paper Ricerca", "Meeting", "Report Tecnico", "Chat History", "System Docs"])
    
    if st.button("Manda al Cluster (Acer)"):
        if uploaded_files:
            total_files = len(uploaded_files)
            progress_bar = st.progress(0)
            status_area = st.empty()
            success_count = 0
            
            status_area.text(f"🚀 Inizio caricamento di {total_files} file...")
            
            for i, file_obj in enumerate(uploaded_files):
                try:
                    current_name = file_obj.name
                    status_area.text(f"⏳ Processando ({i+1}/{total_files}): {current_name}...")
                    
                    file_obj.seek(0) # Reset puntatore
                    
                    files = {"file": (current_name, file_obj, file_obj.type)}
                    data = {"client_name": client_tag, "doc_type": doc_type}
                    
                    # Timeout 120s per file
                    res = requests.post(IP_ACER_INGEST, files=files, data=data, timeout=120)
                    
                    if res.status_code == 200:
                        success_count += 1
                    else:
                        st.error(f"❌ Errore su {current_name}: {res.text}")
                        
                except Exception as e:
                    st.error(f"❌ Errore critico su {current_name}: {e}")
                
                progress_bar.progress((i + 1) / total_files)
            
            status_area.text("✅ Operazione completata.")
            if success_count == total_files:
                st.success(f"Tutti i {success_count} file indicizzati!")
            else:
                st.warning(f"Caricamento finito: {success_count}/{total_files} riusciti.")
        else:
            st.warning("Nessun file selezionato.")

    st.divider()

    # 3. SALVATAGGIO CHAT (NUOVO SISTEMA DINAMICO)
    st.subheader("💾 Memoria Conversazione")
    
    # Input per definire il contesto (es. "Nike" o "System")
    chat_topic = st.text_input("Nome Progetto (es. Nike, System)", value="Generale")
    
    if st.button("Salva Chat in Memoria"):
        if "history" in st.session_state and len(st.session_state.history) > 0:
            with st.spinner("Indicizzazione conversazione..."):
                try:
                    chat_text = f"--- CHAT LOG: {selected_mode} | TOPIC: {chat_topic} ---\n"
                    for msg in st.session_state.history:
                        icon = "UTENTE" if msg['role'] == "user" else "AI"
                        chat_text += f"[{icon}]: {msg['content']}\n\n"
                    
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
                    # Nome file parlante
                    filename = f"Chat_{chat_topic.replace(' ', '_')}_{timestamp}.txt"
                    
                    files = {"file": (filename, chat_text.encode('utf-8'), "text/plain")}
                    
                    # Generazione TAG DINAMICO (es. CHAT_NIKE)
                    clean_topic = chat_topic.strip().upper().replace(' ', '_')
                    dynamic_tag = f"CHAT_{clean_topic}"
                    
                    data = {"client_name": dynamic_tag, "doc_type": "Chat History"}
                    
                    res = requests.post(IP_ACER_INGEST, files=files, data=data, timeout=60)
                    if res.status_code == 200:
                        st.success(f"✅ Chat salvata! Tag assegnato: **{dynamic_tag}**")
                    else:
                        st.error("Errore salvataggio.")
                except Exception as e:
                    st.error(f"Errore: {e}")
        else:
            st.warning("Nessuna chat da salvare.")

# --- INTERFACCIA PRINCIPALE ---
st.title(f"🧠 Agency Brain • {selected_mode}")

if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input(f"Dai un ordine a {selected_mode}...")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        container = st.empty()
        container.info("🤔 Analisi contesto e pianificazione...")
        
        # FASE 1: PLANNER (INTELLIGENZA DEI TAG AGGIUNTA)
        suggested_filter = personas.FILTER_MAP.get(selected_mode, "nessuno")
        
        planner_prompt = f"""
        L'utente ha chiesto: "{prompt}"
        Il ruolo attivo è: "{selected_mode}"
        
        Il tuo compito è decidere cosa cercare nel database vettoriale (Zenbook).
        Suggerimento filtro per questo ruolo: {suggested_filter}
        
        [GUIDA AI TAG PER IL DATABASE]
        - Se l'utente parla di un CLIENTE, cerca tag come 'CLIENTE_Nome' o 'DATA_Nome'.
        - Se parla di PROGETTI INTERNI o CODICE, cerca tag come 'PROGETTO_Nome' o 'SYSTEM_DOCS'.
        - Se chiede di una CHAT passata, cerca tag come 'CHAT_Nome'.
        - Se chiede teoria/manuali, usa i tag standard (RESEARCH_ADS, RESEARCH_COPY, ecc).
        
        Rispondi ESATTAMENTE in formato JSON:
        {{
            "query": "termini di ricerca specifici per il database",
            "client_filter": "nome tag esatto (es. RESEARCH_ADS, CLIENTE_NIKE) o 'nessuno'"
        }}
        """
        
        try:
            plan_response = client_ai.chat.completions.create(
                model="qwen-max",
                messages=[{"role": "user", "content": planner_prompt}],
                temperature=0.1
            )
            raw_json = plan_response.choices[0].message.content
            raw_json = raw_json.replace("```json", "").replace("```", "").strip()
            params = json.loads(raw_json)
            
            q_search = params.get("query")
            q_client = params.get("client_filter")
            
            container.write(f"🔍 **Ricerca:** '{q_search}' (Target: {q_client})")
            
            # FASE 2: WORKER
            retrieved_data = tools.search_memory(q_search, q_client)
            
            if "Nessun dato trovato" in retrieved_data:
                 container.caption("⚠️ Ricerca specifica vuota, estendo al database globale...")
                 retrieved_data = tools.search_memory(q_search, None)

            # FASE 3: ANALYST
            container.write("📝 **Elaborazione Strategia...**")
            
            system_persona = personas.PERSONA_MAP.get(selected_mode, "Sei un assistente utile.")
            
            final_prompt = f"""
            {system_persona}
            
            [CONTESTO OPERATIVO]
            L'utente ha chiesto: "{prompt}"
            
            [DATI DALLA MEMORIA AZIENDALE]
            {retrieved_data}
            
            [ISTRUZIONI DI RISPOSTA]
            1. Usa il Tono di Voce definito nel tuo profilo.
            2. Basa la tua strategia sui DATI forniti sopra (se rilevanti).
            3. Se usi i dati dei paper, cita la fonte tra parentesi.
            4. Se mancano info, chiedile usando la fase di "Discovery" del tuo protocollo.
            """
            
            final_response = client_ai.chat.completions.create(
                model="qwen-max",
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.7 
            )
            
            answer = final_response.choices[0].message.content
            
            # --- TASSAMETRO ---
            usage = final_response.usage
            in_tokens = usage.prompt_tokens
            out_tokens = usage.completion_tokens
            cost = ((in_tokens/1000)*0.004) + ((out_tokens/1000)*0.012)
            
            container.markdown(answer)
            st.caption(f"📊 **Metrica:** Input: {in_tokens} | Output: {out_tokens} | **Costo: ${cost:.5f}**")
            
            st.session_state.history.append({"role": "assistant", "content": answer})

        except Exception as e:
            container.error(f"❌ Errore Critico: {e}")