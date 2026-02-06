# -*- coding: utf-8 -*-
"""
CONFIGURAZIONE CENTRALIZZATA - Agency OS v16
=============================================

v16 — Aggiornamento modelli per architettura RLM corretta:
- Root LM: qwen3-max (258k context — allineato con GPT-5 usato nel paper RLM)
- Sub LM: qwen-plus (fino a 1M context — analizza documenti interi)
- Limiti di contesto espliciti per modello
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

# Modelli v16
QWEN_MODEL_ROOT = "qwen3-max"          # Root LM — 258k context, ragionamento top
QWEN_MODEL_SUB = "qwen-plus"           # Sub LM — fino a 1M context, analisi documenti

# ============================================
# 📐 LIMITI CONTESTO PER MODELLO
# ============================================
# Limiti REALI confermati dalla documentazione DashScope.
# Il sistema li usa per gestire il troncamento in modo adattivo.

MODEL_CONTEXT_LIMITS = {
    # Modello: (max_input_tokens, max_output_tokens)
    "qwen3-max":        (258048, 65536),   # Context totale: 262144
    "qwen-max":         (30720,  8192),    # Context totale: 32768
    "qwen-plus":        (129024, 8192),    # Default; fino a 1M con max_input_tokens
    "qwen-flash":       (129024, 8192),    # Default; fino a 1M
    "qwen-turbo":       (129024, 8192),    # Default; fino a 1M
    "qwen3-coder-plus": (1000000, 65536),  # 1M input
}

def get_root_context_limit(model: str = None) -> int:
    """Restituisce il limite di input token per il Root LM."""
    model = model or QWEN_MODEL_ROOT
    limits = MODEL_CONTEXT_LIMITS.get(model, (30720, 8192))
    return limits[0]

def get_safe_context_limit(model: str = None) -> int:
    """
    Limite 'sicuro' per il Root LM = 80% del max input.
    Lascia margine per la risposta e per il next_action_prompt.
    """
    return int(get_root_context_limit(model) * 0.80)

# ============================================
# 📊 QDRANT (Asus Zenbook)
# ============================================

QDRANT_HOST = os.getenv("QDRANT_HOST", "192.168.1.6")
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

DATA_FILES_DIR = "./data_files"

# Chunking per embedding vettoriale (necessario per sentence-transformers)
# Nota: questo è il chunking per QDRANT, non per RLM.
# RLM accede ai documenti completi tramite get_file_content().
CHUNK_SIZE = 1000      # parole per chunk
CHUNK_OVERLAP = 100    # parole di overlap

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
    root_limit = get_root_context_limit()
    safe_limit = get_safe_context_limit()
    
    print("=" * 50)
    print("AGENCY OS v16")
    print("=" * 50)
    print(f"Qdrant:       {QDRANT_URL}")
    print(f"Collection:   {COLLECTION_NAME}")
    print(f"Root LM:      {QWEN_MODEL_ROOT} ({root_limit:,} max input tokens)")
    print(f"Sub LM:       {QWEN_MODEL_SUB}")
    print(f"Safe context: {safe_limit:,} tokens")
    print(f"API Key:      {'✅ Configurata' if QWEN_API_KEY else '❌ MANCANTE'}")
    print("=" * 50)
