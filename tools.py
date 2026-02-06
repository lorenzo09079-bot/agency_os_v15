# -*- coding: utf-8 -*-
"""
Tools v5.1 - Agency OS v14
==========================
Fix: get_file_content() ora accetta sia stringa che dict

Funzioni per esplorare autonomamente il database Qdrant.
"""
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from typing import Optional, List, Dict, Any
from collections import defaultdict

# ============================================
# CONFIGURAZIONE
# ============================================
try:
    from config import QDRANT_URL, QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME
except ImportError:
    QDRANT_HOST = "192.168.1.6"
    QDRANT_PORT = 6333
    QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
    COLLECTION_NAME = "agenzia_memory"

# ============================================
# INIZIALIZZAZIONE
# ============================================
print(f"Tools v5.1: Connessione a {QDRANT_HOST}:{QDRANT_PORT}...")

try:
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=30)
    qdrant.get_collections()
    print("Tools v5.1: ✅ Connesso!")
except Exception as e:
    print(f"Tools v5.1: ❌ ERRORE connessione Qdrant: {e}")
    qdrant = None

encoder = SentenceTransformer("all-MiniLM-L6-v2")


# ============================================
# HELPER: Normalizza filename
# ============================================

def _normalize_filename(filename_or_dict) -> str:
    """
    Accetta sia una stringa che un dict e restituisce il filename.
    Fix per quando l'AI passa il dict intero invece di filename.
    """
    if isinstance(filename_or_dict, dict):
        return filename_or_dict.get('filename', str(filename_or_dict))
    return str(filename_or_dict)


# ============================================
# FUNZIONI DI ESPLORAZIONE
# ============================================

def list_all_tags() -> Dict[str, int]:
    """
    Restituisce TUTTI i tag nel database con il conteggio dei chunks.
    
    Returns:
        Dict con tag -> numero di chunks
    """
    if qdrant is None:
        return {"error": "Connessione Qdrant non disponibile"}
    
    try:
        tags_count = defaultdict(int)
        offset = None
        
        while True:
            results, offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=["client_name"]
            )
            
            for point in results:
                if point.payload and "client_name" in point.payload:
                    tag = point.payload["client_name"]
                    tags_count[tag] += 1
            
            if offset is None:
                break
        
        return dict(sorted(tags_count.items()))
    
    except Exception as e:
        return {"error": str(e)}


def list_files_by_tag(tag: str) -> List[Dict[str, Any]]:
    """
    Elenca TUTTI i file unici associati a un tag specifico.
    
    Args:
        tag: Il tag da cercare (es. "DATI_EUROITALIA_METAADS")
    
    Returns:
        Lista di dict con info su ogni file
    """
    if qdrant is None:
        return [{"error": "Connessione Qdrant non disponibile"}]
    
    try:
        tag = tag.upper().strip()
        
        qdrant_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="client_name",
                    match=models.MatchValue(value=tag)
                )
            ]
        )
        
        files_info = defaultdict(lambda: {"chunks": 0, "doc_type": "", "date": ""})
        offset = None
        
        while True:
            results, offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=qdrant_filter,
                limit=100,
                offset=offset,
                with_payload=["filename", "doc_type", "date"]
            )
            
            for point in results:
                if point.payload:
                    filename = point.payload.get("filename", "Unknown")
                    files_info[filename]["chunks"] += 1
                    files_info[filename]["doc_type"] = point.payload.get("doc_type", "")
                    files_info[filename]["date"] = point.payload.get("date", "")[:10]
            
            if offset is None:
                break
        
        result = []
        for filename, info in sorted(files_info.items()):
            result.append({
                "filename": filename,
                "chunks": info["chunks"],
                "doc_type": info["doc_type"],
                "date": info["date"]
            })
        
        return result if result else [{"message": f"Nessun file trovato con tag '{tag}'"}]
    
    except Exception as e:
        return [{"error": str(e)}]


