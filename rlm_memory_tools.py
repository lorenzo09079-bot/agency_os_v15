# -*- coding: utf-8 -*-
"""
RLM Memory Tools v3.0 - Ricerca + Analisi Excel
Per Agency OS v5.5

FUNZIONALITA:
- Ricerca semantica nel vector DB (Qdrant)
- Analisi strutturata file Excel/CSV
- Cross-reference tra documenti e dati
"""
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import json
from pathlib import Path

# Import Excel Analyzer
try:
    from excel_analyzer import (
        ExcelAnalyzer,
        ExcelToolsExecutor,
        get_excel_tools_definitions,
        DATA_FILES_DIR
    )
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    print("WARN: excel_analyzer.py non trovato - funzionalita Excel disabilitata")


# --- CONFIGURAZIONE ---
IP_ZENBOOK = "http://192.168.1.4:6333"
COLLECTION_NAME = "agenzia_memory"


# --- MAPPING TAG ---
TAG_SHORTCUTS = {
    "ads": "RESEARCH_ADS",
    "advertising": "RESEARCH_ADS",
    "meta": "RESEARCH_ADS",
    "google": "RESEARCH_ADS",
    "paid": "RESEARCH_ADS",
    
    "social": "RESEARCH_SOCIAL",
    "social media": "RESEARCH_SOCIAL",
    "instagram": "RESEARCH_SOCIAL",
    "linkedin": "RESEARCH_SOCIAL",
    "facebook": "RESEARCH_SOCIAL",
    
    "copy": "RESEARCH_COPY",
    "copywriting": "RESEARCH_COPY",
    "scrittura": "RESEARCH_COPY",
    "writing": "RESEARCH_COPY",
    
    "blog": "RESEARCH_BLOG",
    "content": "RESEARCH_BLOG",
    
    "seo": "RESEARCH_SEO",
    
    "email": "RESEARCH_EMAIL",
    "newsletter": "RESEARCH_EMAIL",
}


def normalize_filter(filter_input: str) -> Optional[str]:
    """Normalizza un filtro al formato database."""
    if not filter_input:
        return None
    
    filter_clean = filter_input.strip().lower()
    
    if filter_clean in ["nessuno", "none", "null", "all", "tutto", ""]:
        return None
    
    if filter_clean in TAG_SHORTCUTS:
        return TAG_SHORTCUTS[filter_clean]
    
    filter_upper = filter_input.strip().upper()
    valid_prefixes = ["RESEARCH_", "CLIENT_", "CHAT_", "DATA_", "SYSTEM_"]
    for prefix in valid_prefixes:
        if filter_upper.startswith(prefix):
            return filter_upper
    
    return filter_upper


