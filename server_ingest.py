# -*- coding: utf-8 -*-
"""
Server Ingest v1.5 - Fix Minimale + Preparazione Future Features
Per Acer (Debian) - Agency OS

MODIFICHE DA v1.0:
- Testo PIU PULITO (tag solo a inizio chunk, non ripetuto ovunque)
- Aggiunto campo 'client' duplicato per compatibilita con tools.py
- Overlap nei chunk per mantenere contesto
- Endpoint /health e /stats
- Pronto per future feature (profili cliente, etc.)

INSTALLAZIONE:
pip install fastapi uvicorn qdrant-client sentence-transformers pymupdf python-docx pandas
"""
import os
import uvicorn
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF
import pandas as pd
import docx
from datetime import datetime
from typing import Optional

# --- CONFIGURAZIONE ---
app = FastAPI(title="Agency OS Ingester v1.5")

IP_ZENBOOK = "192.168.1.4"
PORT_ZENBOOK = 6333
COLLECTION_NAME = "agenzia_memory"
MODEL_NAME = "all-MiniLM-L6-v2"

print("=" * 50)
print("Agency OS Ingester v1.5")
print("=" * 50)
print(f"Qdrant: {IP_ZENBOOK}:{PORT_ZENBOOK}")
print(f"Collection: {COLLECTION_NAME}")
print("Inizializzazione...")

encoder = SentenceTransformer(MODEL_NAME)
qdrant = QdrantClient(host=IP_ZENBOOK, port=PORT_ZENBOOK, check_compatibility=False)

print("Server Pronto!")
print("=" * 50)


# --- ESTRAZIONE TESTO ---
def extract_text(file_path: str, filename: str) -> str:
    """
    Estrae il testo dal documento.
    Versione pulita: niente tag ripetuti dentro il contenuto.
    """
    text = ""
    
    try:
        if filename.endswith(".pdf"):
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc, 1):
                    page_text = page.get_text().strip()
                    if page_text:
                        text += f"\n[Pagina {page_num}]\n{page_text}\n"
        
        elif filename.endswith(".docx"):
            doc = docx.Document(file_path)
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())
            text = "\n\n".join(paragraphs)
        
        elif filename.endswith((".txt", ".md", ".py", ".json")):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        
        elif filename.endswith((".xlsx", ".xls", ".csv")):
            # Per Excel/CSV: formato strutturato ma leggibile
            if filename.endswith(".csv"):
                df = pd.read_csv(file_path, dtype=str)
            else:
                df = pd.read_excel(file_path, dtype=str)
            
            df.fillna("", inplace=True)
            
            # Header con nomi colonne
            columns = df.columns.tolist()
            text = f"TABELLA DATI - Colonne: {', '.join(columns)}\n\n"
            
            # Ogni riga come record leggibile
            for idx, row in df.iterrows():
                row_parts = []
                for col in columns:
                    val = str(row[col]).strip()
                    if val and val.lower() not in ["nan", "n/a", "none", ""]:
                        row_parts.append(f"{col}: {val}")
                
                if row_parts:
                    text += f"Riga {idx + 1}: {', '.join(row_parts)}\n"
        
        else:
            # Tipo file non supportato, prova come testo
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except:
                return ""
    
    except Exception as e:
        print(f"Errore estrazione: {e}")
        return ""
    
    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """
    Divide il testo in chunk con overlap per mantenere contesto.
    """
    words = text.split()
    chunks = []
    
    if len(words) <= chunk_size:
        return [text] if text.strip() else []
    
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        
        if chunk_text.strip():
            chunks.append(chunk_text)
        
        # Avanza con overlap
        i += chunk_size - overlap
    
    return chunks