def get_file_content(filename, max_chunks: int = 50) -> str:
    """
    Recupera il CONTENUTO COMPLETO di un file specifico.
    
    Args:
        filename: Nome del file (stringa) OPPURE dict con chiave 'filename'
        max_chunks: Massimo numero di chunks da recuperare
    
    Returns:
        Testo completo del file
    """
    if qdrant is None:
        return "ERRORE: Connessione Qdrant non disponibile"
    
    # FIX: Normalizza input (accetta sia stringa che dict)
    filename = _normalize_filename(filename)
    
    try:
        qdrant_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="filename",
                    match=models.MatchValue(value=filename)
                )
            ]
        )
        
        results, _ = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=qdrant_filter,
            limit=max_chunks,
            with_payload=["text", "chunk_index", "client_name", "doc_type"]
        )
        
        if not results:
            return f"File '{filename}' non trovato nel database."
        
        chunks = []
        metadata = {}
        
        for point in results:
            payload = point.payload
            text = payload.get("text", "")
            idx = payload.get("chunk_index", 0)
            chunks.append((idx, text))
            
            if not metadata:
                metadata = {
                    "tag": payload.get("client_name", ""),
                    "doc_type": payload.get("doc_type", "")
                }
        
        chunks.sort(key=lambda x: x[0])
        full_text = "\n\n".join([c[1] for c in chunks])
        
        header = f"=== FILE: {filename} ===\n"
        header += f"Tag: {metadata.get('tag', 'N/A')} | Tipo: {metadata.get('doc_type', 'N/A')}\n"
        header += f"Chunks: {len(chunks)}\n"
        header += "=" * 50 + "\n\n"
        
        return header + full_text
    
    except Exception as e:
        return f"ERRORE: {str(e)}"


def search_semantic(query: str, tag_filter: Optional[str] = None, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Ricerca SEMANTICA nel database.
    
    Args:
        query: Cosa cercare
        tag_filter: Opzionale - limita a un tag specifico
        top_k: Numero di risultati
    
    Returns:
        Lista di dict con risultati ordinati per rilevanza
    """
    if qdrant is None:
        return [{"error": "Connessione Qdrant non disponibile"}]
    
    try:
        vector = encoder.encode(query).tolist()
        
        qdrant_filter = None
        if tag_filter:
            tag_filter = tag_filter.upper().strip()
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="client_name",
                        match=models.MatchValue(value=tag_filter)
                    )
                ]
            )
        
        hits = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=top_k
        )
        
        if not hits:
            return [{"message": "Nessun risultato trovato"}]
        
        results = []
        for hit in hits:
            payload = hit.payload
            results.append({
                "score": round(hit.score, 3),
                "filename": payload.get("filename", "Unknown"),
                "tag": payload.get("client_name", "N/A"),
                "doc_type": payload.get("doc_type", ""),
                "content": payload.get("text", "")[:500] + "..." if len(payload.get("text", "")) > 500 else payload.get("text", "")
            })
        
        return results
    
    except Exception as e:
        return [{"error": str(e)}]


def search_by_keyword(keyword: str, tag_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Ricerca per PAROLA CHIAVE esatta nel testo.
    
    Args:
        keyword: Parola da cercare (case-insensitive)
        tag_filter: Opzionale - limita a un tag specifico
    
    Returns:
        Lista di risultati che contengono la keyword
    """
    if qdrant is None:
        return [{"error": "Connessione Qdrant non disponibile"}]
    
    try:
        keyword_lower = keyword.lower()
        
        qdrant_filter = None
        if tag_filter:
            tag_filter = tag_filter.upper().strip()
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="client_name",
                        match=models.MatchValue(value=tag_filter)
                    )
                ]
            )
        
        results = []
        offset = None
        
        while len(results) < 20:
            batch, offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=qdrant_filter,
                limit=100,
                offset=offset,
                with_payload=["text", "filename", "client_name", "doc_type"]
            )
            
            for point in batch:
                payload = point.payload
                text = payload.get("text", "")
                
                if keyword_lower in text.lower():
                    results.append({
                        "filename": payload.get("filename", "Unknown"),
                        "tag": payload.get("client_name", "N/A"),
                        "doc_type": payload.get("doc_type", ""),
                        "content": text[:300] + "..." if len(text) > 300 else text
                    })
                    
                    if len(results) >= 20:
                        break
            
            if offset is None:
                break
        
        return results if results else [{"message": f"Nessun risultato contenente '{keyword}'"}]
    
    except Exception as e:
        return [{"error": str(e)}]


