import unittest
from pathlib import Path
import tempfile
import cabinet.history as history

class TestHistory(unittest.TestCase):
    def setUp(self):
        # Redirection du fichier d'historique vers un fichier temporaire
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_history_file = Path(self.temp_dir.name) / "history.json"
        
        self.original_history_file = history.HISTORY_FILE
        history.HISTORY_FILE = self.temp_history_file

    def tearDown(self):
        history.HISTORY_FILE = self.original_history_file
        self.temp_dir.cleanup()

    def test_save_and_retrieve_session(self):
        """Vérifie que la sauvegarde et la récupération de session fonctionnent."""
        # 1. Pas d'historique initial
        self.assertIsNone(history.get_last_session())
        
        # 2. Enregistrement d'une session
        moves = [
            {"source": "a.txt", "dest": "b.txt"}
        ]
        history.save_session(moves, "category")
        
        # 3. Récupération
        last = history.get_last_session()
        self.assertIsNotNone(last)
        self.assertEqual(last["strategy"], "category")
        self.assertEqual(len(last["moves"]), 1)
        self.assertEqual(last["moves"][0]["source"], "a.txt")
        self.assertEqual(last["moves"][0]["dest"], "b.txt")
        
        # 4. Suppression (pop)
        popped = history.pop_last_session()
        self.assertEqual(popped["strategy"], "category")
        self.assertIsNone(history.get_last_session())

if __name__ == "__main__":
    unittest.main()
