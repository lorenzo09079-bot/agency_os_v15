# test_cluster.py - Test completo del cluster
import requests
import sys

print("=" * 60)
print("🧪 TEST CLUSTER AGENCY OS")
print("=" * 60)

# Configurazione
ASUS_IP = "192.168.1.6"
ACER_IP = "192.168.1.8"

tests_passed = 0
tests_failed = 0

# TEST 1: Qdrant (Asus)
print("\n[1/5] Test Qdrant (Asus)...")
try:
    r = requests.get(f"http://{ASUS_IP}:6333/collections", timeout=5)
    if r.status_code == 200:
        print(f"  ✅ Qdrant OK - {ASUS_IP}:6333")
        tests_passed += 1
    else:
        print(f"  ❌ Qdrant risponde ma status {r.status_code}")
        tests_failed += 1
except Exception as e:
    print(f"  ❌ Qdrant non raggiungibile: {e}")
    tests_failed += 1

# TEST 2: Ingest Server (Acer)
print("\n[2/5] Test Ingest Server (Acer)...")
try:
    r = requests.get(f"http://{ACER_IP}:5000/health", timeout=5)
    data = r.json()
    if data.get("qdrant_connected"):
        print(f"  ✅ Acer OK - Connesso a Qdrant")
        print(f"     Punti nel DB: {data.get('total_points', 'N/A')}")
        tests_passed += 1
    else:
        print(f"  ⚠️ Acer attivo ma Qdrant non connesso")
        tests_failed += 1
except Exception as e:
    print(f"  ❌ Acer non raggiungibile: {e}")
    tests_failed += 1

# TEST 3: Lista Tag
print("\n[3/5] Test Lista Tag...")
try:
    r = requests.get(f"http://{ACER_IP}:5000/tags", timeout=5)
    data = r.json()
    tags = data.get("tags", [])
    print(f"  ✅ Tag trovati: {len(tags)}")
    if tags:
        print(f"     Esempi: {', '.join(tags[:5])}")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Errore: {e}")
    tests_failed += 1

# TEST 4: Ricerca Memoria (tools.py)
print("\n[4/5] Test Ricerca Memoria...")
try:
    import tools
    result = tools.search_memory("marketing", None)
    if "ERRORE" not in result and "ERROR" not in result:
        print(f"  ✅ Ricerca OK")
        # Conta risultati
        count = result.count("Score:")
        print(f"     Risultati trovati: {count}")
        tests_passed += 1
    else:
        print(f"  ❌ Errore ricerca: {result[:100]}")
        tests_failed += 1
except Exception as e:
    print(f"  ❌ Errore: {e}")
    tests_failed += 1

# TEST 5: Upload Test (opzionale)
print("\n[5/5] Test Upload Documento...")
try:
    # Crea file di test
    test_content = "Questo è un documento di test per Agency OS. Data: 2026-01-24. Budget: €10000."
    
    files = {"file": ("test_document.txt", test_content.encode(), "text/plain")}
    data = {"client_name": "TEST_VERIFICA", "doc_type": "Test"}
    
    r = requests.post(f"http://{ACER_IP}:5000/ingest", files=files, data=data, timeout=30)
    
    if r.status_code == 200:
        result = r.json()
        print(f"  ✅ Upload OK")
        print(f"     Tag: {result.get('tag')}")
        print(f"     Chunks: {result.get('chunks')}")
        tests_passed += 1
    else:
        print(f"  ❌ Upload fallito: {r.text}")
        tests_failed += 1
except Exception as e:
    print(f"  ❌ Errore: {e}")
    tests_failed += 1

# RIEPILOGO
print("\n" + "=" * 60)
print(f"📊 RISULTATO: {tests_passed} passati, {tests_failed} falliti")
print("=" * 60)

if tests_failed == 0:
    print("\n🎉 TUTTI I TEST PASSATI! Il cluster è operativo.")
else:
    print("\n⚠️ Alcuni test falliti. Controlla i messaggi sopra.")