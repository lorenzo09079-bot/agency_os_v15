from qdrant_client import QdrantClient

# Configurazione
IP_ZENBOOK = "192.168.1.6"
client = QdrantClient(host=IP_ZENBOOK, port=6333)
COLLECTION = "agenzia_memory"

print(f"📚 INVENTARIO COMPLETO DATABASE ({IP_ZENBOOK})")
print("-" * 50)

try:
    # 1. Recupera Info Totali
    count = client.count(COLLECTION).count
    print(f"📦 Totale Frammenti (Vettori): {count}")
    
    # 2. Scansiona per trovare i nomi univoci dei file
    # (Qdrant non ha una funzione 'SELECT DISTINCT', quindi li raccogliamo noi)
    unique_files = {} # Dizionario per contare i chunk per file
    
    next_offset = None
    scanned = 0
    
    print("⏳ Scansione in corso (potrebbe volerci qualche secondo)...")
    
    while True:
        # Scarica a pacchetti di 200 per non intasare la RAM
        records, next_offset = client.scroll(
            collection_name=COLLECTION,
            limit=200,
            offset=next_offset,
            with_payload=True,
            with_vectors=False
        )
        
        for point in records:
            name = point.payload.get("filename", "Sconosciuto")
            tag = point.payload.get("client_name", "Nessun Tag")
            
            # Crea una chiave univoca (Nome + Tag)
            key = f"{name}  [Tag: {tag}]"
            unique_files[key] = unique_files.get(key, 0) + 1
            
        scanned += len(records)
        if next_offset is None or scanned >= count:
            break

    print("-" * 50)
    print(f"✅ TROVATI {len(unique_files)} DOCUMENTI UNICI:\n")
    
    for filename, chunks in unique_files.items():
        print(f"📄 {filename} ({chunks} frammenti)")
        
    print("-" * 50)

except Exception as e:
    print(f"❌ Errore: {e}")