import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Set
from cabinet.config import get_category_for_extension

class CabinetOrganizer:
    def __init__(self, target_dir: Path):
        self.target_dir = Path(target_dir).expanduser().resolve()

    def scan_files(self) -> List[Path]:
        """Scan et retourne uniquement les fichiers présents à la racine du dossier cible."""
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            return []
        
        files = []
        for item in self.target_dir.iterdir():
            # On ignore les dossiers cachés et les fichiers systèmes (ex: .DS_Store)
            if item.is_file() and not item.name.startswith('.'):
                files.append(item)
        return files

    def get_destination(self, file_path: Path, strategy: str) -> Path:
        """Calcule le chemin de destination d'un fichier selon la stratégie choisie."""
        suffix = file_path.suffix.lower()
        
        # Récupération de la date de modification pour le classement temporel
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
            # Si pas d'extension, on met dans "Sans_Extension"
            ext_folder = suffix.replace('.', '').upper() if suffix else "SANS_EXTENSION"
            dest_dir = self.target_dir / ext_folder
        elif strategy == "hybrid":
            # Combinaison : Catégorie puis Date
            dest_dir = self.target_dir / category / date_str
        else:
            # Sécurité par défaut
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
            # Résolution de conflit virtuelle pour la prévisualisation
            resolved_dest = self.resolve_conflict(dest_path)
            
            # Utilisation de la version relative pour l'affichage de l'arborescence
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
                # Création des répertoires parents s'ils n'existent pas
                resolved_dest.parent.mkdir(parents=True, exist_ok=True)
                
                # Déplacement du fichier
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
        
        # On parcourt à l'envers pour restaurer correctement
        for move in reversed(moves):
            source_path = Path(move["source"])
            dest_path = Path(move["dest"])
            
            if not dest_path.exists():
                errors.append(f"Le fichier déplacé n'existe plus : {dest_path.name}")
                continue
                
            try:
                # Si le dossier d'origine a été supprimé, on le recrée
                source_path.parent.mkdir(parents=True, exist_ok=True)
                
                # S'il y a un conflit à la source (par exemple si un nouveau fichier a été créé),
                # on renomme le fichier restauré pour ne rien écraser.
                resolved_source = self.resolve_conflict(source_path)
                
                shutil.move(str(dest_path), str(resolved_source))
                reverted_count += 1
                
                # Nettoyage des dossiers vides créés lors de l'organisation
                self._clean_empty_parents(dest_path.parent)
            except Exception as e:
                errors.append(f"Impossible de restaurer {dest_path.name} : {str(e)}")
                
        return reverted_count, errors

    def _clean_empty_parents(self, path: Path):
        """Supprime récursivement les répertoires vides jusqu'au dossier cible racine."""
        current = path
        # On remonte tant qu'on est dans un sous-dossier du dossier cible
        while current != self.target_dir and current.parts > self.target_dir.parts:
            try:
                if current.exists() and current.is_dir() and not any(current.iterdir()):
                    current.rmdir()
                    current = current.parent
                else:
                    break
            except Exception:
                break
