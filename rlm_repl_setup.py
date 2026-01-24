# -*- coding: utf-8 -*-
"""
RLM REPL Setup - Funzioni di accesso alla memoria per Agency OS
Questo codice viene eseguito all'avvio del REPL di RLM

Fornisce:
- search_memory(): Ricerca semantica nel database Qdrant
- list_tags(): Lista tutti i tag disponibili
- search_by_tag(): Ricerca in un tag specifico
- analyze_excel(): Analisi file Excel/CSV (se pandas disponibile)
"""

# ============================================================
# CONFIGURAZIONE
# ============================================================

QDRANT_HOST = "192.168.1.4"
QDRANT_PORT = 6333
COLLECTION_NAME = "agenzia_memory"
ENCODER_MODEL = "all-MiniLM-L6-v2"

# ============================================================
# INIZIALIZZAZIONE
# ============================================================

print("🧠 Inizializzazione Agency OS Memory Tools...")

# Import necessari
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

# Connessione Qdrant
_qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)
_encoder = SentenceTransformer(ENCODER_MODEL)

print(f"✅ Connesso a Qdrant ({QDRANT_HOST}:{QDRANT_PORT})")

# ============================================================
# FUNZIONI MEMORIA
# ============================================================

def search_memory(query: str, tag: str = None, top_k: int = 7) -> str:
    """
    Cerca nella memoria dell'agenzia.
    
    Args:
        query: Testo da cercare (ricerca semantica)
        tag: Filtro opzionale (es. 'RESEARCH_ADS', 'CLIENT_NIKE', 'CHAT_NIKE')
        top_k: Numero massimo di risultati
    
    Returns:
        Stringa formattata con i risultati
    
    Esempi:
        search_memory("strategie ads")
        search_memory("nike performance", tag="CLIENT_NIKE")
        search_memory("copywriting", tag="RESEARCH_COPY", top_k=10)
    """
    vector = _encoder.encode(query).tolist()
    
    # Costruisci filtro
    qdrant_filter = None
    if tag:
        tag = tag.upper()
        qdrant_filter = models.Filter(
            must=[models.FieldCondition(key="client_name", match=models.MatchValue(value=tag))]
        )
    
    # Esegui ricerca
    hits = _qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        query_filter=qdrant_filter,
        limit=top_k
    )
    
    if not hits:
        return f"Nessun risultato per: '{query}' (tag: {tag or 'tutti'})"
    
    # Formatta risultati
    results = [f"=== RICERCA: '{query}' | Tag: {tag or 'tutti'} | Trovati: {len(hits)} ===\n"]
    
    for i, hit in enumerate(hits, 1):
        p = hit.payload
        results.append(f"--- Risultato {i} (Score: {hit.score:.3f}) ---")
        results.append(f"Fonte: {p.get('filename', 'N/A')}")
        results.append(f"Tag: {p.get('client_name', 'N/A')}")
        results.append(f"Contenuto:\n{p.get('text', 'N/A')[:2000]}\n")
    
    return "\n".join(results)


def list_tags() -> str:
    """
    Lista tutti i tag disponibili nel database.
    
    Returns:
        Stringa con tutti i tag e il numero di documenti per ciascuno
    """
    results = _qdrant.scroll(
        collection_name=COLLECTION_NAME,
        limit=2000,
        with_payload=True,
        with_vectors=False
    )
    
    tags = {}
    docs_by_tag = {}
    
    for point in results[0]:
        tag = point.payload.get('client_name', 'UNKNOWN')
        filename = point.payload.get('filename', 'unknown')
        
        if tag not in tags:
            tags[tag] = 0
            docs_by_tag[tag] = set()
        
        tags[tag] += 1
        docs_by_tag[tag].add(filename)
    
    output = ["=== TAG DISPONIBILI ===\n"]
    for tag, count in sorted(tags.items()):
        num_docs = len(docs_by_tag[tag])
        output.append(f"  {tag}: {num_docs} documenti, {count} chunks")
    
    output.append("\n=== DOCUMENTI PER TAG ===\n")
    for tag, docs in sorted(docs_by_tag.items()):
        output.append(f"[{tag}]:")
        for doc in sorted(docs):
            output.append(f"  - {doc}")
        output.append("")
    
    return "\n".join(output)


