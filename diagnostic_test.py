# -*- coding: utf-8 -*-
"""
DIAGNOSTIC TEST - Agency OS
===========================
Esegui questo script per verificare lo stato di tutti i componenti.

USO:
    cd alla cartella AI_Lab
    python diagnostic_test.py

Questo script testera:
1. Connessione a Qdrant
2. Connessione al server Ingest (Acer)
3. API Qwen/DashScope
4. Import RLM
5. Tools e loro funzionamento
6. Un test RLM completo
"""

import sys
import os
import json
from datetime import datetime

# Colori per output
class Colors:
    OK = '\033[92m'      # Verde
    WARN = '\033[93m'    # Giallo
    FAIL = '\033[91m'    # Rosso
    BOLD = '\033[1m'
    END = '\033[0m'

def ok(msg): print(f"{Colors.OK}[OK] {msg}{Colors.END}")
def warn(msg): print(f"{Colors.WARN}[WARN] {msg}{Colors.END}")
def fail(msg): print(f"{Colors.FAIL}[FAIL] {msg}{Colors.END}")
def header(msg): print(f"\n{Colors.BOLD}{'='*60}\n{msg}\n{'='*60}{Colors.END}")

results = {
    "timestamp": datetime.now().isoformat(),
    "tests": {}
}

# ============================================
# TEST 1: CONFIGURAZIONE
# ============================================
header("TEST 1: CONFIGURAZIONE")

try:
    from config import (
        ASUS_IP, QDRANT_PORT, QDRANT_URL,
        ACER_IP, INGEST_PORT, INGEST_URL,
        QWEN_API_KEY, QWEN_BASE_URL,
        COLLECTION_NAME
    )
    ok(f"config.py caricato")
    print(f"   Qdrant: {QDRANT_URL}")
    print(f"   Ingest: {INGEST_URL}")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   API Key: {QWEN_API_KEY[:10]}...{QWEN_API_KEY[-5:]}")
    results["tests"]["config"] = "OK"
except Exception as e:
    fail(f"config.py: {e}")
    results["tests"]["config"] = f"FAIL: {e}"

# ============================================
# TEST 2: CONNESSIONE QDRANT
# ============================================
header("TEST 2: CONNESSIONE QDRANT")

try:
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(host=ASUS_IP, port=QDRANT_PORT, timeout=10)
    
    # Test connessione
    collections = qdrant.get_collections()
    ok(f"Connesso a Qdrant ({ASUS_IP}:{QDRANT_PORT})")
    print(f"   Collections: {[c.name for c in collections.collections]}")
    
    # Test collection specifica
    try:
        info = qdrant.get_collection(COLLECTION_NAME)
        ok(f"Collection '{COLLECTION_NAME}' trovata")
        print(f"   Punti totali: {info.points_count}")
        results["tests"]["qdrant"] = f"OK - {info.points_count} punti"
    except Exception as e:
        warn(f"Collection '{COLLECTION_NAME}' non trovata: {e}")
        results["tests"]["qdrant"] = f"WARN: collection non trovata"
        
except Exception as e:
    fail(f"Qdrant non raggiungibile: {e}")
    results["tests"]["qdrant"] = f"FAIL: {e}"

# ============================================
# TEST 3: CONNESSIONE SERVER INGEST (ACER)
# ============================================
header("TEST 3: SERVER INGEST (ACER)")

try:
    import requests
    
    # Health check
    r = requests.get(f"{INGEST_URL}/health", timeout=10)
    if r.status_code == 200:
        data = r.json()
        ok(f"Server Ingest attivo ({ACER_IP}:{INGEST_PORT})")
        print(f"   Versione: {data.get('version', 'N/A')}")
        print(f"   Modalita: {data.get('mode', 'N/A')}")
        print(f"   Documenti: {data.get('total_documents', 'N/A')}")
        results["tests"]["ingest_server"] = "OK"
    else:
        warn(f"Server risponde con status {r.status_code}")
        results["tests"]["ingest_server"] = f"WARN: status {r.status_code}"
        
except requests.exceptions.ConnectionError:
    fail(f"Server Ingest non raggiungibile su {INGEST_URL}")
    print("   Verifica che il server sia avviato su Acer:")
    print("   python server_ingest.py")
    results["tests"]["ingest_server"] = "FAIL: connection refused"
except Exception as e:
    fail(f"Errore: {e}")
    results["tests"]["ingest_server"] = f"FAIL: {e}"

# ============================================
# TEST 4: API QWEN (DashScope)
# ============================================
header("TEST 4: API QWEN (DashScope)")

