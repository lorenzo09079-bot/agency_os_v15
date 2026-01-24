# test_manuale.py
import tools
import time

print("🧪 INIZIO TEST MANUALE ACER...")

# 1. Test Ricerca Web
print("\n[1/2] Chiamo tools.search_web('Elon Musk')...")
try:
    risultato = tools.search_web("Elon Musk ultimissime")
    print(f"✅ RISULTATO DALL'ACER:\n{risultato[:200]}...") # Primi 200 caratteri
except Exception as e:
    print(f"❌ ERRORE WEB: {e}")

print("\n" + "="*30 + "\n")

# 2. Test Memoria
print("[2/2] Chiamo tools.lookup_memory('Elon Musk')...")
try:
    memoria = tools.lookup_memory("Elon Musk")
    print(f"✅ RISULTATO DALLO ZENBOOK:\n{memoria[:200]}...")
except Exception as e:
    print(f"❌ ERRORE MEMORIA: {e}")

print("\n🧪 TEST FINITO.")