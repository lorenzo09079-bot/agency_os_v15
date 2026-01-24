# -*- coding: utf-8 -*-
"""
Tools v2.0 - Ricerca Memoria Aziendale
Per Agency OS v5.0

FIX: Usa il campo corretto 'client_name' invece di 'client'
"""
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

# --- CONFIGURAZIONE ---
IP_ZENBOOK = "http://192.168.1.4:6333"
COLLECTION_NAME = "agenzia_memory"

print(f"Init Tools v2: Connessione a Zenbook ({IP_ZENBOOK})...")
encoder = SentenceTransformer('all-MiniLM-L6-v2')
qdrant = QdrantClient(url=IP_ZENBOOK)
print("Tools v2: Connesso!")

# --- MAPPING SHORTCUT ---
TAG_SHORTCUTS = {
    "ads": "RESEARCH_ADS",
    "advertising": "RESEARCH_ADS",
    "social": "RESEARCH_SOCIAL",
    "copy": "RESEARCH_COPY",
    "copywriting": "RESEARCH_COPY",
}


def normalize_filter(filter_input: str) -> str:
    """Normalizza il filtro al formato database."""
    if not filter_input:
        return None
    
    clean = filter_input.strip().lower()
    
    if clean in ["nessuno", "none", "null", ""]:
        return None
    
    # Cerca shortcut
    if clean in TAG_SHORTCUTS:
        return TAG_SHORTCUTS[clean]
    
    # Altrimenti usa uppercase
    return filter_input.strip().upper()


def search_memory(query: str, client_filter: str = None) -> str:
    """
    Esegue una ricerca semantica su Zenbook.
    
    Args:
        query: Testo da cercare
        client_filter: Tag per filtrare (RESEARCH_ADS, ads, social, etc.)
    
    Returns:
        Risultati formattati
    """
    try:
        # Normalizza filtro
        db_filter = normalize_filter(client_filter)
        
        print(f"SEARCH: Query='{query}' | Filter='{client_filter}' -> '{db_filter}'")
        
        vector = encoder.encode(query).tolist()
        
        # Costruisci filtro Qdrant
        qdrant_filter = None
        if db_filter:
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="client_name",  # CORRETTO: era "client"
                        match=models.MatchValue(value=db_filter)
                    )
                ]
            )

        hits = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=7
        )

        if not hits:
            return "SYSTEM: Nessun dato trovato nel database per questa ricerca."

        context_str = f"--- INIZIO DATI RECUPERATI DAL DB AZIENDALE ---\n"
        context_str += f"Query: '{query}' | Filtro: {db_filter or 'nessuno'}\n\n"
        
        for i, hit in enumerate(hits, 1):
            p = hit.payload
            context_str += f"[{i}] Score: {hit.score:.3f}\n"
            context_str += f"Fonte: {p.get('filename')} | Tag: {p.get('client_name')}\n"
            context_str += f"Contenuto: {p.get('text')}\n\n"
        
        context_str += "--- FINE DATI RECUPERATI ---\n"
        
        return context_str

    except Exception as e:
        return f"SYSTEM ERROR: Errore connessione a Zenbook: {str(e)}"


# Test se eseguito direttamente
if __name__ == "__main__":
    print("\nTest ricerca:")
    result = search_memory("strategie Meta Ads", "ads")
    print(result[:500] + "...")
