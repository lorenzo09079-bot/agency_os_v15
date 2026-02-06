# -*- coding: utf-8 -*-
"""
Validator v1.0 - Anti-Hallucination Post-Check
==============================================

Valida le risposte di RLM verificando che i dati citati
esistano effettivamente nel database.

USO:
    from rlm.utils.validator import validate_response
    
    result = validate_response(
        response="Ho trovato il file report.csv che contiene...",
        repl_env=rlm.repl_env,
        tools=tools_dict
    )
    
    if result['has_hallucinations']:
        print(f"⚠️ Possibili allucinazioni: {result['issues']}")
"""

import re
from typing import Dict, List, Any, Optional


def extract_cited_filenames(text: str) -> List[str]:
    """
    Estrae nomi di file citati nel testo.
    Cerca pattern comuni come:
    - "file: nome.csv"
    - "documento nome.docx"
    - "Report-qualcosa.csv"
    - estensioni comuni (.csv, .xlsx, .docx, .pdf, .txt, .md)
    """
    patterns = [
        # File con estensioni comuni
        r'[\w\-\s\(\)]+\.(csv|xlsx|xls|docx|doc|pdf|txt|md)',
        # Pattern "file: nome" o "File: nome"
        r'[Ff]ile[:\s]+([^\n,]+\.\w+)',
        # Pattern "documento nome"
        r'[Dd]ocumento[:\s]+([^\n,]+\.\w+)',
    ]
    
    filenames = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            # Pulisci il nome
            clean_name = match.strip().strip('"').strip("'").strip()
            if clean_name and len(clean_name) > 3:
                filenames.add(clean_name)
    
    return list(filenames)


def extract_cited_tags(text: str) -> List[str]:
    """
    Estrae tag citati nel testo.
    Cerca pattern come NOME_TAG in maiuscolo.
    """
    # Pattern per tag (PAROLE_MAIUSCOLE_CON_UNDERSCORE)
    pattern = r'\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b'
    matches = re.findall(pattern, text)
    return list(set(matches))


def extract_cited_numbers(text: str) -> Dict[str, List[str]]:
    """
    Estrae numeri/statistiche citati che potrebbero essere inventati.
    """
    numbers = {
        'righe': re.findall(r'(\d+)\s*(?:righe|rows)', text, re.IGNORECASE),
        'colonne': re.findall(r'(\d+)\s*(?:colonne|columns)', text, re.IGNORECASE),
        'documenti': re.findall(r'(\d+)\s*(?:documenti|documents|file)', text, re.IGNORECASE),
        'percentuali': re.findall(r'(\d+(?:\.\d+)?)\s*%', text),
    }
    return {k: v for k, v in numbers.items() if v}