# --- ENDPOINT PRINCIPALE ---
@app.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    client_name: str = Form(...),
    doc_type: str = Form(...)
):
    """
    Indicizza un documento nel database vettoriale.
    
    Parametri:
    - file: Il documento (PDF, DOCX, TXT, XLSX, CSV, MD)
    - client_name: Tag/categoria (es. RESEARCH_ADS, CLIENT_NIKE, CHAT_NIKE)
    - doc_type: Tipo documento (Strategia, Ricerca, Meeting, Report, Chat History)
    """
    print(f"\n{'='*50}")
    print(f"INGEST: {file.filename}")
    print(f"Tag: {client_name} | Tipo: {doc_type}")
    
    # Normalizza il tag (uppercase, no spazi)
    tag = client_name.strip().upper().replace(" ", "_")
    
    # Salva file temporaneo
    temp_filename = f"temp_{uuid.uuid4()}_{file.filename}"
    
    try:
        with open(temp_filename, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Estrai testo
        raw_text = extract_text(temp_filename, file.filename)
        
        if not raw_text or len(raw_text) < 10:
            raise HTTPException(status_code=400, detail="File vuoto o non leggibile")
        
        print(f"Testo estratto: {len(raw_text)} caratteri")
        
        # Crea chunks
        chunks = chunk_text(raw_text, chunk_size=500, overlap=50)
        print(f"Chunks creati: {len(chunks)}")
        
        # Prepara punti per Qdrant
        points = []
        timestamp = datetime.now().isoformat()
        
        for i, chunk in enumerate(chunks):
            # Aggiungi contesto minimo al chunk (solo header, non ripetuto)
            chunk_with_context = f"[{tag}] [Fonte: {file.filename}]\n{chunk}"
            
            vector = encoder.encode(chunk_with_context).tolist()
            
            payload = {
                # Campi principali
                "filename": file.filename,
                "text": chunk,  # Testo pulito senza tag
                
                # Tag - ENTRAMBI i campi per compatibilita
                "client_name": tag,  # Usato dal nuovo codice
                "client": tag,       # Usato dal vecchio tools.py
                
                # Metadata
                "doc_type": doc_type,
                "date": timestamp,
                "chunk_index": i,
                "total_chunks": len(chunks),
                
                # Preparazione per future feature
                "category": None,    # Verra popolato da AI classification
                "topic": None,
                "project": None,     # Per collegare a progetti/clienti
            }
            
            points.append(models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload
            ))
        
        # Upsert in Qdrant
        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"Indicizzati: {len(points)} chunks")
            print(f"{'='*50}\n")
            
            return {
                "status": "success",
                "filename": file.filename,
                "tag": tag,
                "chunks": len(points),
                "characters": len(raw_text)
            }
        
        raise HTTPException(status_code=500, detail="Nessun chunk creato")
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERRORE: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Pulizia file temporaneo
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


# --- ENDPOINT UTILITA ---
@app.get("/health")
async def health_check():
    """Verifica che il server sia attivo."""
    try:
        # Test connessione Qdrant
        info = qdrant.get_collection(COLLECTION_NAME)
        qdrant_ok = True
        points = info.points_count
    except:
        qdrant_ok = False
        points = 0
    
    return {
        "status": "healthy" if qdrant_ok else "degraded",
        "version": "1.5",
        "qdrant_connected": qdrant_ok,
        "total_points": points
    }


@app.get("/stats")
async def get_stats():
    """Statistiche del database."""
    try:
        info = qdrant.get_collection(COLLECTION_NAME)
        
        # Conta documenti per tag
        results = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        tags_count = {}
        docs_count = {}
        
        for point in results[0]:
            tag = point.payload.get("client_name", "UNKNOWN")
            filename = point.payload.get("filename", "unknown")
            
            tags_count[tag] = tags_count.get(tag, 0) + 1
            
            if tag not in docs_count:
                docs_count[tag] = set()
            docs_count[tag].add(filename)
        
        # Formatta output
        tags_summary = {
            tag: {
                "chunks": count,
                "documents": len(docs_count.get(tag, set()))
            }
            for tag, count in tags_count.items()
        }
        
        return {
            "collection": COLLECTION_NAME,
            "total_chunks": info.points_count,
            "total_documents": sum(len(d) for d in docs_count.values()),
            "tags": tags_summary
        }
    
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    """Homepage con info base."""
    return {
        "name": "Agency OS Ingester",
        "version": "1.5",
        "endpoints": {
            "POST /ingest": "Carica e indicizza un documento",
            "GET /health": "Stato del server",
            "GET /stats": "Statistiche database"
        }
    }


# --- MAIN ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
