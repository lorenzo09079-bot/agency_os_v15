from qdrant_client import QdrantClient
from qdrant_client.http import models

IP_ZENBOOK = "192.168.1.4"
client = QdrantClient(host=IP_ZENBOOK, port=6333)
COLLECTION_NAME = "agenzia_memory"

try:
    print(f"🔥 Eliminazione collezione '{COLLECTION_NAME}' su {IP_ZENBOOK}...")
    client.delete_collection(COLLECTION_NAME)
    print("✅ Collezione eliminata.")
    
    print("✨ Ricreazione collezione pulita...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )
    print("✅ Database resettato e pronto!")
except Exception as e:
    print(f"❌ Errore: {e}")