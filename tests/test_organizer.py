import unittest
import shutil
import os
from pathlib import Path
import tempfile
from datetime import datetime, timedelta

from cabinet.organizer import CabinetOrganizer
import cabinet.config as config

class TestOrganizer(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory to simulate the Downloads folder
        self.temp_dir = tempfile.TemporaryDirectory()
        self.downloads_path = Path(self.temp_dir.name).resolve() / "Downloads"
        self.downloads_path.mkdir(parents=True, exist_ok=True)
        
        # Redirect rules file path to prevent altering local config
        self.temp_config_dir = Path(self.temp_dir.name).resolve() / "config"
        self.temp_rules_file = self.temp_config_dir / "rules.json"
        
        self.original_rules_file = config.RULES_FILE
        config.RULES_FILE = self.temp_rules_file
        config.save_rules([])  # Initialize empty rules by default

        self.organizer = CabinetOrganizer(self.downloads_path)

    def tearDown(self):
        config.RULES_FILE = self.original_rules_file
        self.temp_dir.cleanup()

    def test_scan_files_and_filtering(self):
        """Verify directory scanning and temporary file filtering."""
        # 1. Create valid and temporary/hidden files
        (self.downloads_path / "valid.txt").write_text("content")
        (self.downloads_path / "downloading.crdownload").write_text("part")
        (self.downloads_path / ".hidden").write_text("hidden")
        
        scanned = self.organizer.scan_files()
        self.assertEqual(len(scanned), 1)
        self.assertEqual(scanned[0].name, "valid.txt")

    def test_get_destination_strategies(self):
        """Verify destination calculations across different organization strategies."""
        file_path = self.downloads_path / "photo.jpg"
        
        # 1. Category Strategy
        dest = self.organizer.get_destination(file_path, "category")
        self.assertEqual(dest.parent.name, "Images")
        
        # 2. Date Strategy
        dest_date = self.organizer.get_destination(file_path, "date")
        expected_date = datetime.now().strftime("%Y-%m")
        self.assertEqual(dest_date.parent.name, expected_date)
        
        # 3. Extension Strategy
        dest_ext = self.organizer.get_destination(file_path, "extension")
        self.assertEqual(dest_ext.parent.name, "JPG")
        
        # 4. Hybrid Strategy
        dest_hyb = self.organizer.get_destination(file_path, "hybrid")
        self.assertEqual(dest_hyb.parent.parent.name, "Images")
        self.assertEqual(dest_hyb.parent.name, expected_date)

    def test_smart_rules_override(self):
        """Verify that custom Smart Rules take absolute precedence in destination calculations."""
        # Save a custom smart rule
        config.save_rules([{"pattern": "facture", "folder": "Compta/Factures"}])
        
        file_path = self.downloads_path / "facture_internet.pdf"
        dest = self.organizer.get_destination(file_path, "category")
        
        # Target path should map to custom rule location
        self.assertEqual(dest.relative_to(self.downloads_path), Path("Compta/Factures/facture_internet.pdf"))

    def test_conflict_resolution(self):
        """Verify that name collisions trigger numerical counter increments."""
        file_a = self.downloads_path / "test.txt"
        file_a.write_text("a")
        
        # 1. No collision when no file exists at destination
        dest_none = self.downloads_path / "test_other.txt"
        self.assertEqual(self.organizer.resolve_conflict(dest_none), dest_none)
        
        # 2. Direct collision triggers incremented suffix
        resolved = self.organizer.resolve_conflict(file_a)
        self.assertEqual(resolved.name, "test (1).txt")

    def test_find_duplicates(self):
        """Verify duplicate file detection utilizing sizing and SHA-256 hash checks."""
        file_a = self.downloads_path / "a.txt"
        file_a.write_text("identical content")
        
        file_b = self.downloads_path / "b.txt"
        file_b.write_text("identical content")
        
        file_c = self.downloads_path / "c.txt"
        file_c.write_text("different content")
        
        duplicates = self.organizer.find_duplicates(recursive=False)
        self.assertEqual(len(duplicates), 1)
        
        # Ensure a and b are grouped as duplicates
        paths = list(duplicates.values())[0]
        self.assertEqual(len(paths), 2)
        self.assertTrue(file_a in paths)
        self.assertTrue(file_b in paths)

    def test_clean_old_files_zip_and_trash(self):
        """Verify age-based file filtering, archiving, and trashing."""
        # 1. Create an old file
        old_file = self.downloads_path / "vieux.txt"
        old_file.write_text("old")
        past_time = (datetime.now() - timedelta(days=50)).timestamp()
        os.utime(old_file, (past_time, past_time))
        
        # 2. Create a recent file
        recent_file = self.downloads_path / "recent.txt"
        recent_file.write_text("recent")
        
        # 3. Retrieve old files
        old_list = self.organizer.get_old_files(days=30)
        self.assertEqual(len(old_list), 1)
        self.assertEqual(old_list[0].name, "vieux.txt")
        
        # 4. Test archiving into ZIP
        count, archive_path, errors = self.organizer.clean_old_files(days=30, action="archive")
        self.assertEqual(count, 1)
        self.assertIsNotNone(archive_path)
        self.assertTrue(archive_path.exists())
        self.assertFalse(old_file.exists())

if __name__ == "__main__":
    unittest.main()