def get_database_stats() -> Dict[str, Any]:
    """
    Statistiche complete del database.
    
    Returns:
        Dict con statistiche complete
    """
    if qdrant is None:
        return {"error": "Connessione Qdrant non disponibile"}
    
    try:
        info = qdrant.get_collection(COLLECTION_NAME)
        
        tags_count = defaultdict(int)
        files_per_tag = defaultdict(set)
        doc_types = defaultdict(int)
        
        offset = None
        while True:
            results, offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=["client_name", "filename", "doc_type"]
            )
            
            for point in results:
                if point.payload:
                    tag = point.payload.get("client_name", "UNKNOWN")
                    filename = point.payload.get("filename", "unknown")
                    doc_type = point.payload.get("doc_type", "N/A")
                    
                    tags_count[tag] += 1
                    files_per_tag[tag].add(filename)
                    doc_types[doc_type] += 1
            
            if offset is None:
                break
        
        return {
            "total_chunks": info.points_count,
            "total_files": sum(len(files) for files in files_per_tag.values()),
            "total_tags": len(tags_count),
            "tags": {
                tag: {
                    "chunks": count,
                    "files": len(files_per_tag[tag]),
                    "file_list": sorted(list(files_per_tag[tag]))
                }
                for tag, count in sorted(tags_count.items())
            },
            "doc_types": dict(doc_types)
        }
    
    except Exception as e:
        return {"error": str(e)}


def find_related_tags(keyword: str) -> List[str]:
    """
    Trova tag che contengono una keyword.
    
    Args:
        keyword: Parola chiave da cercare nei nomi dei tag
    
    Returns:
        Lista di tag che contengono la keyword
    """
    all_tags = list_all_tags()
    
    if "error" in all_tags:
        return []
    
    keyword_lower = keyword.lower()
    related = [tag for tag in all_tags.keys() if keyword_lower in tag.lower()]
    
    return sorted(related)


# ============================================
# FUNZIONE LEGACY
# ============================================

def search_memory(query: str, client_filter: str = None, top_k: int = 7) -> str:
    """Funzione legacy per compatibilità."""
    results = search_semantic(query, client_filter, top_k)
    
    if not results or (len(results) == 1 and "error" in results[0]):
        return "SYSTEM: Nessun dato trovato nel database."
    
    output = ["--- INIZIO DATI RECUPERATI ---"]
    output.append(f"Query: '{query}' | Filtro: {client_filter or 'nessuno'}\n")
    
    for i, r in enumerate(results, 1):
        if "error" in r or "message" in r:
            continue
        output.append(f"[{i}] Score: {r['score']}")
        output.append(f"Fonte: {r['filename']} | Tag: {r['tag']}")
        output.append(f"Contenuto: {r['content']}\n")
    
    output.append("--- FINE DATI RECUPERATI ---")
    
    return "\n".join(output)


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("TEST TOOLS v5.1")
    print("=" * 50)
    
    if qdrant:
        print("\n1. Test list_all_tags():")
        tags = list_all_tags()
        print(f"   Tag: {tags}")
        
        print("\n2. Test get_file_content() con dict (FIX):")
        test_dict = {"filename": "test.csv", "chunks": 1}
        normalized = _normalize_filename(test_dict)
        print(f"   Input dict: {test_dict}")
        print(f"   Normalized: {normalized}")
        
        print("\n✅ Test completati!")
