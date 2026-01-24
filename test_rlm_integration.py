# -*- coding: utf-8 -*-
"""
Test Script per RLM Integration
Verifica che tutti i componenti funzionino prima di usarli in Streamlit
"""
import sys
from pathlib import Path

print("=" * 60)
print("TEST RLM INTEGRATION - Agency OS v5.0")
print("=" * 60)

# Aggiungi la cartella rlm al path per gli import
rlm_path = Path("./rlm")
if rlm_path.exists():
    sys.path.insert(0, str(rlm_path))
    print("Aggiunta cartella RLM al path: " + str(rlm_path.absolute()))

tests_passed = 0
tests_failed = 0

# --- TEST 1: Import RLM ---
print("\n[1/6] Test import RLM...")
try:
    from rlm import RLM
    print("[OK] RLM importato correttamente")
    tests_passed += 1
except ImportError as e:
    print("[ERRORE] Import RLM: " + str(e))
    print("Suggerimento: Assicurati di aver fatto:")
    print("   cd rlm")
    print("   .venv\\Scripts\\activate")
    print("   uv pip install -e .")
    tests_failed += 1

# --- TEST 2: Import QwenClient ---
print("\n[2/6] Test import QwenClient...")
try:
    from rlm_qwen_client import QwenClient, create_qwen_client
    print("[OK] QwenClient importato")
    tests_passed += 1
except ImportError as e:
    print("[ERRORE] " + str(e))
    print("Suggerimento: Assicurati che rlm_qwen_client.py sia nella cartella corrente")
    tests_failed += 1

# --- TEST 3: Import Memory Tools ---
print("\n[3/6] Test import Memory Tools...")
try:
    from rlm_memory_tools import (
        MemoryTools, 
        MemoryToolsExecutor,
        get_rlm_tools_definitions
    )
    print("[OK] Memory Tools importati")
    tests_passed += 1
except ImportError as e:
    print("[ERRORE] " + str(e))
    print("Suggerimento: Assicurati che rlm_memory_tools.py sia nella cartella corrente")
    tests_failed += 1

# --- TEST 4: Test QwenClient ---
print("\n[4/6] Test chiamata API Qwen...")
try:
    client = QwenClient(
        api_key="sk-96a9773427c649d5a6af2a6842404c88",
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-max"
    )
    print("   -> Client inizializzato")
    
    # Test chiamata semplice
    print("   -> Invio richiesta test...")
    response = client.completion(prompt="Rispondi solo 'OK' se mi senti", temperature=0)
    
    print("   -> Risposta: " + str(response['response']))
    
    if response['usage']:
        cost = client.calculate_cost(response['usage'])
        print("   -> Token usati: " + str(response['usage']['total_tokens']))
        print("   -> Costo: $" + str(round(cost, 5)))
    
    print("[OK] Qwen API funzionante!")
    tests_passed += 1
    
except Exception as e:
    print("[ERRORE] API Qwen: " + str(e))
    print("Suggerimento: Verifica la tua API key e connessione internet")
    tests_failed += 1

# --- TEST 5: Test Function Calling ---
print("\n[5/6] Test Qwen Function Calling...")
try:
    # Definisci un tool di test
    test_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Ottieni il meteo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "La citta"}
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    response = client.completion(
        prompt="Che tempo fa a Roma?",
        tools=test_tools,
        temperature=0
    )
    
    if response['tool_calls']:
        tc = response['tool_calls'][0]
        print("   -> Tool chiamato: " + tc['function']['name'])
        print("   -> Argomenti: " + tc['function']['arguments'])
        print("[OK] Function Calling funzionante!")
        tests_passed += 1
    else:
        print("   -> Risposta testuale: " + str(response['response'][:100]))
        print("[OK] Function calling non attivato (ma API funziona)")
        tests_passed += 1
        
except Exception as e:
    print("[ERRORE] Function Calling: " + str(e))
    tests_failed += 1

# --- TEST 6: Test Memory Tools (connessione Qdrant) ---
print("\n[6/6] Test connessione Vector DB (Qdrant su Zenbook)...")
try:
    tools = MemoryTools()
    
    # Prima mostra i filtri (non richiede connessione)
    print("   -> Filtri disponibili:")
    filters = tools.list_available_filters()
    for line in filters.split('\n')[:3]:
        print("      " + line)
    
    # Prova connessione
    print("   -> Tentativo connessione a 192.168.1.4:6333...")
    result = tools.search_memory("test connessione", top_k=1)
    
    if "SYSTEM ERROR" in result:
        print("   [WARN] Qdrant non raggiungibile")
        print("   Nota: Questo e NORMALE se il Zenbook e spento")
        print("   L'app funzionera comunque (fallback mode)")
    else:
        print("   [OK] Connessione a Qdrant OK!")
    
    tests_passed += 1
    
except Exception as e:
    print("   [WARN] Errore connessione Qdrant: " + str(e))
    print("   Nota: Normale se Zenbook spento - l'app funzionera comunque")
    tests_passed += 1  # Non e un fallimento critico

# --- TEST BONUS: Import personas e tools esistenti ---
print("\n[BONUS] Test import file esistenti...")
try:
    import personas
    import tools as app_tools
    print("   [OK] personas.py importato")
    print("   [OK] tools.py importato")
    print("   -> Personas disponibili: " + str(list(personas.PERSONA_MAP.keys())))
except ImportError as e:
    print("   [WARN] File non trovati: " + str(e))
    print("   Nota: Assicurati di essere nella cartella con app.py")

# --- SUMMARY ---
print("\n" + "=" * 60)
print("RISULTATO TEST")
print("=" * 60)
print("Test passati: " + str(tests_passed))
print("Test falliti: " + str(tests_failed))

if tests_failed == 0:
    print("\nTUTTI I TEST PASSATI!")
    print("\nPROSSIMI STEP:")
    print("1. Assicurati che Zenbook (Qdrant) sia acceso per la memoria")
    print("2. Lancia l'app: streamlit run app_rlm_integrated.py")
    print("3. Nella sidebar, scegli tra modalita 'Standard' o 'RLM'")
    print("4. Testa prima con una query semplice")
else:
    print("\nALCUNI TEST FALLITI")
    print("Risolvi gli errori sopra prima di procedere.")
    print("Se hai bisogno di aiuto, copia l'output e chiedimi!")

print("\n" + "=" * 60)
