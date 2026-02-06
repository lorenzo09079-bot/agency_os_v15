# -*- coding: utf-8 -*-
"""
Tools v15 - Agency OS
=====================
Funzioni per esplorare il database Qdrant.
Tutte le configurazioni vengono da config.py.
"""

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from typing import Optional, List, Dict, Any
from collections import defaultdict

from config import QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME, ENCODER_MODEL

# ============================================
# INIZIALIZZAZIONE
# ============================================

print(f"Tools v15: Connessione a {QDRANT_HOST}:{QDRANT_PORT}...")

try:
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=30)
    qdrant.get_collections()
    print("Tools v15: ✅ Connesso!")
except Exception as e:
    print(f"Tools v15: ❌ Qdrant non raggiungibile: {e}")
    qdrant = None

encoder = SentenceTransformer(ENCODER_MODEL)


# ============================================
# HELPER
# ============================================

def _normalize_filename(filename_or_dict) -> str:
    """Accetta sia stringa che dict e restituisce il filename."""
    if isinstance(filename_or_dict, dict):
        return filename_or_dict.get('filename', str(filename_or_dict))
    return str(filename_or_dict)


def _check_qdrant():
    """Verifica connessione Qdrant."""
    if qdrant is None:
        return False
    return True


# ============================================
# ESPLORAZIONE DATABASE
# ============================================

def list_all_tags() -> Dict[str, int]:
    """Restituisce tutti i tag nel database con il conteggio dei chunks."""
    if not _check_qdrant():
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
                    tags_count[point.payload["client_name"]] += 1
            
            if offset is None:
                break
        
        return dict(sorted(tags_count.items()))
    except Exception as e:
        return {"error": str(e)}


def list_files_by_tag(tag: str) -> List[Dict[str, Any]]:
    """Elenca tutti i file associati a un tag."""
    if not _check_qdrant():
        return [{"error": "Connessione Qdrant non disponibile"}]
    
    try:
        tag = tag.upper().strip()
        qdrant_filter = models.Filter(
            must=[models.FieldCondition(
                key="client_name", match=models.MatchValue(value=tag)
            )]
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
                    fn = point.payload.get("filename", "Unknown")
                    files_info[fn]["chunks"] += 1
                    files_info[fn]["doc_type"] = point.payload.get("doc_type", "")
                    files_info[fn]["date"] = point.payload.get("date", "")[:10]
            
            if offset is None:
                break
        
        result = [
            {"filename": fn, **info}
            for fn, info in sorted(files_info.items())
        ]
        return result if result else [{"message": f"Nessun file con tag '{tag}'"}]
    except Exception as e:
        return [{"error": str(e)}]


def get_file_content(filename, max_chunks: int = 50) -> str:
    """Recupera il contenuto completo di un file specifico."""
    if not _check_qdrant():
        return "ERRORE: Connessione Qdrant non disponibile"
    
    filename = _normalize_filename(filename)
    
    try:
        qdrant_filter = models.Filter(
            must=[models.FieldCondition(
                key="filename", match=models.MatchValue(value=filename)
            )]
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
            chunks.append((payload.get("chunk_index", 0), payload.get("text", "")))
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


def get_database_stats() -> Dict[str, Any]:
    """Statistiche complete del database."""
    if not _check_qdrant():
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
                    tags_count[tag] += 1
                    files_per_tag[tag].add(point.payload.get("filename", "unknown"))
                    doc_types[point.payload.get("doc_type", "N/A")] += 1
            
            if offset is None:
                break
        
        return {
            "total_chunks": info.points_count,
            "total_files": sum(len(f) for f in files_per_tag.values()),
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
    """Trova tag che contengono una keyword."""
    all_tags = list_all_tags()
    if "error" in all_tags:
        return []
    keyword_lower = keyword.lower()
    return sorted([tag for tag in all_tags if keyword_lower in tag.lower()])


# ============================================
# RICERCA
# ============================================

def search_semantic(query: str, tag_filter: Optional[str] = None, top_k: int = 10) -> List[Dict[str, Any]]:
    """Ricerca semantica nel database."""
    if not _check_qdrant():
        return [{"error": "Connessione Qdrant non disponibile"}]
    
    try:
        vector = encoder.encode(query).tolist()
        
        qdrant_filter = None
        if tag_filter:
            tag_filter = tag_filter.upper().strip()
            qdrant_filter = models.Filter(
                must=[models.FieldCondition(
                    key="client_name", match=models.MatchValue(value=tag_filter)
                )]
            )
        
        hits = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=top_k
        )
        
        if not hits:
            return [{"message": "Nessun risultato trovato"}]
        
        return [
            {
                "score": round(hit.score, 3),
                "filename": hit.payload.get("filename", "Unknown"),
                "tag": hit.payload.get("client_name", "N/A"),
                "doc_type": hit.payload.get("doc_type", ""),
                "content": hit.payload.get("text", "")[:500]
            }
            for hit in hits
        ]
    except Exception as e:
        return [{"error": str(e)}]


def search_by_keyword(keyword: str, tag_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ricerca per parola chiave esatta nel testo."""
    if not _check_qdrant():
        return [{"error": "Connessione Qdrant non disponibile"}]
    
    try:
        keyword_lower = keyword.lower()
        
        qdrant_filter = None
        if tag_filter:
            qdrant_filter = models.Filter(
                must=[models.FieldCondition(
                    key="client_name", match=models.MatchValue(value=tag_filter.upper().strip())
                )]
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
                text = point.payload.get("text", "")
                if keyword_lower in text.lower():
                    results.append({
                        "filename": point.payload.get("filename", "Unknown"),
                        "tag": point.payload.get("client_name", "N/A"),
                        "doc_type": point.payload.get("doc_type", ""),
                        "content": text[:300]
                    })
                    if len(results) >= 20:
                        break
            
            if offset is None:
                break
        
        return results if results else [{"message": f"Nessun risultato per '{keyword}'"}]
    except Exception as e:
        return [{"error": str(e)}]


def search_memory(query: str, client_filter: str = None, top_k: int = 7) -> str:
    """Ricerca formattata (legacy compatibility)."""
    results = search_semantic(query, client_filter, top_k)
    
    if not results or (len(results) == 1 and "error" in results[0]):
        return "SYSTEM: Nessun dato trovato nel database."
    
    output = ["--- DATI RECUPERATI ---"]
    output.append(f"Query: '{query}' | Filtro: {client_filter or 'nessuno'}\n")
    
    for i, r in enumerate(results, 1):
        if "error" in r or "message" in r:
            continue
        output.append(f"[{i}] Score: {r['score']}")
        output.append(f"Fonte: {r['filename']} | Tag: {r['tag']}")
        output.append(f"Contenuto: {r['content']}\n")
    
    output.append("--- FINE DATI ---")
    return "\n".join(output)
