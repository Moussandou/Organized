import unittest
from pathlib import Path
import tempfile
import cabinet.config as config

class TestConfig(unittest.TestCase):
    def setUp(self):
        # Créer un fichier de règles temporaire pour éviter d'altérer la vraie config de l'utilisateur
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_rules_file = Path(self.temp_dir.name) / "rules.json"
        
        # Sauvegarde et redirection
        self.original_rules_file = config.RULES_FILE
        config.RULES_FILE = self.temp_rules_file

    def tearDown(self):
        # Restauration du chemin d'origine
        config.RULES_FILE = self.original_rules_file
        self.temp_dir.cleanup()

    def test_get_category_for_extension(self):
        """Vérifie que la catégorisation par extension fonctionne correctement."""
        self.assertEqual(config.get_category_for_extension(".png"), "Images")
        self.assertEqual(config.get_category_for_extension(".PNG"), "Images")
        self.assertEqual(config.get_category_for_extension(".pdf"), "Documents")
        self.assertEqual(config.get_category_for_extension(".py"), "Code")
        self.assertEqual(config.get_category_for_extension(".mp3"), "Audio")
        self.assertEqual(config.get_category_for_extension(".mp4"), "Video")
        self.assertEqual(config.get_category_for_extension(".zip"), "Archives")
        self.assertEqual(config.get_category_for_extension(".ai"), "Design")
        self.assertEqual(config.get_category_for_extension(".dmg"), "Archives")
        self.assertEqual(config.get_category_for_extension(""), "Divers")
        self.assertEqual(config.get_category_for_extension(".xyzunknown"), "Divers")

    def test_load_save_rules(self):
        """Vérifie la sérialisation/désérialisation des règles de tri."""
        # 1. Par défaut, aucune règle
        self.assertEqual(config.load_rules(), [])
        
        # 2. Ajout de règles
        rules = [{"pattern": "projet", "folder": "Code/Projets"}]
        config.save_rules(rules)
        
        # 3. Rechargement et vérification
        loaded = config.load_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["pattern"], "projet")
        self.assertEqual(loaded[0]["folder"], "Code/Projets")

if __name__ == "__main__":
    unittest.main()
