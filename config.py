# -*- coding: utf-8 -*-
"""
CONFIGURAZIONE CENTRALIZZATA - Agency OS v15
=============================================

Unica fonte di verità per tutti i parametri del sistema.

v15:
- Root LM: qwen-max (migliore ragionamento e lettura dati)
- Sub LM: qwen-plus (analisi testi)
- Rimosso Acer: ingester integrato in Streamlit
- API key da .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# 🤖 QWEN / DASHSCOPE
# ============================================

QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# Modelli v15
QWEN_MODEL_ROOT = "qwen-max"          # Root LM - Ragionamento, orchestrazione REPL
QWEN_MODEL_SUB = "qwen-plus"          # Sub LM - Analisi testi e dati

# ============================================
# 📊 QDRANT (Asus Zenbook)
# ============================================

QDRANT_HOST = os.getenv("QDRANT_HOST", "192.168.1.3")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
COLLECTION_NAME = "agenzia_memory"

# ============================================
# 🔤 ENCODER
# ============================================

ENCODER_MODEL = "all-MiniLM-L6-v2"

# ============================================
# 📂 INGESTER (locale, integrato in Streamlit)
# ============================================

# Cartella per file dati (Excel/CSV per analisi diretta)
DATA_FILES_DIR = "./data_files"

# Chunking
CHUNK_SIZE = 500       # parole per chunk
CHUNK_OVERLAP = 50     # parole di overlap

# ============================================
# ALIAS PER COMPATIBILITÀ
# ============================================

API_KEY = QWEN_API_KEY
BASE_URL = QWEN_BASE_URL


# ============================================
# HELPER
# ============================================

def print_config():
    """Stampa la configurazione attuale."""
    print("=" * 50)
    print("AGENCY OS v15")
    print("=" * 50)
    print(f"Qdrant:     {QDRANT_URL}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Root LM:    {QWEN_MODEL_ROOT}")
    print(f"Sub LM:     {QWEN_MODEL_SUB}")
    print(f"API Key:    {'✅ Configurata' if QWEN_API_KEY else '❌ MANCANTE'}")
    print("=" * 50)
