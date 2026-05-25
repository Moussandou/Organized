import os
import shutil
import hashlib
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from cabinet.config import get_category_for_extension, IGNORED_EXTENSIONS, load_rules

class CabinetOrganizer:
    def __init__(self, target_dir: Path):
        self.target_dir = Path(target_dir).expanduser().resolve()

    def scan_files(self) -> List[Path]:
        """Scan et retourne uniquement les fichiers présents à la racine du dossier cible (exclut les temporaires)."""
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            return []
        
        files = []
        for item in self.target_dir.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                # On filtre les extensions temporaires de téléchargements en cours
                if item.suffix.lower() not in IGNORED_EXTENSIONS and item.name != ".cabinet_history.json":
                    files.append(item)
        return files

    def scan_all_files_recursive(self) -> List[Path]:
        """Scan et retourne tous les fichiers présents dans le dossier cible et ses sous-dossiers (exclut les temporaires)."""
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            return []
            
        files = []
        for item in self.target_dir.rglob("*"):
            # On ignore les fichiers masqués et les répertoires
            if item.is_file() and not item.name.startswith('.'):
                # Vérifie que le fichier n'est pas dans un sous-dossier masqué
                try:
                    rel_parts = item.relative_to(self.target_dir).parts
                    if any(part.startswith('.') for part in rel_parts):
                        continue
                except ValueError:
                    continue
                    
                if item.suffix.lower() not in IGNORED_EXTENSIONS and item.name != ".cabinet_history.json":
                    files.append(item)
        return files

    def get_destination(self, file_path: Path, strategy: str) -> Path:
        """Calcule le chemin de destination d'un fichier selon les règles et la stratégie choisie."""
        # 1. Vérification des Smart Rules personnalisées (priorité absolue)
        rules = load_rules()
        for rule in rules:
            pattern = rule.get("pattern", "")
            folder = rule.get("folder", "")
            if pattern and folder and pattern.lower() in file_path.name.lower():
                dest_dir = self.target_dir / folder
                return dest_dir / file_path.name

        # 2. Application de la stratégie par défaut
        suffix = file_path.suffix.lower()
        
        try:
            mtime = file_path.stat().st_mtime
            file_date = datetime.fromtimestamp(mtime)
        except Exception:
            file_date = datetime.now()
            
        date_str = file_date.strftime("%Y-%m")
        category = get_category_for_extension(suffix)
        
        if strategy == "category":
            dest_dir = self.target_dir / category
        elif strategy == "date":
            dest_dir = self.target_dir / date_str
        elif strategy == "extension":
            ext_folder = suffix.replace('.', '').upper() if suffix else "SANS_EXTENSION"
            dest_dir = self.target_dir / ext_folder
        elif strategy == "hybrid":
            dest_dir = self.target_dir / category / date_str
        else:
            dest_dir = self.target_dir / "Divers"
            
        return dest_dir / file_path.name

    def resolve_conflict(self, dest_path: Path) -> Path:
        """Gère les conflits si un fichier de même nom existe déjà dans la destination."""
        if not dest_path.exists():
            return dest_path
            
        parent = dest_path.parent
        name = dest_path.stem
        suffix = dest_path.suffix
        
        counter = 1
        new_path = parent / f"{name} ({counter}){suffix}"
        while new_path.exists():
            counter += 1
            new_path = parent / f"{name} ({counter}){suffix}"
            
        return new_path

    def preview_organization(self, files: List[Path], strategy: str) -> Dict[str, List[Tuple[Path, Path]]]:
        """Génère une simulation du rangement sans déplacer les fichiers."""
        preview = {}
        for file in files:
            dest_path = self.get_destination(file, strategy)
            resolved_dest = self.resolve_conflict(dest_path)
            
            try:
                rel_dest = resolved_dest.relative_to(self.target_dir)
                dest_dir_name = str(rel_dest.parent)
            except ValueError:
                dest_dir_name = "Autres"
                
            if dest_dir_name not in preview:
                preview[dest_dir_name] = []
            preview[dest_dir_name].append((file, resolved_dest))
            
        return preview

    def organize(self, files: List[Path], strategy: str) -> Tuple[List[Dict[str, str]], List[str]]:
        """Exécute le déplacement des fichiers avec gestion d'historique."""
        moves = []
        errors = []
        
        for file in files:
            if not file.exists():
                continue
                
            dest_path = self.get_destination(file, strategy)
            resolved_dest = self.resolve_conflict(dest_path)
            
            try:
                resolved_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), str(resolved_dest))
                
                moves.append({
                    "source": str(file),
                    "dest": str(resolved_dest)
                })
            except Exception as e:
                errors.append(f"Erreur lors du déplacement de {file.name} : {str(e)}")
                
        return moves, errors

    def revert_moves(self, moves: List[Dict[str, str]]) -> Tuple[int, List[str]]:
        """Annule une liste de déplacements en remettant les fichiers à leur place."""
        reverted_count = 0
        errors = []
        
        for move in reversed(moves):
            source_path = Path(move["source"])
            dest_path = Path(move["dest"])
            
            if not dest_path.exists():
                errors.append(f"Le fichier déplacé n'existe plus : {dest_path.name}")
                continue
                
            try:
                source_path.parent.mkdir(parents=True, exist_ok=True)
                resolved_source = self.resolve_conflict(source_path)
                shutil.move(str(dest_path), str(resolved_source))
                reverted_count += 1
                
                self._clean_empty_parents(dest_path.parent)
            except Exception as e:
                errors.append(f"Impossible de restaurer {dest_path.name} : {str(e)}")
                
        return reverted_count, errors

    def _clean_empty_parents(self, path: Path):
        """Supprime récursivement les répertoires vides jusqu'au dossier cible racine."""
        current = path
        while current != self.target_dir and current.parts > self.target_dir.parts:
            try:
                if current.exists() and current.is_dir() and not any(current.iterdir()):
                    current.rmdir()
                    current = current.parent
                else:
                    break
            except Exception:
                break

    def _get_file_hash(self, path: Path) -> str:
        """Calcule le hash SHA-256 d'un fichier."""
        hash_sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha.update(chunk)
        return hash_sha.hexdigest()

    def find_duplicates(self, recursive: bool = False) -> Dict[str, List[Path]]:
        """Identifie les fichiers en doublon en comparant taille et hash SHA-256 (composite key)."""
        files = self.scan_all_files_recursive() if recursive else self.scan_files()
        
        # Groupement par taille pour éviter les calculs de hash inutiles sur les fichiers uniques
        by_size = {}
        for file in files:
            try:
                size = file.stat().st_size
                if size == 0:
                    continue
                if size not in by_size:
                    by_size[size] = []
                by_size[size].append(file)
            except Exception:
                continue
                
        candidate_sizes = {s: paths for s, paths in by_size.items() if len(paths) > 1}
        
        # Calcul du hash uniquement pour les groupes de taille identique
        hashes = {}
        for size, paths in candidate_sizes.items():
            for file in paths:
                try:
                    file_hash = self._get_file_hash(file)
                    composite_key = f"{size}_{file_hash}"
                    if composite_key not in hashes:
                        hashes[composite_key] = []
                    hashes[composite_key].append(file)
                except Exception:
                    continue
                    
        return {k: paths for k, paths in hashes.items() if len(paths) > 1}

    def get_old_files(self, days: int) -> List[Path]:
        """Retourne la liste des fichiers qui n'ont pas été modifiés depuis X jours."""
        files = self.scan_all_files_recursive()
        now = datetime.now()
        old_files = []
        for file in files:
            try:
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                age_days = (now - mtime).days
                if age_days >= days:
                    old_files.append(file)
            except Exception:
                continue
        return old_files

    def clean_old_files(self, days: int, action: str) -> Tuple[int, Optional[Path], List[str]]:
        """Archives ou supprime (Corbeille) les vieux fichiers."""
        old_files = self.get_old_files(days)
        if not old_files:
            return 0, None, []
            
        errors = []
        success_count = 0
        trash_dir = Path.home() / ".Trash"
        trash_dir.mkdir(parents=True, exist_ok=True)
        
        if action == "trash":
            for file in old_files:
                try:
                    dest = self.resolve_conflict(trash_dir / file.name)
                    shutil.move(str(file), str(dest))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Erreur de mise à la Corbeille pour {file.name} : {str(e)}")
            return success_count, None, errors
            
        elif action == "archive":
            archive_name = f"archive_downloads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            archive_path = self.target_dir / archive_name
            archive_path = self.resolve_conflict(archive_path)
            
            try:
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file in old_files:
                        try:
                            rel_path = file.relative_to(self.target_dir)
                            zipf.write(file, rel_path)
                        except Exception as e:
                            errors.append(f"Erreur d'archivage de {file.name} : {str(e)}")
                            
                # Déplacement des fichiers d'origine dans la Corbeille
                if archive_path.exists():
                    for file in old_files:
                        if file == archive_path:
                            continue
                        try:
                            dest = self.resolve_conflict(trash_dir / file.name)
                            shutil.move(str(file), str(dest))
                            success_count += 1
                        except Exception as e:
                            errors.append(f"Erreur de suppression après archivage pour {file.name} : {str(e)}")
            except Exception as e:
                errors.append(f"Erreur de création du fichier ZIP : {str(e)}")
                if archive_path.exists():
                    archive_path.unlink()
                return 0, None, errors
                
            return success_count, archive_path, errors
        
        return 0, None, ["Action non reconnue"]
