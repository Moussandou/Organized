import json
from pathlib import Path
import logging

# Default directory to organize (User's Downloads folder)
DEFAULT_TARGET_DIR = Path.home() / "Downloads"

# Temporary extensions to ignore (ongoing downloads)
IGNORED_EXTENSIONS = [".crdownload", ".part", ".download", ".tmp"]

# Location of user configuration and logs
CONFIG_DIR = Path.home() / ".config" / "cabinet"
RULES_FILE = CONFIG_DIR / "rules.json"
LOG_FILE = CONFIG_DIR / "cabinet.log"

def setup_logging():
    """Configure the logging system for cabinet.log."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Configure logging to append to cabinet.log
        logging.basicConfig(
            filename=str(LOG_FILE),
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            encoding="utf-8"
        )
    except Exception:
        # Fallback to prevent crashes due to write permission issues
        logging.basicConfig(handlers=[logging.NullHandler()])

def load_rules() -> list:
    """Load custom rules from the JSON file."""
    if not RULES_FILE.exists():
        return []
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
            return rules if isinstance(rules, list) else []
    except Exception:
        return []

def save_rules(rules: list):
    """Save custom rules to the JSON file."""
    try:
        RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

# Default categorization dictionary
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
    """Return the category associated with a given extension."""
    ext = ext.lower().strip()
    if not ext:
        return "Divers"
    
    for category, extensions in DEFAULT_CATEGORIES.items():
        if ext in extensions:
            return category
            
    return "Divers"
