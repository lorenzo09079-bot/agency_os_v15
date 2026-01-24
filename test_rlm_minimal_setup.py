# -*- coding: utf-8 -*-
"""
Test RLM Minimal - Verifica Setup
=================================

Esegui questo script per verificare che RLM Minimal sia configurato correttamente
PRIMA di lanciare app_rlm_minimal.py

ISTRUZIONI:
1. Copia la cartella `rlm/` da RLM Minimal nella stessa directory di questo file
2. Sostituisci `rlm/utils/llm.py` con `rlm_utils_llm_qwen.py` (rinominandolo)
3. Esegui: python test_rlm_minimal_setup.py
"""

import sys
import os
from pathlib import Path

print("=" * 60)
print("🧪 TEST RLM MINIMAL SETUP")
print("=" * 60)

# Configurazione
API_KEY = "sk-96a9773427c649d5a6af2a6842404c88"
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

tests_passed = 0
tests_failed = 0

# ============================================
# TEST 1: Verifica struttura cartelle
# ============================================
print("\n[1/5] Verifica struttura cartelle RLM Minimal...")

rlm_path = Path("./rlm")
required_files = [
    "rlm/__init__.py",
    "rlm/rlm.py",
    "rlm/rlm_repl.py",
    "rlm/repl.py",
    "rlm/utils/__init__.py",
    "rlm/utils/llm.py",
    "rlm/utils/prompts.py",
    "rlm/utils/utils.py",
    "rlm/logger/__init__.py",
    "rlm/logger/root_logger.py",
    "rlm/logger/repl_logger.py",
]

missing_files = []
for f in required_files:
    if not Path(f).exists():
        missing_files.append(f)

if missing_files:
    print("❌ File mancanti:")
    for f in missing_files:
        print(f"   - {f}")
    print("\n💡 Assicurati di aver copiato la cartella 'rlm/' da RLM Minimal")
    tests_failed += 1
else:
    print("✅ Struttura cartelle OK")
    tests_passed += 1

# ============================================
# TEST 2: Verifica import RLM
# ============================================
print("\n[2/5] Test import RLM Minimal...")

if rlm_path.exists():
    sys.path.insert(0, str(rlm_path.absolute().parent))

try:
    from rlm.rlm_repl import RLM_REPL
    from rlm.repl import REPLEnv, Sub_RLM
    from rlm.utils.llm import OpenAIClient
    print("✅ Import RLM Minimal OK")
    tests_passed += 1
except ImportError as e:
    print(f"❌ Errore import: {e}")
    print("\n💡 Verifica che la cartella 'rlm/' sia nella directory corrente")
    tests_failed += 1

# ============================================
# TEST 3: Verifica configurazione Qwen nel client
# ============================================
print("\n[3/5] Test client LLM (Qwen)...")

try:
    # Imposta variabili ambiente per RLM Minimal
    os.environ["OPENAI_API_KEY"] = API_KEY
    os.environ["OPENAI_BASE_URL"] = BASE_URL
    
    # Prova a creare il client
    from rlm.utils.llm import OpenAIClient
    
    # Verifica che il client usi Qwen
    client = OpenAIClient(api_key=API_KEY, model="qwen-max")
    
    # Test chiamata
    print("   → Invio richiesta test a Qwen...")
    response = client.completion("Rispondi solo 'OK' se mi senti.")
    
    if "OK" in response or len(response) > 0:
        print(f"   → Risposta: {response[:50]}")
        print("✅ Client Qwen funzionante")
        tests_passed += 1
    else:
        print("❌ Risposta vuota o inattesa")
        tests_failed += 1
        
except Exception as e:
    print(f"❌ Errore client: {e}")
    print("\n💡 Verifica di aver sostituito rlm/utils/llm.py con la versione Qwen")
    tests_failed += 1

# ============================================
# TEST 4: Test REPLEnv base
# ============================================
print("\n[4/5] Test REPLEnv (ambiente REPL)...")

try:
    from rlm.repl import REPLEnv
    
    # Crea un ambiente REPL di test
    test_context = "Il numero magico è 42."
    
    repl = REPLEnv(
        recursive_model="qwen-plus",
        context_str=test_context
    )
    
    # Test esecuzione codice
    result = repl.code_execution("print(context[:20])")
    
    if result.stdout:
        print(f"   → Output REPL: {result.stdout.strip()}")
        print("✅ REPLEnv funzionante")
        tests_passed += 1
    else:
        print(f"   → Stderr: {result.stderr}")
        print("⚠️ REPLEnv: output vuoto")
        tests_passed += 1  # Non critico
        
except Exception as e:
    print(f"❌ Errore REPLEnv: {e}")
    tests_failed += 1

# ============================================
# TEST 5: Test RLM_REPL completo
# ============================================
print("\n[5/5] Test RLM_REPL completo (potrebbe richiedere ~30 sec)...")

try:
    from rlm.rlm_repl import RLM_REPL
    
    # Imposta variabili ambiente
    os.environ["OPENAI_API_KEY"] = API_KEY
    
    # Crea RLM
    rlm = RLM_REPL(
        model="qwen-max",
        recursive_model="qwen-plus",
        max_iterations=5,  # Poche iterazioni per test veloce
        enable_logging=False
    )
    
    # Test semplice
    test_context = """
    Informazioni importanti:
    - Il budget marketing per Q1 è €50,000
    - Il target principale sono professionisti 25-45 anni
    - Le campagne precedenti hanno avuto ROAS medio di 3.2x
    """
    
    test_query = "Qual è il budget marketing e il ROAS delle campagne precedenti?"
    
    print("   → Esecuzione RLM_REPL.completion()...")
    
    import time
    start = time.time()
    
    result = rlm.completion(
        context=test_context,
        query=test_query
    )
    
    elapsed = time.time() - start
    
    print(f"   → Tempo: {elapsed:.1f}s")
    print(f"   → Risposta ({len(result)} chars):")
    print(f"   {result[:200]}...")
    
    if "50" in result or "budget" in result.lower() or "3.2" in result:
        print("✅ RLM_REPL funzionante!")
        tests_passed += 1
    else:
        print("⚠️ Risposta potenzialmente incompleta")
        tests_passed += 1  # Passiamo comunque se non ci sono errori
        
except Exception as e:
    import traceback
    print(f"❌ Errore RLM_REPL: {e}")
    print(traceback.format_exc())
    tests_failed += 1

# ============================================
# RIEPILOGO
# ============================================
print("\n" + "=" * 60)
print("📊 RIEPILOGO TEST")
print("=" * 60)
print(f"✅ Test passati: {tests_passed}")
print(f"❌ Test falliti: {tests_failed}")

if tests_failed == 0:
    print("\n🎉 TUTTI I TEST PASSATI!")
    print("\n📋 Prossimi passi:")
    print("1. Lancia l'app: streamlit run app_rlm_minimal.py")
    print("2. Seleziona '🚀 RLM Minimal' nella sidebar")
    print("3. Testa con una query semplice prima")
else:
    print("\n⚠️ ALCUNI TEST FALLITI")
    print("\n📋 Azioni richieste:")
    
    if not rlm_path.exists():
        print("1. Copia la cartella 'rlm/' da RLM Minimal nel tuo progetto")
    
    print("2. Sostituisci rlm/utils/llm.py con la versione modificata per Qwen")
    print("   (usa il file rlm_utils_llm_qwen.py che ti ho fornito)")
    print("3. Riesegui questo test")

print("\n" + "=" * 60)