try:
    from openai import OpenAI
    
    client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)
    
    # Test semplice
    response = client.chat.completions.create(
        model="qwen-turbo",  # Modello piu economico per test
        messages=[{"role": "user", "content": "Rispondi solo: OK"}],
        max_tokens=10
    )
    
    answer = response.choices[0].message.content
    ok(f"API Qwen funzionante")
    print(f"   Risposta test: '{answer}'")
    print(f"   Token usati: {response.usage.total_tokens}")
    results["tests"]["qwen_api"] = "OK"
    
except Exception as e:
    fail(f"API Qwen: {e}")
    results["tests"]["qwen_api"] = f"FAIL: {e}"

# ============================================
# TEST 5: IMPORT RLM
# ============================================
header("TEST 5: IMPORT RLM")

try:
    # IMPORTANTE: Aggiungi current working directory al path PRIMA di tutto
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    
    # Aggiungi anche path dello script se diverso
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Debug: mostra il path
    print(f"   CWD: {cwd}")
    print(f"   sys.path[0]: {sys.path[0]}")
    
    from rlm import RLM
    ok("RLM base importato")
    
    from rlm.rlm_repl import RLM_REPL
    ok("RLM_REPL importato")
    
    from rlm.repl import REPLEnv
    ok("REPLEnv importato")
    
    # Verifica inject_tools
    if hasattr(REPLEnv, 'inject_tools'):
        ok("REPLEnv.inject_tools() disponibile")
    else:
        warn("REPLEnv.inject_tools() NON disponibile - versione vecchia?")
    
    from rlm.utils.llm import OpenAIClient
    ok("OpenAIClient (Qwen) importato")
    
    results["tests"]["rlm_imports"] = "OK"
    
except ImportError as e:
    fail(f"Import fallito: {e}")
    results["tests"]["rlm_imports"] = f"FAIL: {e}"

# ============================================
# TEST 6: TOOLS
# ============================================
header("TEST 6: TOOLS DATABASE")

try:
    import tools
    
    # Test list_all_tags
    if hasattr(tools, 'list_all_tags'):
        tags = tools.list_all_tags()
        if "error" not in tags:
            ok(f"list_all_tags() funziona - {len(tags)} tag trovati")
            for tag, count in list(tags.items())[:5]:
                print(f"   - {tag}: {count} documenti")
            results["tests"]["tools_list_tags"] = f"OK - {len(tags)} tags"
        else:
            fail(f"list_all_tags() errore: {tags['error']}")
            results["tests"]["tools_list_tags"] = f"FAIL: {tags['error']}"
    else:
        warn("list_all_tags() non disponibile")
        results["tests"]["tools_list_tags"] = "WARN: funzione mancante"
    
    # Test get_database_stats
    if hasattr(tools, 'get_database_stats'):
        stats = tools.get_database_stats()
        if "error" not in stats:
            ok(f"get_database_stats() funziona")
            print(f"   Chunks totali: {stats.get('total_chunks', 'N/A')}")
            print(f"   File totali: {stats.get('total_files', 'N/A')}")
            print(f"   Tag totali: {stats.get('total_tags', 'N/A')}")
        else:
            warn(f"get_database_stats() errore: {stats['error']}")
    
    # Test search_semantic
    if hasattr(tools, 'search_semantic'):
        results_search = tools.search_semantic("test", top_k=2)
        if results_search and "error" not in results_search[0]:
            ok(f"search_semantic() funziona - {len(results_search)} risultati")
        else:
            warn("search_semantic() nessun risultato o errore")
    
    results["tests"]["tools"] = "OK"
    
except Exception as e:
    fail(f"Tools: {e}")
    import traceback
    traceback.print_exc()
    results["tests"]["tools"] = f"FAIL: {e}"

# ============================================
# TEST 7: RLM REPL ENVIRONMENT
# ============================================
header("TEST 7: RLM REPL ENVIRONMENT")

try:
    from rlm.repl import REPLEnv
    
    # Crea ambiente REPL
    env = REPLEnv(
        recursive_model="qwen-plus",
        context_str="Test context: il numero magico e 42."
    )
    ok("REPLEnv creato")
    
    # Test esecuzione codice
    result = env.code_execution("print('Hello from REPL')")
    if "Hello from REPL" in result.stdout:
        ok("Esecuzione codice funziona")
    else:
        warn(f"Output inatteso: {result.stdout}")
    
    # Test accesso al context
    result = env.code_execution("print(context[:50])")
    if "42" in result.stdout or "magico" in result.stdout:
        ok("Context accessibile nel REPL")
    else:
        warn(f"Context non trovato: {result.stdout}")
    
    # Test inject_tools
    if hasattr(env, 'inject_tools'):
        def dummy_tool():
            return "Tool funziona!"
        
        env.inject_tools({'test_tool': dummy_tool})
        result = env.code_execution("print(test_tool())")
        
        if "Tool funziona!" in result.stdout:
            ok("inject_tools() funziona")
        else:
            warn(f"inject_tools output: {result.stdout}")
    
    # Test FINAL
    result = env.code_execution("risposta = 'La risposta e 42'")
    if "risposta" in env.locals:
        ok(f"Variabili salvate nel REPL: {list(env.locals.keys())[:5]}")
    
    results["tests"]["repl_env"] = "OK"
    