def search_by_tag(tag: str, query: str = None, top_k: int = 10) -> str:
    """
    Cerca tutti i documenti con un tag specifico.
    
    Args:
        tag: Tag da cercare (es. 'RESEARCH_ADS', 'CHAT_NIKE')
        query: Query opzionale per filtrare semanticamente
        top_k: Numero massimo di risultati
    
    Returns:
        Stringa con i risultati
    """
    if query:
        return search_memory(query, tag=tag, top_k=top_k)
    
    # Scroll tutti i documenti con quel tag
    tag = tag.upper()
    results = _qdrant.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="client_name", match=models.MatchValue(value=tag))]
        ),
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )
    
    if not results[0]:
        return f"Nessun documento con tag: {tag}"
    
    output = [f"=== DOCUMENTI CON TAG: {tag} ===\n"]
    
    seen_files = set()
    for point in results[0]:
        p = point.payload
        filename = p.get('filename', 'N/A')
        
        if filename not in seen_files:
            seen_files.add(filename)
            output.append(f"📄 {filename}")
            output.append(f"   Tipo: {p.get('doc_type', 'N/A')}")
            output.append(f"   Data: {p.get('date', 'N/A')}")
            output.append(f"   Preview: {p.get('text', '')[:200]}...")
            output.append("")
    
    return "\n".join(output)


def get_document(filename: str) -> str:
    """
    Recupera il contenuto completo di un documento.
    
    Args:
        filename: Nome del file da recuperare
    
    Returns:
        Contenuto concatenato di tutti i chunk del documento
    """
    results = _qdrant.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="filename", match=models.MatchValue(value=filename))]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    
    if not results[0]:
        return f"Documento non trovato: {filename}"
    
    # Ordina per chunk_index se disponibile
    chunks = sorted(results[0], key=lambda x: x.payload.get('chunk_index', 0))
    
    output = [f"=== DOCUMENTO: {filename} ===\n"]
    output.append(f"Tag: {chunks[0].payload.get('client_name', 'N/A')}")
    output.append(f"Chunks: {len(chunks)}")
    output.append("\n--- CONTENUTO ---\n")
    
    for chunk in chunks:
        output.append(chunk.payload.get('text', ''))
    
    return "\n".join(output)


# ============================================================
# FUNZIONI ANALISI EXCEL (se pandas disponibile)
# ============================================================

