import os
import shutil
import hashlib
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from cabinet.config import get_category_for_extension, IGNORED_EXTENSIONS, load_rules, DEFAULT_CATEGORIES

class CabinetOrganizer:
    def __init__(self, target_dir: Path):
        self.target_dir = Path(target_dir).expanduser().resolve()

    def scan_files(self) -> List[Path]:
        """Scan and return files and folders at the root (excluding temporary files and category directories)."""
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            return []
        
        # List of target category directories to ignore, avoiding moving them recursively
        ignored_names = set(DEFAULT_CATEGORIES.keys())
        ignored_names.update(["Divers", "Dossiers", "DOSSIERS", "SANS_EXTENSION", "Autres"])
        
        # Also ignore target root directories defined in custom smart rules
        rules = load_rules()
        for rule in rules:
            folder = rule.get("folder", "")
            if folder:
                root_part = Path(folder).parts[0]
                ignored_names.add(root_part)
        
        items = []
        for item in self.target_dir.iterdir():
            # Ignore hidden files and directories
            if item.name.startswith('.'):
                continue
                
            # Ignore target organization folders
            if item.is_dir() and item.name in ignored_names:
                continue
                
            # Ignore temporary extensions and history metadata
            if item.suffix.lower() not in IGNORED_EXTENSIONS and item.name != ".cabinet_history.json":
                items.append(item)
                
        return items

    def scan_all_files_recursive(self) -> List[Path]:
        """Scan and return all files recursively, excluding temporary/hidden paths."""
        if not self.target_dir.exists() or not self.target_dir.is_dir():
            return []
            
        files = []
        for item in self.target_dir.rglob("*"):
            # Ignore hidden items and directories
            if item.is_file() and not item.name.startswith('.'):
                # Ensure the file is not inside a hidden subdirectory
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
        """Calculate the destination path for a file/folder based on matching rules and the selected strategy."""
        # 1. Check custom smart rules (highest priority)
        rules = load_rules()
        for rule in rules:
            pattern = rule.get("pattern", "")
            folder = rule.get("folder", "")
            if pattern and folder and pattern.lower() in file_path.name.lower():
                dest_dir = self.target_dir / folder
                return dest_dir / file_path.name

        # 2. Apply the chosen organization strategy
        suffix = file_path.suffix.lower()
        
        try:
            mtime = file_path.stat().st_mtime
            file_date = datetime.fromtimestamp(mtime)
        except Exception:
            file_date = datetime.now()
            
        date_str = file_date.strftime("%Y-%m")
        category = get_category_for_extension(suffix)
        
        # Fallback categories to "Dossiers" if item is a directory with no other category
        if file_path.is_dir() and category == "Divers":
            category = "Dossiers"
        
        if strategy == "category":
            dest_dir = self.target_dir / category
        elif strategy == "date":
            dest_dir = self.target_dir / date_str
        elif strategy == "extension":
            if file_path.is_dir() and not suffix:
                ext_folder = "DOSSIERS"
            else:
                ext_folder = suffix.replace('.', '').upper() if suffix else "SANS_EXTENSION"
            dest_dir = self.target_dir / ext_folder
        elif strategy == "hybrid":
            dest_dir = self.target_dir / category / date_str
        else:
            dest_dir = self.target_dir / "Divers"
            
        return dest_dir / file_path.name

    def resolve_conflict(self, dest_path: Path) -> Path:
        """Resolve name collisions by appending a counter suffix to the destination file."""
        if not dest_path.exists():
            return dest_path
            
        parent = dest_path.parent
        name = dest_path.style if hasattr(dest_path, "style") else dest_path.stem
        suffix = dest_path.suffix
        
        counter = 1
        new_path = parent / f"{name} ({counter}){suffix}"
        while new_path.exists():
            counter += 1
            new_path = parent / f"{name} ({counter}){suffix}"
            
        return new_path

    def preview_organization(self, files: List[Path], strategy: str) -> Dict[str, List[Tuple[Path, Path]]]:
        """Simulate the organization process without actually moving any files."""
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
        """Perform file moves and track history for undo capability."""
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
                errors.append(f"Error moving {file.name}: {str(e)}")
                
        return moves, errors

    def revert_moves(self, moves: List[Dict[str, str]]) -> Tuple[int, List[str]]:
        """Rollback a list of file moves, returning them to their source locations."""
        reverted_count = 0
        errors = []
        
        for move in reversed(moves):
            source_path = Path(move["source"])
            dest_path = Path(move["dest"])
            
            if not dest_path.exists():
                errors.append(f"Moved file no longer exists: {dest_path.name}")
                continue
                
            try:
                source_path.parent.mkdir(parents=True, exist_ok=True)
                resolved_source = self.resolve_conflict(source_path)
                shutil.move(str(dest_path), str(resolved_source))
                reverted_count += 1
                
                self._clean_empty_parents(dest_path.parent)
            except Exception as e:
                errors.append(f"Could not restore {dest_path.name}: {str(e)}")
                
        return reverted_count, errors

    def _clean_empty_parents(self, path: Path):
        """Recursively remove empty parent directories up to the root target folder."""
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
        """Calculate SHA-256 hash of a file."""
        hash_sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha.update(chunk)
        return hash_sha.hexdigest()

    def find_duplicates(self, recursive: bool = False) -> Dict[str, List[Path]]:
        """Find duplicate files by grouping them by size and SHA-256 hash."""
        files = self.scan_all_files_recursive() if recursive else self.scan_files()
        
        # Group by size first to avoid computing hashes for unique file sizes
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
        
        # Calculate hash only for duplicate size candidates
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
        """Return files that have not been modified for at least X days."""
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
        """Clean up old files by trashing or archiving them."""
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
                    errors.append(f"Error trashing {file.name}: {str(e)}")
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
                            errors.append(f"Error archiving {file.name}: {str(e)}")
                            
                # Move original files to system Trash after successful archiving
                if archive_path.exists():
                    for file in old_files:
                        if file == archive_path:
                            continue
                        try:
                            dest = self.resolve_conflict(trash_dir / file.name)
                            shutil.move(str(file), str(dest))
                            success_count += 1
                        except Exception as e:
                            errors.append(f"Error trashing original after archiving {file.name}: {str(e)}")
            except Exception as e:
                errors.append(f"Error creating ZIP archive: {str(e)}")
                if archive_path.exists():
                    archive_path.unlink()
                return 0, None, errors
                
            return success_count, archive_path, errors
        
        return 0, None, ["Action not recognized"]
