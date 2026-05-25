import unittest
import tempfile
from pathlib import Path
import cabinet.i18n as i18n

class TestI18n(unittest.TestCase):
    def setUp(self):
        # Redirect config directory and settings file to avoid polluting real user config
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_config_dir = Path(self.temp_dir.name) / "config"
        self.temp_settings_file = self.temp_config_dir / "settings.json"
        
        self.original_config_dir = i18n.CONFIG_DIR
        self.original_settings_file = i18n.SETTINGS_FILE
        
        i18n.CONFIG_DIR = self.temp_config_dir
        i18n.SETTINGS_FILE = self.temp_settings_file
        
        # Reset local variable state inside i18n module
        i18n._current_lang = None

    def tearDown(self):
        i18n.CONFIG_DIR = self.original_config_dir
        i18n.SETTINGS_FILE = self.original_settings_file
        self.temp_dir.cleanup()

    def test_default_language_detection(self):
        """Verify that get_current_language returns a fallback value when no config file exists."""
        lang = i18n.get_current_language()
        self.assertIn(lang, ["en", "fr"])

    def test_set_and_get_language(self):
        """Verify that set_language changes the language and stores it persistently in the settings file."""
        i18n.set_language("en")
        self.assertEqual(i18n.get_current_language(), "en")
        self.assertTrue(self.temp_settings_file.exists())
        
        # Reset state and load from file
        i18n._current_lang = None
        self.assertEqual(i18n.get_current_language(), "en")

        # Switch language to French
        i18n.set_language("fr")
        self.assertEqual(i18n.get_current_language(), "fr")

    def test_translation_helper(self):
        """Verify that the translation function properly maps keys for French and English."""
        i18n.set_language("en")
        self.assertEqual(i18n.t("yes"), "Yes")
        self.assertEqual(i18n.t("no"), "No")
        self.assertEqual(i18n.t("folder_clean", name="Downloads"), "Your Downloads folder (Downloads) is already clean! No files to organize.")

        i18n.set_language("fr")
        self.assertEqual(i18n.t("yes"), "Oui")
        self.assertEqual(i18n.t("no"), "Non")
        self.assertEqual(i18n.t("folder_clean", name="Downloads"), "Votre dossier Téléchargements (Downloads) est déjà propre ! Aucun fichier à ranger.")

    def test_nonexistent_key_fallback(self):
        """Verify that the translation function returns the key itself as a fallback if not found."""
        self.assertEqual(i18n.t("non_existent_key_1234"), "non_existent_key_1234")

if __name__ == "__main__":
    unittest.main()
