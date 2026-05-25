import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

HISTORY_FILE = Path.home() / ".cabinet_history.json"

def save_session(moves: List[Dict[str, str]], strategy: str):
    """Enregistre une session de rangement dans l'historique."""
    session = {
        "timestamp": datetime.now().isoformat(),
        "strategy": strategy,
        "moves": moves
    }
    
    sessions = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                sessions = json.load(f)
                if not isinstance(sessions, list):
                    sessions = []
        except Exception:
            sessions = []
            
    # On ajoute la nouvelle session au début
    sessions.insert(0, session)
    
    # On garde les 10 dernières sessions pour éviter d'avoir un fichier trop gros
    sessions = sessions[:10]
    
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=4, ensure_ascii=False)
    except Exception as e:
        # En cas d'erreur d'écriture, on ignore silencieusement pour ne pas bloquer l'outil
        pass

def get_last_session() -> Optional[Dict]:
    """Récupère les détails de la dernière session de rangement."""
    if not HISTORY_FILE.exists():
        return None
        
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
            if isinstance(sessions, list) and len(sessions) > 0:
                return sessions[0]
    except Exception:
        return None
    return None

def pop_last_session() -> Optional[Dict]:
    """Récupère et supprime la dernière session de rangement de l'historique."""
    if not HISTORY_FILE.exists():
        return None
        
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
            
        if isinstance(sessions, list) and len(sessions) > 0:
            last_session = sessions.pop(0)
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=4, ensure_ascii=False)
            return last_session
    except Exception:
        return None
    return None
