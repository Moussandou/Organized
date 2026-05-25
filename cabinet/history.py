import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

HISTORY_FILE = Path.home() / ".cabinet_history.json"

def save_session(moves: List[Dict[str, str]], strategy: str):
    """Record an organization session in the history."""
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
            
    # Insert the new session at the beginning
    sessions.insert(0, session)
    
    # Keep only the last 10 sessions to limit file size
    sessions = sessions[:10]
    
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=4, ensure_ascii=False)
    except Exception:
        # Silently ignore write errors to avoid blocking the CLI tool
        pass

def get_last_session() -> Optional[Dict]:
    """Retrieve details of the last organization session."""
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
    """Retrieve and remove the last organization session from history."""
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
