import json
from pathlib import Path

# Dossier par défaut à organiser (Dossier de Téléchargements de l'utilisateur)
DEFAULT_TARGET_DIR = Path.home() / "Downloads"

# Extensions temporaires à ignorer (téléchargements en cours)
IGNORED_EXTENSIONS = [".crdownload", ".part", ".download", ".tmp"]

# Emplacement de la configuration utilisateur
CONFIG_DIR = Path.home() / ".config" / "cabinet"
RULES_FILE = CONFIG_DIR / "rules.json"

def load_rules() -> list:
    """Charge les règles personnalisées depuis le fichier JSON."""
    if not RULES_FILE.exists():
        return []
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
            return rules if isinstance(rules, list) else []
    except Exception:
        return []

def save_rules(rules: list):
    """Sauvegarde les règles personnalisées dans le fichier JSON."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

# Dictionnaire de catégorisation par défaut
DEFAULT_CATEGORIES = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", 
        ".tiff", ".ico", ".raw", ".psd"
    ],
    "Documents": [
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", 
        ".ods", ".odp", ".rtf", ".txt", ".csv", ".md", ".pages", ".numbers", ".key"
    ],
    "Code": [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", 
        ".xml", ".yaml", ".yml", ".sh", ".bash", ".sql", ".rs", ".go", 
        ".c", ".cpp", ".h", ".java", ".kt", ".swift", ".php", ".rb"
    ],
    "Audio": [
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".mid"
    ],
    "Video": [
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".mpeg", ".mpg", ".m4v"
    ],
    "Archives": [
        ".zip", ".tar.gz", ".tar", ".rar", ".7z", ".dmg", ".pkg", ".iso", ".gz"
    ],
    "Design": [
        ".ai", ".fig", ".sketch", ".xd", ".indd"
    ],
    "Applications": [
        ".app", ".exe", ".msi"
    ]
}

def get_category_for_extension(ext: str) -> str:
    """Retourne la catégorie associée à une extension donnée."""
    ext = ext.lower().strip()
    if not ext:
        return "Divers"
    
    for category, extensions in DEFAULT_CATEGORIES.items():
        if ext in extensions:
            return category
            
    return "Divers"
