import sys
from qdrant_client import QdrantClient

# --- CONFIGURAZIONE ---
# Assicurati che questo sia l'IP corretto dello Zenbook
IP_ZENBOOK = "192.168.1.4" 
PORT = 6333
COLLECTION_NAME = "agenzia_memory" # Il nome standard usato dal tuo sistema

def main():
    print(f"\n🔌 Tentativo di connessione a {IP_ZENBOOK}:{PORT}...")
    
    try:
        client = QdrantClient(host=IP_ZENBOOK, port=PORT, timeout=5)
        
        # 1. Verifica che la collezione esista
        collections = client.get_collections()
        available_names = [c.name for c in collections.collections]
        
        if COLLECTION_NAME not in available_names:
            print(f"❌ ERRORE: La collezione '{COLLECTION_NAME}' non esiste!")
            print(f"   Collezioni trovate: {available_names}")
            print("   (Se è vuoto, carica il primo file per crearla)")
            return

        # 2. Ottieni statistiche generali
        info = client.get_collection(COLLECTION_NAME)
        print(f"\n📊 STATO DEL DATABASE")
        print(f"---------------------")
        print(f"✅ Status: {info.status}")
        print(f"🧠 Totale Frammenti (Vectors): {info.points_count}")
        print(f"---------------------\n")

        # 3. Scarica gli ultimi 10 punti (Scroll)
        # Qdrant non ha un ordine cronologico nativo perfetto senza timestamp, 
        # ma lo scroll di solito mostra i dati inseriti.
        print("🔍 ANALISI ULTIMI 10 FRAMMENTI (Payload Check):")
        
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=10,
            with_payload=True,
            with_vectors=False
        )

        if not points:
            print("⚠️ Il database è vuoto o non ci sono punti.")
            return

        for point in points:
            payload = point.payload
            
            # Recupero dati, gestendo chiavi mancanti
            filename = payload.get('filename', 'SENZA NOME')
            # NOTA: Nel tuo app.py salvi il TAG nel campo 'client_name'
            tag = payload.get('client_name', 'NESSUN TAG') 
            doc_type = payload.get('doc_type', 'N/D')
            content = payload.get('text', '')

            # Pulizia anteprima testo
            preview = content[:150].replace('\n', ' ') if content else "[ ⚠️ CONTENUTO VUOTO O NULLO ]"
            
            print(f"📄 File: {filename}")
            print(f"🏷️  Tag:  {tag}") 
            print(f"📂 Tipo: {doc_type}")
            print(f"📝 Contenuto: \"{preview}...\"")
            print("-" * 50)

    except Exception as e:
        print(f"\n❌ ERRORE CRITICO DI CONNESSIONE:")
        print(f"{e}")
        print("\nSuggerimenti:")
        print("1. Lo Zenbook è acceso?")
        print("2. Docker è attivo? (docker ps)")
        print("3. L'IP 192.168.1.4 è ancora corretto?")

if __name__ == "__main__":
    main()