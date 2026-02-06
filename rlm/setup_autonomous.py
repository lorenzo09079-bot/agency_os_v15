# -*- coding: utf-8 -*-
"""
SETUP SCRIPT - Agency OS v6.0 Autonomous Intelligence
======================================================
Esegui questo script per installare il sistema autonomo.

COSA FA:
1. Crea backup dei file esistenti
2. Copia i nuovi file nelle posizioni corrette
3. Verifica che tutto funzioni

USO:
    python setup_autonomous.py
"""

import os
import shutil
from datetime import datetime

# Configurazione percorsi
BASE_DIR = r"C:\Users\loren\Documents\AI Test\AI_Lab"
RLM_DIR = os.path.join(BASE_DIR, "rlm")

# File da installare (source -> destination)
FILES_TO_INSTALL = {
    "tools_v5.py": os.path.join(BASE_DIR, "tools.py"),
    "app_rlm_autonomous.py": os.path.join(BASE_DIR, "app_rlm_autonomous.py"),
    "repl_v2.py": os.path.join(RLM_DIR, "rlm", "repl.py"),
}

BACKUP_DIR = os.path.join(BASE_DIR, "backups", datetime.now().strftime("%Y%m%d_%H%M%S"))


def create_backup(filepath):
    """Crea backup di un file se esiste."""
    if os.path.exists(filepath):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        filename = os.path.basename(filepath)
        backup_path = os.path.join(BACKUP_DIR, filename)
        shutil.copy2(filepath, backup_path)
        print(f"  📦 Backup: {filename} -> {backup_path}")
        return True
    return False


def install_file(source, destination):
    """Installa un file nella destinazione."""
    try:
        # Backup se esiste
        create_backup(destination)
        
        # Copia
        shutil.copy2(source, destination)
        print(f"  ✅ Installato: {os.path.basename(destination)}")
        return True
    except Exception as e:
        print(f"  ❌ Errore: {e}")
        return False


def verify_installation():
    """Verifica che l'installazione sia corretta."""
    print("\n🔍 Verifica installazione...")
    
    all_ok = True
    
    # Verifica file
    for source, dest in FILES_TO_INSTALL.items():
        if os.path.exists(dest):
            print(f"  ✅ {os.path.basename(dest)}")
        else:
            print(f"  ❌ {os.path.basename(dest)} NON TROVATO")
            all_ok = False
    
    # Verifica import
    print("\n🔍 Verifica import...")
    
    try:
        import sys
        sys.path.insert(0, BASE_DIR)
        sys.path.insert(0, RLM_DIR)
        
        # Test tools
        import tools
        tags = tools.list_all_tags() if hasattr(tools, 'list_all_tags') else None
        if tags is not None:
            print(f"  ✅ tools.py (v5 con esplorazione autonoma)")
        else:
            print(f"  ⚠️ tools.py (versione precedente)")
        
        # Test RLM
        from rlm.rlm_repl import RLM_REPL
        print(f"  ✅ RLM_REPL")
        
        # Test REPL con inject_tools
        from rlm.repl import REPLEnv
        if hasattr(REPLEnv, 'inject_tools'):
            print(f"  ✅ REPLEnv (v2 con inject_tools)")
        else:
            print(f"  ⚠️ REPLEnv (versione originale)")
        
    except ImportError as e:
        print(f"  ❌ Errore import: {e}")
        all_ok = False
    
    return all_ok


def main():
    print("=" * 60)
    print("SETUP - Agency OS v6.0 Autonomous Intelligence")
    print("=" * 60)
    
    # Verifica che i file sorgente esistano
    print("\n📁 Verifica file sorgente...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    missing = []
    
    for source in FILES_TO_INSTALL.keys():
        source_path = os.path.join(current_dir, source)
        if os.path.exists(source_path):
            print(f"  ✅ {source}")
        else:
            print(f"  ❌ {source} NON TROVATO")
            missing.append(source)
    
    if missing:
        print(f"\n⚠️ File mancanti: {missing}")
        print("Scarica tutti i file nella stessa cartella prima di eseguire il setup.")
        return
    
    # Installazione
    print("\n📦 Installazione...")
    
    for source, dest in FILES_TO_INSTALL.items():
        source_path = os.path.join(current_dir, source)
        install_file(source_path, dest)
    
    # Verifica
    if verify_installation():
        print("\n" + "=" * 60)
        print("✅ INSTALLAZIONE COMPLETATA!")
        print("=" * 60)
        print(f"\nBackup salvati in: {BACKUP_DIR}")
        print("\nPer avviare:")
        print(f"  cd \"{BASE_DIR}\"")
        print(f"  streamlit run app_rlm_autonomous.py")
    else:
        print("\n" + "=" * 60)
        print("⚠️ INSTALLAZIONE CON PROBLEMI")
        print("=" * 60)
        print("Controlla gli errori sopra e riprova.")


if __name__ == "__main__":
    main()