def validate_response(
    response: str,
    repl_env=None,
    tools: Dict[str, callable] = None,
    strict: bool = False
) -> Dict[str, Any]:
    """
    Valida una risposta RLM controllando che i dati citati esistano.
    
    Args:
        response: La risposta finale di RLM
        repl_env: L'ambiente REPL (per accedere alle variabili)
        tools: Dict dei tools disponibili (list_all_tags, etc.)
        strict: Se True, qualsiasi file non trovato è un'allucinazione
    
    Returns:
        Dict con:
        - has_hallucinations: bool
        - confidence: float (0-1, quanto siamo sicuri)
        - issues: List di problemi trovati
        - verified: List di dati verificati come corretti
        - suggestions: Suggerimenti per correggere
    """
    result = {
        'has_hallucinations': False,
        'confidence': 0.0,
        'issues': [],
        'verified': [],
        'warnings': [],
        'suggestions': []
    }
    
    # Se non abbiamo tools, non possiamo validare
    if not tools:
        result['warnings'].append("Nessun tool disponibile per la validazione")
        return result
    
    # 1. Estrai dati citati
    cited_files = extract_cited_filenames(response)
    cited_tags = extract_cited_tags(response)
    cited_numbers = extract_cited_numbers(response)
    
    # 2. Recupera dati reali dal database
    real_tags = {}
    real_files = set()
    
    if 'list_all_tags' in tools:
        try:
            real_tags = tools['list_all_tags']()
            if isinstance(real_tags, dict) and 'error' not in real_tags:
                result['verified'].append(f"Database accessibile: {len(real_tags)} tag trovati")
        except Exception as e:
            result['warnings'].append(f"Errore accesso database: {e}")
    
    if 'list_files_by_tag' in tools and real_tags:
        for tag in real_tags.keys():
            try:
                files = tools['list_files_by_tag'](tag)
                for f in files:
                    if isinstance(f, dict) and 'filename' in f:
                        real_files.add(f['filename'])
            except:
                pass
    
    # 3. Verifica file citati
    for cited_file in cited_files:
        # Cerca match esatto o parziale
        found = False
        for real_file in real_files:
            if cited_file.lower() in real_file.lower() or real_file.lower() in cited_file.lower():
                found = True
                result['verified'].append(f"File verificato: {cited_file}")
                break
        
        if not found:
            result['issues'].append(f"File non trovato nel database: '{cited_file}'")
            result['has_hallucinations'] = True
    
    # 4. Verifica tag citati
    for cited_tag in cited_tags:
        if cited_tag in real_tags:
            result['verified'].append(f"Tag verificato: {cited_tag}")
        else:
            # Potrebbe essere un falso positivo (non tutti i pattern maiuscoli sono tag)
            result['warnings'].append(f"Tag citato non trovato: {cited_tag}")
    
    # 5. Verifica coerenza con variabili REPL (se disponibili)
    if repl_env and hasattr(repl_env, 'locals'):
        repl_vars = repl_env.locals
        
        # Controlla se ci sono variabili con dati che NON sono stati usati
        for var_name, var_value in repl_vars.items():
            if var_name.startswith('_'):
                continue
            if isinstance(var_value, str) and len(var_value) > 100:
                # C'è una variabile con contenuto sostanzioso
                # Verifica se è stata usata nella risposta
                if var_value[:50] not in response:
                    result['warnings'].append(
                        f"Variabile '{var_name}' contiene dati non usati nella risposta"
                    )
    
    # 6. Calcola confidence score
    total_checks = len(cited_files) + len(cited_tags)
    if total_checks > 0:
        verified_count = len([v for v in result['verified'] if 'verificato' in v])
        result['confidence'] = verified_count / total_checks
    else:
        result['confidence'] = 0.5  # Nessun dato citato = incerto
    
    # 7. Genera suggerimenti
    if result['has_hallucinations']:
        result['suggestions'].append(
            "Riesegui la query chiedendo esplicitamente di usare SOLO dati dal database"
        )
        if real_files:
            result['suggestions'].append(
                f"File reali disponibili: {list(real_files)[:5]}"
            )
    
    return result


def format_validation_report(validation_result: Dict[str, Any]) -> str:
    """Formatta il risultato della validazione in un report leggibile."""
    lines = ["=" * 50]
    lines.append("📋 REPORT VALIDAZIONE RISPOSTA")
    lines.append("=" * 50)
    
    if validation_result['has_hallucinations']:
        lines.append("⚠️ STATO: POSSIBILI ALLUCINAZIONI RILEVATE")
    else:
        lines.append("✅ STATO: Risposta sembra coerente")
    
    lines.append(f"📊 Confidence: {validation_result['confidence']:.0%}")
    
    if validation_result['verified']:
        lines.append("\n✅ Verificati:")
        for v in validation_result['verified']:
            lines.append(f"   • {v}")
    
    if validation_result['issues']:
        lines.append("\n❌ Problemi:")
        for issue in validation_result['issues']:
            lines.append(f"   • {issue}")
    
    if validation_result['warnings']:
        lines.append("\n⚠️ Avvisi:")
        for warning in validation_result['warnings']:
            lines.append(f"   • {warning}")
    
    if validation_result['suggestions']:
        lines.append("\n💡 Suggerimenti:")
        for suggestion in validation_result['suggestions']:
            lines.append(f"   • {suggestion}")
    
    lines.append("=" * 50)
    return "\n".join(lines)


# Test
if __name__ == "__main__":
    # Test estrazione
    test_text = """
    Ho trovato il file Report-senza-titolo (1).csv nel tag DATI_EUROITALIA_METAADS.
    Contiene 215 righe e 29 colonne.
    Ho anche trovato ricerca_pubblicitaria_2026.txt che non esiste.
    """
    
    print("Test estrazione file:", extract_cited_filenames(test_text))
    print("Test estrazione tag:", extract_cited_tags(test_text))
    print("Test estrazione numeri:", extract_cited_numbers(test_text))
