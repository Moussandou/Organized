import unittest
from pathlib import Path
import tempfile
import cabinet.history as history

class TestHistory(unittest.TestCase):
    def setUp(self):
        # Redirect history file path to a temporary location
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_history_file = Path(self.temp_dir.name) / "history.json"
        
        self.original_history_file = history.HISTORY_FILE
        history.HISTORY_FILE = self.temp_history_file

    def tearDown(self):
        history.HISTORY_FILE = self.original_history_file
        self.temp_dir.cleanup()

    def test_save_and_retrieve_session(self):
        """Verify saving and retrieving sessions from the history file."""
        # 1. Ensure no history exists initially
        self.assertIsNone(history.get_last_session())
        
        # 2. Record an organization session
        moves = [
            {"source": "a.txt", "dest": "b.txt"}
        ]
        history.save_session(moves, "category")
        
        # 3. Retrieve recorded session details
        last = history.get_last_session()
        self.assertIsNotNone(last)
        self.assertEqual(last["strategy"], "category")
        self.assertEqual(len(last["moves"]), 1)
        self.assertEqual(last["moves"][0]["source"], "a.txt")
        self.assertEqual(last["moves"][0]["dest"], "b.txt")
        
        # 4. Pop and delete the last session
        popped = history.pop_last_session()
        self.assertEqual(popped["strategy"], "category")
        self.assertIsNone(history.get_last_session())

if __name__ == "__main__":
    unittest.main()