class MemoryTools:
    """Tools per ricerca nel Vector DB Qdrant."""
    
    def __init__(
        self, 
        qdrant_url: str = IP_ZENBOOK,
        collection_name: str = COLLECTION_NAME
    ):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.encoder = None
        self.qdrant = None
        self._initialized = False
    
    def _init_connections(self):
        if not self._initialized:
            try:
                print(f"MemoryTools: Connessione a {self.qdrant_url}...")
                self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
                self.qdrant = QdrantClient(url=self.qdrant_url)
                self._initialized = True
                print("MemoryTools: Connesso!")
            except Exception as e:
                print(f"MemoryTools: Errore - {e}")
                raise
    
    def search_memory(
        self, 
        query: str, 
        client_filter: Optional[str] = None,
        top_k: int = 7
    ) -> str:
        """Cerca nella memoria vettoriale."""
        self._init_connections()
        
        try:
            db_filter = normalize_filter(client_filter)
            
            print(f"SEARCH: query='{query[:50]}...' | filter={db_filter}")
            
            vector = self.encoder.encode(query).tolist()
            
            filter_conditions = []
            if db_filter:
                filter_conditions.append(
                    models.FieldCondition(
                        key="client_name",
                        match=models.MatchValue(value=db_filter)
                    )
                )
            
            qdrant_filter = None
            if filter_conditions:
                qdrant_filter = models.Filter(must=filter_conditions)
            
            hits = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=qdrant_filter,
                limit=top_k
            )
            
            if not hits:
                return f"NESSUN RISULTATO per: '{query}' (filtro: {db_filter or 'nessuno'})"
            
            result = f"=== RISULTATI RICERCA ===\n"
            result += f"Query: '{query}'\n"
            result += f"Filtro: {db_filter or 'nessuno (tutto il database)'}\n"
            result += f"Trovati: {len(hits)} risultati\n\n"
            
            for i, hit in enumerate(hits, 1):
                p = hit.payload
                result += f"--- Risultato {i} (Score: {hit.score:.3f}) ---\n"
                result += f"Fonte: {p.get('filename', 'N/A')}\n"
                result += f"Tag: {p.get('client_name', 'N/A')}\n"
                result += f"Contenuto:\n{p.get('text', 'N/A')}\n\n"
            
            result += "=== FINE RISULTATI ===\n"
            return result
            
        except Exception as e:
            return f"ERRORE RICERCA: {str(e)}"
    
    def multi_tag_search(
        self, 
        query: str, 
        tags: List[str], 
        top_k: int = 3
    ) -> str:
        """Cerca in multipli tag e aggrega risultati."""
        all_results = []
        
        for tag in tags:
            result = self.search_memory(query, client_filter=tag, top_k=top_k)
            all_results.append(f"\n{'='*40}\nRICERCA CON TAG: {tag}\n{'='*40}\n{result}")
        
        return "\n".join(all_results)
    
    def list_available_filters(self) -> str:
        """Mostra tutti i filtri disponibili."""
        self._init_connections()
        
        try:
            results = self.qdrant.scroll(
                collection_name=self.collection_name,
                limit=500,
                with_payload=True,
                with_vectors=False
            )
            
            tags_count = {}
            docs_by_tag = {}
            
            for point in results[0]:
                tag = point.payload.get('client_name', 'UNKNOWN')
                filename = point.payload.get('filename', 'Unknown')
                
                if tag not in tags_count:
                    tags_count[tag] = 0
                    docs_by_tag[tag] = set()
                
                tags_count[tag] += 1
                docs_by_tag[tag].add(filename)
            
            output = "=== CONTENUTO DATABASE ===\n\n"
            
            output += "TAG DISPONIBILI:\n"
            for tag, count in sorted(tags_count.items()):
                num_docs = len(docs_by_tag[tag])
                output += f"  - {tag}: {num_docs} documenti, {count} chunks\n"
            
            output += "\nSHORTCUT ACCETTATI:\n"
            output += "  - 'ads' -> RESEARCH_ADS\n"
            output += "  - 'social' -> RESEARCH_SOCIAL\n"
            output += "  - 'copy' -> RESEARCH_COPY\n"
            output += "  - 'blog' -> RESEARCH_BLOG\n"
            output += "  - 'seo' -> RESEARCH_SEO\n"
            
            output += "\nDOCUMENTI PER TAG:\n"
            for tag, docs in sorted(docs_by_tag.items()):
                output += f"\n[{tag}]:\n"
                for doc in sorted(docs):
                    output += f"  - {doc}\n"
            
            return output
            
        except Exception as e:
            return f"ERRORE: {str(e)}"


