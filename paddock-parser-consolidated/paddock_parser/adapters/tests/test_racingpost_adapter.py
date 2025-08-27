import unittest
from unittest.mock import Mock
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from paddock_parser.adapters.racingpost import RacingPostAdapter

class TestRacingPostAdapter(unittest.TestCase):

    def setUp(self):
        mock_config_manager = Mock()
        self.adapter = RacingPostAdapter(config_manager=mock_config_manager)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.sample_html_path = os.path.join(self.current_dir, 'racingpost_sample.html')

        try:
            with open(self.sample_html_path, 'r', encoding='utf-8') as f:
                self.html_content = f.read()
        except FileNotFoundError:
            self.html_content = None

    def test_parse_and_normalize_racecard(self):
        self.assertIsNotNone(self.html_content, "racingpost_sample.html could not be found or read.")

        races = self.adapter._parse_and_normalize_racecard(self.html_content)

        # Based on the adapter's logic, it should find races in the JSON
        self.assertGreater(len(races), 0, "No races were parsed from the sample HTML.")

        # Test the first race for correct structure
        first_race = races[0]
        self.assertIsInstance(first_race.race_key, str)
        self.assertIsInstance(first_race.track_key, str)
        self.assertIsInstance(first_race.start_time_iso, str)
        self.assertTrue(len(first_race.runners) > 0)

        # Test the first runner for correct structure
        first_runner = first_race.runners[0]
        self.assertIsInstance(first_runner.runner_id, str)
        self.assertIsInstance(first_runner.name, str)
        self.assertIsInstance(first_runner.saddle_cloth, str)

if __name__ == '__main__':
    unittest.main()
