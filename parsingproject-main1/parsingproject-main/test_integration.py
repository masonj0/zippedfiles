import unittest
import json
import os
from pathlib import Path

from paddock_parser.config import load_config
from paddock_parser.analysis import V2Scorer
from paddock_parser.config_manager import config_manager

class TestIntegration(unittest.TestCase):
    """
    Integration tests to ensure components work together correctly.
    """

    def setUp(self):
        """
        Set up a temporary configuration file for testing.
        """
        self.test_config_path = "test_config.json"
        self.test_weights = {
            "FIELD_SIZE": 0.1,
            "FAVORITE_ODDS": 0.2,
            "ODDS_SPREAD": 0.3,
            "VALUE_VS_SP": 0.4,
        }
        test_config_data = {
            "SCHEMA_VERSION": "test",
            "APP_NAME": "Test App",
            "SCORER_WEIGHTS": self.test_weights
        }
        with open(self.test_config_path, 'w') as f:
            json.dump(test_config_data, f)

    def tearDown(self):
        """
        Clean up the temporary configuration file.
        """
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

    def test_load_config_success(self):
        """
        Tests that the load_config function can successfully read a JSON file.
        """
        config = load_config(self.test_config_path)
        self.assertIsNotNone(config)
        self.assertEqual(config.get("APP_NAME"), "Test App")
        self.assertIn("SCORER_WEIGHTS", config)

    def test_load_config_not_found(self):
        """
        Tests that the load_config function returns an empty dict
        when the specified file does not exist.
        """
        if os.path.exists("non_existent_config.json"):
            os.remove("non_existent_config.json")

        config = load_config("non_existent_config.json")
        self.assertIsInstance(config, dict)
        self.assertEqual(config, {})

    def test_v2scorer_initialization_with_config(self):
        """
        Tests that the V2Scorer correctly initializes its weights
        from the provided configuration file.
        """
        original_path = config_manager.config_path
        config_manager.config_path = Path(self.test_config_path)
        config_manager._config = config_manager._load_config()

        scorer = V2Scorer()

        total_weight = sum(self.test_weights.values())
        expected_weights = {key: value / total_weight for key, value in self.test_weights.items()}

        self.assertDictEqual(scorer.weights, expected_weights)

        config_manager.config_path = original_path
        config_manager._config = config_manager._load_config()


    def test_v2scorer_initialization_with_missing_weights(self):
        """
        Tests that V2Scorer falls back to default weights if the config
        is missing the SCORER_WEIGHTS section.
        """
        temp_path = "temp_missing_weights_config.json"
        with open(temp_path, 'w') as f:
            json.dump({"APP_NAME": "Test App"}, f)

        original_path = config_manager.config_path
        config_manager.config_path = Path(temp_path)
        config_manager._config = config_manager._load_config()

        scorer = V2Scorer()

        config_manager.config_path = original_path
        config_manager._config = config_manager._load_config()
        os.remove(temp_path)

        default_weights = {
            "FIELD_SIZE": 0.25,
            "FAVORITE_ODDS": 0.35,
            "ODDS_SPREAD": 0.10,
            "VALUE_VS_SP": 0.30,
        }

        self.assertDictEqual(scorer.weights, default_weights)

if __name__ == '__main__':
    unittest.main(verbosity=2)