except Exception as e:
    fail(f"REPL Environment: {e}")
    import traceback
    traceback.print_exc()
    results["tests"]["repl_env"] = f"FAIL: {e}"

# ============================================
# TEST 8: RLM COMPLETO (Mini Test)
# ============================================
header("TEST 8: RLM COMPLETO (Mini Test)")

try:
    from rlm.rlm_repl import RLM_REPL
    import tools
    
    # Imposta variabili ambiente
    os.environ["OPENAI_API_KEY"] = QWEN_API_KEY
    os.environ["OPENAI_BASE_URL"] = QWEN_BASE_URL
    
    # Crea RLM
    rlm = RLM_REPL(
        model="qwen-plus",  # Piu economico per test
        recursive_model="qwen-turbo",
        max_iterations=3,  # Poche iterazioni per test veloce
        enable_logging=True
    )
    ok("RLM_REPL creato")
    
    # Context semplice
    context = "Il numero segreto in questo documento e 12345."
    
    # Setup
    rlm.setup_context(context=context, query="Qual e il numero segreto?")
    ok("Context impostato")
    
    # Inietta tools
    if rlm.repl_env and hasattr(rlm.repl_env, 'inject_tools'):
        tools_dict = {
            'list_all_tags': tools.list_all_tags,
            'search_semantic': tools.search_semantic,
        }
        rlm.repl_env.inject_tools(tools_dict)
        ok("Tools iniettati")
    
    # Esegui (test veloce)
    print("\n   Esecuzione RLM (max 3 iterazioni)...")
    result = rlm.completion(context=context, query="Qual e il numero segreto? Rispondi brevemente.")
    
    print(f"\n   Risposta RLM: {result[:200]}...")
    
    if "12345" in result:
        ok("RLM ha trovato la risposta corretta!")
        results["tests"]["rlm_complete"] = "OK"
    else:
        warn("RLM non ha trovato il numero, ma ha risposto")
        results["tests"]["rlm_complete"] = f"WARN: risposta senza numero"
    
except Exception as e:
    fail(f"RLM completo: {e}")
    import traceback
    traceback.print_exc()
    results["tests"]["rlm_complete"] = f"FAIL: {e}"

# ============================================
# RIEPILOGO
# ============================================
header("RIEPILOGO DIAGNOSTICA")

total_tests = len(results["tests"])
passed = sum(1 for v in results["tests"].values() if v.startswith("OK"))
warnings = sum(1 for v in results["tests"].values() if v.startswith("WARN"))
failed = sum(1 for v in results["tests"].values() if v.startswith("FAIL"))

print(f"Totale test: {total_tests}")
print(f"{Colors.OK}Passati: {passed}{Colors.END}")
print(f"{Colors.WARN}Warning: {warnings}{Colors.END}")
print(f"{Colors.FAIL}Falliti: {failed}{Colors.END}")

print("\nDettaglio:")
for test, result in results["tests"].items():
    if result.startswith("OK"):
        print(f"  {Colors.OK}[OK] {test}: {result}{Colors.END}")
    elif result.startswith("WARN"):
        print(f"  {Colors.WARN}[WARN] {test}: {result}{Colors.END}")
    else:
        print(f"  {Colors.FAIL}[FAIL] {test}: {result}{Colors.END}")

# Salva risultati
output_file = "diagnostic_results.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nRisultati salvati in: {output_file}")

# ============================================
# SUGGERIMENTI
# ============================================
header("SUGGERIMENTI")

if failed > 0:
    print("Problemi da risolvere:")
    
    if "qdrant" in results["tests"] and "FAIL" in results["tests"]["qdrant"]:
        print("   - Verifica che Qdrant sia attivo su Asus (docker ps)")
        print("   - Verifica IP in config.py")
    
    if "ingest_server" in results["tests"] and "FAIL" in results["tests"]["ingest_server"]:
        print("   - Avvia server su Acer: python server_ingest.py")
    
    if "qwen_api" in results["tests"] and "FAIL" in results["tests"]["qwen_api"]:
        print("   - Verifica API key in config.py")
        print("   - Verifica connessione internet")
    
    if "rlm_imports" in results["tests"] and "FAIL" in results["tests"]["rlm_imports"]:
        print("   - Verifica struttura cartella rlm/")
        print("   - Installa dipendenze: pip install openai rich")

if passed == total_tests:
    print("Tutto funziona! Il problema potrebbe essere nei prompt o nella logica.")
    print("   Condividi i log delle query problematiche per analisi.")

print("\n" + "="*60)
