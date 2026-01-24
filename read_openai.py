import os

# Percorso che abbiamo trovato prima
path = r"C:\Users\loren\Documents\AI Test\AI_Lab\rlm\rlm\clients\openai.py"

print(f"📖 Leggo: {path}\n")
print("-" * 40)

try:
    with open(path, "r", encoding="utf-8") as f:
        # Leggo le prime 50 righe (bastano per vedere gli import e la classe)
        print(f.read()) 
except Exception as e:
    print(f"Errore lettura: {e}")