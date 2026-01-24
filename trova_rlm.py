import os

print("🕵️‍♂️ Avvio investigazione file...")
cartella_base = os.path.join(os.getcwd(), "rlm")

if not os.path.exists(cartella_base):
    print(f"❌ ERRORE: La cartella {cartella_base} non esiste!")
else:
    trovato = False
    for root, dirs, files in os.walk(cartella_base):
        for file in files:
            if file.endswith(".py"):
                path_completo = os.path.join(root, file)
                try:
                    with open(path_completo, "r", encoding="utf-8", errors="ignore") as f:
                        contenuto = f.read()
                        if "class RLM" in contenuto:
                            print(f"\n✅ TROVATO! La classe RLM è qui:")
                            print(f"📂 File: {path_completo}")
                            # Mostriamo le prime righe per capire come importarlo
                            print(f"📝 Prime righe del file:\n{'-'*20}")
                            print(contenuto[:200])
                            trovato = True
                except Exception as e:
                    print(f"⚠️ Non riesco a leggere {file}: {e}")

    if not trovato:
        print("\n❌ NON TROVATO. Nessun file contiene 'class RLM'.")
        print("Forse la classe ha un nome diverso? (es. Agent, Model, Engine?)")