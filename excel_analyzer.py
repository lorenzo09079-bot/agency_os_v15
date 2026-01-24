# -*- coding: utf-8 -*-
"""
Excel/CSV Analyzer v1.0 - Analisi Strutturata per Agency OS
Permette a RLM di fare query sui dati tabellari (calcoli, aggregazioni, filtri)

FUNZIONALITA:
- Carica e analizza file Excel/CSV
- Query in linguaggio naturale convertite in operazioni pandas
- Calcoli: somme, medie, min, max, conteggi
- Filtri: per colonna, per valore, per range
- Aggregazioni: group by, pivot
- Confronti tra periodi/campagne
"""
import os
import pandas as pd
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

# --- CONFIGURAZIONE ---
# Cartella dove vengono salvati i file Excel/CSV originali
DATA_FILES_DIR = Path("./data_files")
DATA_FILES_DIR.mkdir(exist_ok=True)


class ExcelAnalyzer:
    """
    Analizzatore di file Excel/CSV per Agency OS.
    Mantiene i file in memoria per query veloci.
    """
    
    def __init__(self, data_dir: Path = DATA_FILES_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.loaded_files: Dict[str, pd.DataFrame] = {}
        self.file_metadata: Dict[str, Dict] = {}
    
    def list_available_files(self) -> str:
        """Lista tutti i file Excel/CSV disponibili per l'analisi."""
        files = []
        
        for ext in ['*.xlsx', '*.xls', '*.csv']:
            files.extend(self.data_dir.glob(ext))
        
        if not files:
            return "NESSUN FILE DATI DISPONIBILE.\nCarica file Excel o CSV tramite l'interfaccia per poterli analizzare."
        
        output = "=== FILE DATI DISPONIBILI ===\n\n"
        
        for f in sorted(files):
            try:
                # Carica per ottenere info
                df = self._load_file(f)
                rows, cols = df.shape
                columns = df.columns.tolist()
                
                output += f"FILE: {f.name}\n"
                output += f"  Righe: {rows} | Colonne: {cols}\n"
                output += f"  Colonne: {', '.join(columns[:10])}"
                if len(columns) > 10:
                    output += f" ... (+{len(columns)-10} altre)"
                output += "\n\n"
                
            except Exception as e:
                output += f"FILE: {f.name} (ERRORE: {e})\n\n"
        
        output += "=== USA analyze_data() PER ANALIZZARE UN FILE ===\n"
        return output
    
    def _load_file(self, filepath: Path) -> pd.DataFrame:
        """Carica un file in memoria (con cache)."""
        filepath_str = str(filepath)
        
        if filepath_str in self.loaded_files:
            return self.loaded_files[filepath_str]
        
        if filepath.suffix.lower() == '.csv':
            # Prova diversi encoding
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(filepath, encoding=encoding)
                    break
                except:
                    continue
            else:
                df = pd.read_csv(filepath, encoding='utf-8', errors='ignore')
        else:
            df = pd.read_excel(filepath)
        
        # Pulisci nomi colonne
        df.columns = df.columns.str.strip()
        
        # Cache
        self.loaded_files[filepath_str] = df
        self.file_metadata[filepath_str] = {
            "loaded_at": datetime.now().isoformat(),
            "rows": len(df),
            "columns": df.columns.tolist()
        }
        
        return df
    
    def get_file_info(self, filename: str) -> str:
        """Ottiene informazioni dettagliate su un file."""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            # Cerca con pattern
            matches = list(self.data_dir.glob(f"*{filename}*"))
            if matches:
                filepath = matches[0]
            else:
                return f"ERRORE: File '{filename}' non trovato in {self.data_dir}"
        
        try:
            df = self._load_file(filepath)
            
            output = f"=== INFO FILE: {filepath.name} ===\n\n"
            output += f"Dimensioni: {len(df)} righe x {len(df.columns)} colonne\n\n"
            
            output += "COLONNE E TIPI:\n"
            for col in df.columns:
                dtype = str(df[col].dtype)
                non_null = df[col].notna().sum()
                sample = str(df[col].dropna().iloc[0])[:50] if non_null > 0 else "N/A"
                output += f"  - {col} ({dtype}): {non_null} valori, es: {sample}\n"
            
            output += f"\nPRIME 5 RIGHE:\n"
            output += df.head().to_string() + "\n"
            
            # Statistiche per colonne numeriche
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                output += f"\nSTATISTICHE COLONNE NUMERICHE:\n"
                output += df[numeric_cols].describe().to_string() + "\n"
            
            return output
            
        except Exception as e:
            return f"ERRORE lettura file: {e}"
    
    def analyze_data(
        self,
        filename: str,
        query: str = None,
        columns: List[str] = None,
        filter_column: str = None,
        filter_value: str = None,
        group_by: str = None,
        aggregation: str = "sum",
        sort_by: str = None,
        top_n: int = None
    ) -> str:
        """
        Analizza i dati di un file Excel/CSV.
        
        Args:
            filename: Nome del file da analizzare
            query: Query in linguaggio naturale (opzionale, per log)
            columns: Lista colonne da includere
            filter_column: Colonna su cui filtrare
            filter_value: Valore per il filtro
            group_by: Colonna per raggruppamento
            aggregation: Tipo aggregazione (sum, mean, count, min, max)
            sort_by: Colonna per ordinamento
            top_n: Limita ai primi N risultati
        
        Returns:
            Risultato dell'analisi come stringa formattata
        """
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            matches = list(self.data_dir.glob(f"*{filename}*"))
            if matches:
                filepath = matches[0]
            else:
                return f"ERRORE: File '{filename}' non trovato"
        
        try:
            df = self._load_file(filepath)
            result_df = df.copy()
            operations = []
            
            # 1. Filtro
            if filter_column and filter_value:
                if filter_column in result_df.columns:
                    # Prova match esatto o contiene
                    mask = result_df[filter_column].astype(str).str.contains(
                        filter_value, case=False, na=False
                    )
                    result_df = result_df[mask]
                    operations.append(f"Filtrato: {filter_column} contiene '{filter_value}'")
            
            # 2. Selezione colonne
            if columns:
                valid_cols = [c for c in columns if c in result_df.columns]
                if valid_cols:
                    # Mantieni anche group_by se specificato
                    if group_by and group_by not in valid_cols:
                        valid_cols = [group_by] + valid_cols
                    result_df = result_df[valid_cols]
                    operations.append(f"Colonne: {', '.join(valid_cols)}")
            
            # 3. Aggregazione
            if group_by and group_by in result_df.columns:
                numeric_cols = result_df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    agg_func = {
                        'sum': 'sum',
                        'mean': 'mean',
                        'avg': 'mean',
                        'count': 'count',
                        'min': 'min',
                        'max': 'max'
                    }.get(aggregation.lower(), 'sum')
                    
                    result_df = result_df.groupby(group_by)[numeric_cols].agg(agg_func).reset_index()
                    operations.append(f"Raggruppato per: {group_by} ({agg_func})")
            
            # 4. Ordinamento
            if sort_by and sort_by in result_df.columns:
                result_df = result_df.sort_values(sort_by, ascending=False)
                operations.append(f"Ordinato per: {sort_by} (desc)")
            
            # 5. Limite risultati
            if top_n:
                result_df = result_df.head(top_n)
                operations.append(f"Top {top_n} risultati")
            
            # Formatta output
            output = f"=== ANALISI: {filepath.name} ===\n"
            if query:
                output += f"Query: {query}\n"
            if operations:
                output += f"Operazioni: {' -> '.join(operations)}\n"
            output += f"Risultati: {len(result_df)} righe\n\n"
            
            # Tabella risultati
            output += result_df.to_string(index=False) + "\n"
            
            # Statistiche rapide per colonne numeriche
            numeric_cols = result_df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols and len(result_df) > 1:
                output += "\nRIEPILOGO:\n"
                for col in numeric_cols[:5]:  # Max 5 colonne
                    total = result_df[col].sum()
                    avg = result_df[col].mean()
                    output += f"  {col}: Totale={total:,.2f}, Media={avg:,.2f}\n"
            
            return output
            
        except Exception as e:
            return f"ERRORE analisi: {e}"
    
    def calculate(
        self,
        filename: str,
        operation: str,
        column: str,
        filter_column: str = None,
        filter_value: str = None
    ) -> str:
        """
        Esegue un calcolo specifico su una colonna.
        
        Args:
            filename: Nome del file
            operation: sum, mean, min, max, count, median
            column: Colonna su cui calcolare
            filter_column: Filtro opzionale
            filter_value: Valore filtro
        
        Returns:
            Risultato del calcolo
        """
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            matches = list(self.data_dir.glob(f"*{filename}*"))
            if matches:
                filepath = matches[0]
            else:
                return f"ERRORE: File '{filename}' non trovato"
        
        try:
            df = self._load_file(filepath)
            
            # Applica filtro
            if filter_column and filter_value and filter_column in df.columns:
                mask = df[filter_column].astype(str).str.contains(
                    filter_value, case=False, na=False
                )
                df = df[mask]
            
            if column not in df.columns:
                # Cerca colonna simile
                similar = [c for c in df.columns if column.lower() in c.lower()]
                if similar:
                    column = similar[0]
                else:
                    return f"ERRORE: Colonna '{column}' non trovata. Colonne disponibili: {', '.join(df.columns)}"
            
            # Converti a numerico se necessario
            series = pd.to_numeric(df[column], errors='coerce')
            
            # Calcola
            ops = {
                'sum': ('Somma', series.sum()),
                'mean': ('Media', series.mean()),
                'avg': ('Media', series.mean()),
                'min': ('Minimo', series.min()),
                'max': ('Massimo', series.max()),
                'count': ('Conteggio', series.count()),
                'median': ('Mediana', series.median()),
                'std': ('Deviazione Std', series.std()),
            }
            
            op_lower = operation.lower()
            if op_lower not in ops:
                return f"ERRORE: Operazione '{operation}' non valida. Usa: sum, mean, min, max, count, median"
            
            name, value = ops[op_lower]
            
            result = f"=== CALCOLO ===\n"
            result += f"File: {filepath.name}\n"
            result += f"Colonna: {column}\n"
            if filter_column:
                result += f"Filtro: {filter_column} = '{filter_value}'\n"
            result += f"Righe analizzate: {len(df)}\n"
            result += f"\n{name} di {column}: {value:,.2f}\n"
            
            return result
            
        except Exception as e:
            return f"ERRORE calcolo: {e}"
    
    def compare_values(
        self,
        filename: str,
        group_column: str,
        value_column: str,
        aggregation: str = "sum"
    ) -> str:
        """
        Confronta valori tra gruppi (es. campagne, periodi).
        
        Args:
            filename: Nome del file
            group_column: Colonna per raggruppare (es. "Campagna", "Mese")
            value_column: Colonna da confrontare (es. "Spesa", "Conversioni")
            aggregation: Tipo aggregazione
        """
        return self.analyze_data(
            filename=filename,
            group_by=group_column,
            columns=[value_column],
            aggregation=aggregation,
            sort_by=value_column
        )


# --- DEFINIZIONI TOOL PER RLM ---
def get_excel_tools_definitions() -> List[Dict[str, Any]]:
    """
    Tools per analisi Excel/CSV che RLM puo chiamare.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "list_data_files",
                "description": (
                    "Elenca tutti i file Excel e CSV disponibili per l'analisi. "
                    "Mostra nome file, numero righe/colonne, e nomi delle colonne. "
                    "Usa questo tool per scoprire quali file dati sono disponibili."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_file_info",
                "description": (
                    "Ottiene informazioni dettagliate su un file Excel/CSV: "
                    "struttura colonne, tipi di dati, prime righe di esempio, "
                    "e statistiche base per colonne numeriche."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Nome del file da esaminare"
                        }
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_data",
                "description": (
                    "Analizza dati da un file Excel/CSV con filtri, raggruppamenti e aggregazioni. "
                    "Esempi: 'mostra spesa per campagna', 'filtra per data', 'calcola totali'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Nome del file da analizzare"
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista colonne da includere (opzionale)"
                        },
                        "filter_column": {
                            "type": "string",
                            "description": "Colonna su cui applicare un filtro"
                        },
                        "filter_value": {
                            "type": "string",
                            "description": "Valore da cercare nella colonna filtro"
                        },
                        "group_by": {
                            "type": "string",
                            "description": "Colonna per raggruppare i dati (es. 'Campagna', 'Mese')"
                        },
                        "aggregation": {
                            "type": "string",
                            "description": "Tipo aggregazione: sum, mean, count, min, max (default: sum)"
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Colonna per ordinare i risultati"
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "Limita ai primi N risultati"
                        }
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": (
                    "Esegue un calcolo specifico su una colonna: somma, media, minimo, massimo, conteggio, mediana. "
                    "Esempio: 'calcola la spesa totale', 'qual e il CPA medio?'"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Nome del file"
                        },
                        "operation": {
                            "type": "string",
                            "description": "Operazione: sum, mean, min, max, count, median"
                        },
                        "column": {
                            "type": "string",
                            "description": "Colonna su cui calcolare"
                        },
                        "filter_column": {
                            "type": "string",
                            "description": "Colonna per filtro opzionale"
                        },
                        "filter_value": {
                            "type": "string",
                            "description": "Valore per filtro opzionale"
                        }
                    },
                    "required": ["filename", "operation", "column"]
                }
            }
        }
    ]


class ExcelToolsExecutor:
    """Esegue i tool calls per l'analisi Excel."""
    
    def __init__(self, data_dir: Path = DATA_FILES_DIR):
        self.analyzer = ExcelAnalyzer(data_dir)
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Esegue un tool e ritorna il risultato."""
        print(f"EXCEL TOOL: {tool_name}({arguments})")
        
        if tool_name == "list_data_files":
            return self.analyzer.list_available_files()
        
        elif tool_name == "get_file_info":
            return self.analyzer.get_file_info(
                filename=arguments.get("filename", "")
            )
        
        elif tool_name == "analyze_data":
            return self.analyzer.analyze_data(
                filename=arguments.get("filename", ""),
                columns=arguments.get("columns"),
                filter_column=arguments.get("filter_column"),
                filter_value=arguments.get("filter_value"),
                group_by=arguments.get("group_by"),
                aggregation=arguments.get("aggregation", "sum"),
                sort_by=arguments.get("sort_by"),
                top_n=arguments.get("top_n")
            )
        
        elif tool_name == "calculate":
            return self.analyzer.calculate(
                filename=arguments.get("filename", ""),
                operation=arguments.get("operation", "sum"),
                column=arguments.get("column", ""),
                filter_column=arguments.get("filter_column"),
                filter_value=arguments.get("filter_value")
            )
        
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


# --- FUNZIONE PER SALVARE FILE DATI ---
def save_data_file(file_content: bytes, filename: str, data_dir: Path = DATA_FILES_DIR) -> str:
    """
    Salva un file Excel/CSV nella cartella dati per analisi future.
    
    Args:
        file_content: Contenuto del file in bytes
        filename: Nome del file
        data_dir: Cartella destinazione
    
    Returns:
        Path del file salvato o messaggio errore
    """
    data_dir.mkdir(exist_ok=True)
    
    # Aggiungi timestamp se file esiste
    filepath = data_dir / filename
    if filepath.exists():
        stem = filepath.stem
        suffix = filepath.suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = data_dir / f"{stem}_{timestamp}{suffix}"
    
    try:
        with open(filepath, 'wb') as f:
            f.write(file_content)
        return str(filepath)
    except Exception as e:
        return f"ERRORE salvataggio: {e}"


# --- TEST ---
if __name__ == "__main__":
    print("Test Excel Analyzer...")
    print("=" * 50)
    
    analyzer = ExcelAnalyzer()
    
    print("\n[1] Lista file disponibili:")
    print(analyzer.list_available_files())
    
    # Se ci sono file, prova ad analizzarli
    files = list(DATA_FILES_DIR.glob("*.xlsx")) + list(DATA_FILES_DIR.glob("*.csv"))
    if files:
        test_file = files[0].name
        print(f"\n[2] Info su {test_file}:")
        print(analyzer.get_file_info(test_file))
