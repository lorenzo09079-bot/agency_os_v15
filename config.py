# -*- coding: utf-8 -*-
"""
CONFIGURAZIONE CENTRALIZZATA - Agency OS v14
=============================================

Modifica gli IP QUI e tutti i file li leggeranno automaticamente.

AGGIORNAMENTO v14:
- Nuova API Key DashScope International
- Root LM: qwen3-coder-plus (specializzato codice)
- Sub LM: qwen-plus (analisi testi)
"""

# ============================================
# 🔧 NETWORK - MODIFICA QUESTI VALORI QUANDO GLI IP CAMBIANO
# ============================================

# ASUS ZENBOOK - Database Vettoriale (Qdrant + Docker)
ASUS_IP = "192.168.1.6"
QDRANT_PORT = 6333

# ACER - Server Ingestione Documenti
ACER_IP = "192.168.1.7"
INGEST_PORT = 5000

# ============================================
# URL COMPLETI (generati automaticamente)
# ============================================

QDRANT_URL = f"http://{ASUS_IP}:{QDRANT_PORT}"
QDRANT_HOST = ASUS_IP
INGEST_URL = f"http://{ACER_IP}:{INGEST_PORT}"
INGEST_ENDPOINT = f"{INGEST_URL}/ingest"

# ============================================
# 🤖 QWEN/DASHSCOPE - API v14
# ============================================

# API Key (International - Singapore endpoint)
QWEN_API_KEY = "sk-c6cdd02fbdb14232a22a589b94a18d14"

# Base URL - International (Singapore)
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# Modelli v14
QWEN_MODEL_ROOT = "qwen3-coder-plus"  # Root LM - Generazione codice REPL
QWEN_MODEL_SUB = "qwen-plus"          # Sub LM - Analisi testi e ragionamento

# Alias per compatibilità
QWEN_MODEL_DEFAULT = QWEN_MODEL_ROOT
QWEN_MODEL_FAST = QWEN_MODEL_SUB

# ============================================
# 📊 DATABASE
# ============================================

COLLECTION_NAME = "agenzia_memory"
ENCODER_MODEL = "all-MiniLM-L6-v2"

# ============================================
# ALIAS PER COMPATIBILITÀ CON VECCHIO CODICE
# ============================================

API_KEY = QWEN_API_KEY
BASE_URL = QWEN_BASE_URL
ACER_PORT = INGEST_PORT
QDRANT_IP = ASUS_IP

# Vecchi nomi modelli -> nuovi
QWEN_MODEL_CHEAP = "qwen-flash"  # Se serve economico

# ============================================
# HELPER FUNCTIONS
# ============================================

def print_config():
    """Stampa la configurazione attuale."""
    print("=" * 50)
    print("CONFIGURAZIONE AGENCY OS v14")
    print("=" * 50)
    print(f"Qdrant:     {QDRANT_URL}")
    print(f"Ingest:     {INGEST_URL}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Root LM:    {QWEN_MODEL_ROOT}")
    print(f"Sub LM:     {QWEN_MODEL_SUB}")
    print(f"Base URL:   {QWEN_BASE_URL}")
    print("=" * 50)


def test_connections():
    """Testa le connessioni ai server."""
    import requests
    
    print("\n🔌 Test Connessioni...")
    
    # Test Qdrant
    try:
        r = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        if r.status_code == 200:
            print(f"✅ Qdrant ({ASUS_IP}): OK")
        else:
            print(f"⚠️ Qdrant ({ASUS_IP}): Status {r.status_code}")
    except Exception as e:
        print(f"❌ Qdrant ({ASUS_IP}): {e}")
    
    # Test Acer
    try:
        r = requests.get(f"{INGEST_URL}/health", timeout=5)
        if r.status_code == 200:
            print(f"✅ Acer ({ACER_IP}): OK")
        else:
            print(f"⚠️ Acer ({ACER_IP}): Status {r.status_code}")
    except Exception as e:
        print(f"❌ Acer ({ACER_IP}): {e}")


def test_qwen_api():
    """Testa la connessione all'API Qwen."""
    from openai import OpenAI
    
    print("\n🤖 Test API Qwen...")
    
    try:
        client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)
        response = client.chat.completions.create(
            model=QWEN_MODEL_SUB,  # Usa il più economico per test
            messages=[{"role": "user", "content": "Rispondi solo: OK"}],
            max_tokens=10
        )
        print(f"✅ Qwen API: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Qwen API: {e}")


if __name__ == "__main__":
    print_config()
    test_connections()
    test_qwen_api()