try:
    import pandas as pd
    import os
    
    DATA_DIR = "./data_files"
    
    def list_data_files() -> str:
        """Lista i file Excel/CSV disponibili per analisi."""
        if not os.path.exists(DATA_DIR):
            return "Cartella data_files non trovata"
        
        files = []
        for ext in ['*.xlsx', '*.xls', '*.csv']:
            import glob
            files.extend(glob.glob(os.path.join(DATA_DIR, ext)))
        
        if not files:
            return "Nessun file dati trovato in data_files/"
        
        output = ["=== FILE DATI DISPONIBILI ===\n"]
        for f in files:
            fname = os.path.basename(f)
            size = os.path.getsize(f) / 1024
            output.append(f"  - {fname} ({size:.1f}KB)")
        
        return "\n".join(output)
    
    def analyze_excel(filename: str, query: str = None) -> str:
        """
        Analizza un file Excel/CSV.
        
        Args:
            filename: Nome del file
            query: Descrizione di cosa analizzare (opzionale)
        
        Returns:
            Informazioni sul file e statistiche base
        """
        filepath = os.path.join(DATA_DIR, filename)
        
        if not os.path.exists(filepath):
            # Cerca pattern
            import glob
            matches = glob.glob(os.path.join(DATA_DIR, f"*{filename}*"))
            if matches:
                filepath = matches[0]
            else:
                return f"File non trovato: {filename}"
        
        # Carica file
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        output = [f"=== ANALISI: {os.path.basename(filepath)} ===\n"]
        output.append(f"Righe: {len(df)}")
        output.append(f"Colonne: {len(df.columns)}")
        output.append(f"\nColonne disponibili:")
        for col in df.columns:
            dtype = str(df[col].dtype)
            output.append(f"  - {col} ({dtype})")
        
        output.append(f"\nPrime 5 righe:")
        output.append(df.head().to_string())
        
        # Statistiche numeriche
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            output.append(f"\nStatistiche colonne numeriche:")
            output.append(df[numeric_cols].describe().to_string())
        
        return "\n".join(output)
    
    def excel_query(filename: str, operation: str, column: str = None, group_by: str = None) -> str:
        """
        Esegue query specifiche su file Excel/CSV.
        
        Args:
            filename: Nome del file
            operation: 'sum', 'mean', 'min', 'max', 'count', 'unique'
            column: Colonna su cui operare
            group_by: Colonna per raggruppamento (opzionale)
        
        Returns:
            Risultato della query
        """
        filepath = os.path.join(DATA_DIR, filename)
        
        if not os.path.exists(filepath):
            import glob
            matches = glob.glob(os.path.join(DATA_DIR, f"*{filename}*"))
            if matches:
                filepath = matches[0]
            else:
                return f"File non trovato: {filename}"
        
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        if column and column not in df.columns:
            return f"Colonna '{column}' non trovata. Colonne: {list(df.columns)}"
        
        if group_by:
            if group_by not in df.columns:
                return f"Colonna group_by '{group_by}' non trovata"
            grouped = df.groupby(group_by)
            if operation == 'sum':
                result = grouped[column].sum()
            elif operation == 'mean':
                result = grouped[column].mean()
            elif operation == 'count':
                result = grouped[column].count()
            else:
                result = grouped[column].agg(operation)
            return f"=== {operation.upper()} di {column} per {group_by} ===\n{result.to_string()}"
        else:
            if column:
                series = df[column]
                if operation == 'sum':
                    result = series.sum()
                elif operation == 'mean':
                    result = series.mean()
                elif operation == 'min':
                    result = series.min()
                elif operation == 'max':
                    result = series.max()
                elif operation == 'count':
                    result = series.count()
                elif operation == 'unique':
                    result = series.unique().tolist()
                else:
                    return f"Operazione non supportata: {operation}"
                return f"{operation.upper()} di {column}: {result}"
            else:
                return df.describe().to_string()
    
    print("✅ Funzioni Excel disponibili: list_data_files(), analyze_excel(), excel_query()")

except ImportError:
    print("⚠️ pandas non disponibile - funzioni Excel disabilitate")
    print("   Installa con: pip install pandas openpyxl")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def help_memory():
    """Mostra l'aiuto per le funzioni disponibili."""
    return """
=== AGENCY OS MEMORY TOOLS ===

RICERCA NEL DATABASE:
  search_memory(query, tag=None, top_k=7)
    - Ricerca semantica nella memoria
    - Esempio: search_memory("strategie social media")
    - Esempio: search_memory("nike ads", tag="CLIENT_NIKE")
  
  list_tags()
    - Mostra tutti i tag e documenti disponibili
  
  search_by_tag(tag, query=None, top_k=10)
    - Cerca tutti i documenti con un tag specifico
    - Esempio: search_by_tag("RESEARCH_ADS")
  
  get_document(filename)
    - Recupera il contenuto completo di un documento
    - Esempio: get_document("Red Pill_ Verità Meta Ads_.docx")

ANALISI FILE EXCEL/CSV (se pandas installato):
  list_data_files()
    - Mostra i file Excel/CSV disponibili
  
  analyze_excel(filename)
    - Analizza struttura e statistiche di un file
  
  excel_query(filename, operation, column, group_by=None)
    - Esegue query specifiche (sum, mean, min, max, count)

RICORSIONE LLM:
  llm_query(prompt)
    - Chiama l'LLM ricorsivamente per analisi complesse
  
  llm_query_batched(prompts)
    - Chiama l'LLM su multiple query in parallelo

RISPOSTA FINALE:
  FINAL(risposta)
    - Fornisce la risposta finale
  
  FINAL_VAR(nome_variabile)
    - Usa una variabile come risposta finale
"""

print("\n💡 Scrivi help_memory() per vedere le funzioni disponibili")
print("=" * 50)
