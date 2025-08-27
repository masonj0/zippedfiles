import unittest
from unittest.mock import Mock
import os
import sys
import datetime as dt

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from paddock_parser.adapters.equibase import EquibaseAdapter

class TestEquibaseAdapter(unittest.TestCase):

    def setUp(self):
        # Mock the ConfigurationManager
        mock_config_manager = Mock()
        self.adapter = EquibaseAdapter(config_manager=mock_config_manager)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.sample_html_path = os.path.join(self.current_dir, 'equibase_sample.html')
        with open(self.sample_html_path, 'r', encoding='utf-8') as f:
            self.html_content = f.read()

    def test_parse_racecard(self):
        races = self.adapter._parse_racecard(self.html_content)

        # There are 10 races in the sample file
        self.assertEqual(len(races), 10)

        # Test the first race in detail
        first_race = races[0]
        self.assertEqual(first_race.track_key, 'saratoga')
        self.assertEqual(first_race.start_time_iso, '2025-08-22T13:10:00')
        self.assertEqual(first_race.race_key, 'saratoga::r1310')
        self.assertEqual(first_race.race_name, 'Maiden Special Weight')
        self.assertEqual(first_race.extras['race_number'], 1)
        self.assertEqual(first_race.extras['purse'], '$90,000')
        self.assertEqual(first_race.extras['distance'], '5 1/2 F')
        self.assertEqual(first_race.extras['surface'], 'Turf')
        self.assertEqual(first_race.extras['starters'], 9)
        self.assertEqual(len(first_race.runners), 0)

        # Test a few fields from the last race to be sure
        last_race = races[9]
        self.assertEqual(last_race.track_key, 'saratoga')
        self.assertEqual(last_race.start_time_iso, '2025-08-22T18:16:00')
        self.assertEqual(last_race.race_key, 'saratoga::r1816')
        self.assertEqual(last_race.race_name, 'Claiming')
        self.assertEqual(last_race.extras['race_number'], 10)
        self.assertEqual(last_race.extras['purse'], '$50,000')

if __name__ == '__main__':
    unittest.main()
