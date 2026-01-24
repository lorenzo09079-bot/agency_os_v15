# -*- coding: utf-8 -*-
"""
CONFIGURAZIONE CENTRALIZZATA - Agency OS
=========================================

Modifica gli IP QUI e tutti i file li leggeranno automaticamente.
Non dovrai più cercare e modificare IP in 10 file diversi!

ISTRUZIONI:
1. Modifica gli IP sotto quando cambiano
2. Tutti i file che importano questo modulo useranno gli IP corretti

SUGGERIMENTO:
Per evitare che gli IP cambino, imposta IP statici sui PC:
- Asus (Qdrant): 192.168.1.100
- Acer (Ingest): 192.168.1.101
"""

# ============================================
# 🔧 MODIFICA QUESTI VALORI QUANDO GLI IP CAMBIANO
# ============================================

# ASUS ZENBOOK - Database Vettoriale (Qdrant + Docker)
ASUS_IP = "192.168.1.6"
QDRANT_PORT = 6333

# ACER - Server Ingestione Documenti
ACER_IP = "192.168.1.8"
INGEST_PORT = 5000

# ============================================
# URL COMPLETI (generati automaticamente)
# ============================================

# Qdrant
QDRANT_URL = f"http://{ASUS_IP}:{QDRANT_PORT}"
QDRANT_HOST = ASUS_IP

# Server Ingestione
INGEST_URL = f"http://{ACER_IP}:{INGEST_PORT}"
INGEST_ENDPOINT = f"{INGEST_URL}/ingest"

# ============================================
# CONFIGURAZIONE QWEN (DashScope)
# ============================================

QWEN_API_KEY = "sk-96a9773427c649d5a6af2a6842404c88"
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL_DEFAULT = "qwen-max"
QWEN_MODEL_FAST = "qwen-plus"
QWEN_MODEL_CHEAP = "qwen-turbo"

# ============================================
# CONFIGURAZIONE DATABASE
# ============================================

COLLECTION_NAME = "agenzia_memory"
ENCODER_MODEL = "all-MiniLM-L6-v2"

# ============================================
# HELPER FUNCTIONS
# ============================================

def print_config():
    """Stampa la configurazione attuale."""
    print("=" * 50)
    print("CONFIGURAZIONE AGENCY OS")
    print("=" * 50)
    print(f"Asus (Qdrant):  {QDRANT_URL}")
    print(f"Acer (Ingest):  {INGEST_URL}")
    print(f"Collection:     {COLLECTION_NAME}")
    print(f"Qwen Model:     {QWEN_MODEL_DEFAULT}")
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


# ============================================
# TEST
# ============================================

if __name__ == "__main__":
    print_config()
    test_connections()
