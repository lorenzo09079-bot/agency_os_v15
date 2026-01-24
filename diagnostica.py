# -*- coding: utf-8 -*-
"""
Agency OS - Diagnostica Sistema v1.0
Verifica stato di tutti i componenti

Esegui: python diagnostica.py
"""
import sys
import os

print("=" * 60)
print("🔍 DIAGNOSTICA AGENCY OS")
print("=" * 60)

# --- 1. CHECK DIPENDENZE ---
print("\n[1] DIPENDENZE PYTHON")
print("-" * 40)

dependencies = {
    "pandas": "Analisi dati",
    "openpyxl": "Lettura file Excel (.xlsx)",
    "qdrant_client": "Database vettoriale",
    "sentence_transformers": "Encoding testo",
    "openai": "Client API (Qwen)",
    "streamlit": "Interfaccia web",
    "requests": "HTTP requests",
}

missing = []
for pkg, desc in dependencies.items():
    try:
        __import__(pkg.replace("-", "_"))
        print(f"  ✅ {pkg}: OK ({desc})")
    except ImportError:
        print(f"  ❌ {pkg}: MANCANTE ({desc})")
        missing.append(pkg)

if missing:
    print(f"\n  ⚠️  Installa con: pip install {' '.join(missing)}")

# --- 2. CHECK QDRANT ---
print("\n[2] CONNESSIONE QDRANT")
print("-" * 40)

try:
    from qdrant_client import QdrantClient
    import time
    
    QDRANT_IP = "192.168.1.4"
    QDRANT_PORT = 6333
    COLLECTION = "agenzia_memory"
    
    print(f"  Connessione a {QDRANT_IP}:{QDRANT_PORT}...")
    
    start = time.time()
    client = QdrantClient(host=QDRANT_IP, port=QDRANT_PORT, timeout=10)
    
    # Test collection
    info = client.get_collection(COLLECTION)
    elapsed = time.time() - start
    
    print(f"  ✅ Connesso in {elapsed:.2f}s")
    print(f"  📊 Collection: {COLLECTION}")
    print(f"  📦 Punti totali: {info.points_count}")
    print(f"  📐 Dimensione vettori: {info.config.params.vectors.size}")
    
    # Test velocità query
    print(f"\n  Test velocità ricerca...")
    from sentence_transformers import SentenceTransformer
    encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    start = time.time()
    vector = encoder.encode("test query").tolist()
    hits = client.search(collection_name=COLLECTION, query_vector=vector, limit=3)
    elapsed = time.time() - start
    
    print(f"  ✅ Ricerca completata in {elapsed:.2f}s")
    print(f"  📄 Risultati: {len(hits)}")
    
    if elapsed > 5:
        print(f"  ⚠️  ATTENZIONE: Ricerca lenta (>{elapsed:.0f}s). Verifica rete/Qdrant.")
    
except Exception as e:
    print(f"  ❌ ERRORE: {e}")
    print(f"  💡 Verifica che Qdrant sia attivo su {QDRANT_IP}:{QDRANT_PORT}")

# --- 3. CHECK SERVER INGESTER ---
print("\n[3] SERVER INGESTER (Acer)")
print("-" * 40)

try:
    import requests
    
    INGESTER_URL = "http://192.168.1.6:5000"
    
    print(f"  Connessione a {INGESTER_URL}...")
    
    try:
        response = requests.get(f"{INGESTER_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Server attivo")
            print(f"  📊 Versione: {data.get('version', 'N/A')}")
            print(f"  🔗 Qdrant: {'OK' if data.get('qdrant_connected') else 'ERRORE'}")
            print(f"  📦 Punti: {data.get('total_points', 'N/A')}")
        else:
            print(f"  ⚠️  Risposta: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Server non raggiungibile")
        print(f"  💡 Avvia il server sull'Acer: python server_ingest.py")
    except requests.exceptions.Timeout:
        print(f"  ❌ Timeout connessione")
        
except Exception as e:
    print(f"  ❌ ERRORE: {e}")

# --- 4. CHECK FILE DATI ---
print("\n[4] FILE DATI LOCALI")
print("-" * 40)

data_dir = "./data_files"
if os.path.exists(data_dir):
    files = []
    for ext in ['*.xlsx', '*.xls', '*.csv']:
        import glob
        files.extend(glob.glob(os.path.join(data_dir, ext)))
    
    if files:
        print(f"  📁 Cartella: {data_dir}")
        print(f"  📄 File trovati: {len(files)}")
        
        for f in files:
            fname = os.path.basename(f)
            size = os.path.getsize(f) / 1024  # KB
            
            # Test lettura
            try:
                import pandas as pd
                if f.endswith('.csv'):
                    df = pd.read_csv(f, nrows=1)
                else:
                    df = pd.read_excel(f, nrows=1)
                status = f"✅ Leggibile ({len(df.columns)} colonne)"
            except Exception as e:
                status = f"❌ Errore: {str(e)[:50]}"
            
            print(f"    - {fname} ({size:.1f}KB): {status}")
    else:
        print(f"  ⚠️  Nessun file dati in {data_dir}")
else:
    print(f"  ⚠️  Cartella {data_dir} non esiste")
    print(f"  💡 Verrà creata automaticamente al primo upload")

# --- 5. CHECK TAG NEL DATABASE ---
print("\n[5] TAG NEL DATABASE")
print("-" * 40)

try:
    from qdrant_client import QdrantClient
    
    client = QdrantClient(host="192.168.1.4", port=6333, timeout=10)
    
    results = client.scroll(
        collection_name="agenzia_memory",
        limit=1000,
        with_payload=True,
        with_vectors=False
    )
    
    tags = {}
    for point in results[0]:
        tag = point.payload.get('client_name', 'UNKNOWN')
        if tag not in tags:
            tags[tag] = {"count": 0, "files": set()}
        tags[tag]["count"] += 1
        tags[tag]["files"].add(point.payload.get('filename', 'unknown'))
    
    print(f"  📊 Tag trovati: {len(tags)}")
    for tag, info in sorted(tags.items()):
        print(f"    - {tag}: {len(info['files'])} documenti, {info['count']} chunks")
    
    # Cerca tag CHAT_*
    chat_tags = [t for t in tags if t.startswith("CHAT_")]
    if chat_tags:
        print(f"\n  💬 Tag CHAT trovati: {chat_tags}")
    else:
        print(f"\n  ⚠️  Nessun tag CHAT_ nel database")
        print(f"  💡 Le chat potrebbero non essere state caricate correttamente")

except Exception as e:
    print(f"  ❌ ERRORE: {e}")

# --- 6. RIEPILOGO ---
print("\n" + "=" * 60)
print("📋 RIEPILOGO")
print("=" * 60)

if missing:
    print(f"\n⚠️  AZIONI RICHIESTE:")
    print(f"   1. Installa dipendenze mancanti:")
    print(f"      pip install {' '.join(missing)}")

print(f"\n💡 SUGGERIMENTI:")
print(f"   - Se Qdrant è lento, riavvia il servizio sullo Zenbook")
print(f"   - Se le chat non sono nel DB, ricaricale tramite l'app")
print(f"   - Se il server Acer è offline, avvialo con: python server_ingest.py")

print("\n" + "=" * 60)