# --- DEFINIZIONI TOOLS COMBINATE ---
def get_rlm_tools_definitions() -> List[Dict[str, Any]]:
    """
    Tutti i tools disponibili per RLM:
    - Ricerca semantica (vector DB)
    - Analisi Excel/CSV
    """
    # Tools ricerca semantica
    memory_tools = [
        {
            "type": "function",
            "function": {
                "name": "search_memory",
                "description": (
                    "Cerca informazioni nel database della memoria aziendale (documenti, ricerche, chat). "
                    "Usa per trovare strategie, best practice, conversazioni passate, documenti clienti."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Testo da cercare"
                        },
                        "client_filter": {
                            "type": "string",
                            "description": (
                                "Filtro: 'ads', 'social', 'copy', 'blog', 'seo' oppure "
                                "tag completo come 'RESEARCH_ADS', 'CLIENT_NIKE'. "
                                "Usa null per cercare ovunque."
                            )
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Numero risultati (default: 7)"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "multi_tag_search",
                "description": "Cerca in piu categorie contemporaneamente per confrontare informazioni.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Testo da cercare"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista tag: ['ads', 'social'] o ['RESEARCH_ADS', 'CLIENT_NIKE']"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Risultati per tag (default: 3)"
                        }
                    },
                    "required": ["query", "tags"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_available_filters",
                "description": "Mostra tutti i tag/filtri disponibili e documenti nel database.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]
    
    # Tools analisi Excel (se disponibile)
    if EXCEL_AVAILABLE:
        excel_tools = get_excel_tools_definitions()
        return memory_tools + excel_tools
    
    return memory_tools


class CombinedToolsExecutor:
    """
    Esegue tutti i tool calls di RLM:
    - Ricerca semantica
    - Analisi Excel
    """
    
    def __init__(
        self, 
        qdrant_url: str = IP_ZENBOOK,
        collection_name: str = COLLECTION_NAME,
        data_dir: Path = None
    ):
        self.memory_tools = MemoryTools(qdrant_url, collection_name)
        
        if EXCEL_AVAILABLE:
            if data_dir:
                self.excel_executor = ExcelToolsExecutor(data_dir)
            else:
                self.excel_executor = ExcelToolsExecutor()
        else:
            self.excel_executor = None
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Esegue un tool e ritorna il risultato."""
        print(f"TOOL EXEC: {tool_name}({arguments})")
        
        # Tools memoria
        if tool_name == "search_memory":
            return self.memory_tools.search_memory(
                query=arguments.get("query", ""),
                client_filter=arguments.get("client_filter"),
                top_k=arguments.get("top_k", 7)
            )
        
        elif tool_name == "multi_tag_search":
            return self.memory_tools.multi_tag_search(
                query=arguments.get("query", ""),
                tags=arguments.get("tags", []),
                top_k=arguments.get("top_k", 3)
            )
        
        elif tool_name == "list_available_filters":
            return self.memory_tools.list_available_filters()
        
        # Tools Excel
        elif tool_name in ["list_data_files", "get_file_info", "analyze_data", "calculate"]:
            if self.excel_executor:
                return self.excel_executor.execute(tool_name, arguments)
            else:
                return "ERRORE: Funzionalita Excel non disponibile. Assicurati che excel_analyzer.py sia presente."
        
        else:
            return f"Tool sconosciuto: {tool_name}"
    
    def execute_from_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """Esegue un tool call dal formato Qwen."""
        func = tool_call.get("function", {})
        name = func.get("name", "")
        args_str = func.get("arguments", "{}")
        
        try:
            arguments = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            arguments = {}
        
        return self.execute(name, arguments)


# Alias per retrocompatibilita
MemoryToolsExecutor = CombinedToolsExecutor


# --- TEST ---
if __name__ == "__main__":
    print("Test RLM Memory Tools v3.0...")
    print("=" * 50)
    
    print(f"Excel disponibile: {EXCEL_AVAILABLE}")
    
    tools_defs = get_rlm_tools_definitions()
    print(f"\nTools disponibili: {len(tools_defs)}")
    for t in tools_defs:
        print(f"  - {t['function']['name']}")
    
    print("\n[1] Test ricerca memoria:")
    executor = CombinedToolsExecutor()
    result = executor.execute("search_memory", {"query": "strategie ads", "top_k": 2})
    print(result[:500] + "...")
    
    if EXCEL_AVAILABLE:
        print("\n[2] Test lista file Excel:")
        result = executor.execute("list_data_files", {})
        print(result)
