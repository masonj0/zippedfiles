import unittest
from unittest.mock import patch
from dataclasses import dataclass

from paddock_parser.analysis import V2Scorer
from paddock_parser.normalizer import NormalizedRace, NormalizedRunner

MOCK_CONFIG = {
    "SCORER_WEIGHTS": {
        "FIELD_SIZE": 0.25,
        "FAVORITE_ODDS": 0.35,
        "ODDS_SPREAD": 0.10,
        "VALUE_VS_SP": 0.30,
    },
    "BEST_VALUE_WEIGHTS": {
        "VALUE_ODDS_WEIGHT": 0.6,
        "VALUE_COMPETITIVENESS_WEIGHT": 0.4
    }
}

class TestV2Scorer(unittest.TestCase):
    """
    Unit tests for the V2Scorer class.
    """

    @patch('paddock_parser.analysis.config_manager.get_config', return_value=MOCK_CONFIG)
    def setUp(self, mock_get_config):
        """Set up a new V2Scorer instance before each test."""
        self.scorer = V2Scorer()
        self.race = NormalizedRace(
            race_key="testtrack_2025-08-20_1430",
            track_key="testtrack",
            start_time_iso="2025-08-20T14:30:00Z",
            runners=[
                NormalizedRunner(runner_id="r1", name="Horse A", saddle_cloth="1", odds_decimal=2.0),
                NormalizedRunner(runner_id="r2", name="Horse B", saddle_cloth="2", odds_decimal=3.5),
                NormalizedRunner(runner_id="r3", name="Horse C", saddle_cloth="3", odds_decimal=5.0),
                NormalizedRunner(runner_id="r4", name="Horse D", saddle_cloth="4", odds_decimal=10.0),
                NormalizedRunner(runner_id="r5", name="Horse E", saddle_cloth="5", odds_decimal=12.0),
                NormalizedRunner(runner_id="r6", name="Horse F", saddle_cloth="6", odds_decimal=20.0),
            ]
        )

    def test_field_size_score(self):
        self.assertEqual(self.scorer._get_field_size_score(2), 20.0)
        self.assertEqual(self.scorer._get_field_size_score(4), 60.0)
        self.assertEqual(self.scorer._get_field_size_score(6), 100.0)
        self.assertEqual(self.scorer._get_field_size_score(9), 80.0)
        self.assertEqual(self.scorer._get_field_size_score(11), 40.0)
        self.assertEqual(self.scorer._get_field_size_score(15), 20.0)

    def test_fav_odds_score(self):
        self.assertEqual(self.scorer._get_fav_odds_score(1.4), 60.0)
        self.assertEqual(self.scorer._get_fav_odds_score(2.0), 100.0)
        self.assertEqual(self.scorer._get_fav_odds_score(3.0), 80.0)
        self.assertEqual(self.scorer._get_fav_odds_score(5.0), 50.0)
        self.assertEqual(self.scorer._get_fav_odds_score(7.0), 30.0)
        self.assertEqual(self.scorer._get_fav_odds_score(None), 20.0)

    def test_odds_spread_score(self):
        self.assertEqual(self.scorer._get_odds_spread_score(2.0, 5.0), 100.0)
        self.assertEqual(self.scorer._get_odds_spread_score(2.0, 3.5), 80.0)
        self.assertEqual(self.scorer._get_odds_spread_score(2.0, 2.6), 50.0)
        self.assertEqual(self.scorer._get_odds_spread_score(2.0, 2.2), 30.0)
        self.assertEqual(self.scorer._get_odds_spread_score(None, 2.2), 20.0)

    def test_best_value_score(self):
        runners_with_odds = sorted(self.race.runners, key=lambda r: r.odds_decimal)
        score, reason = self.scorer._get_best_value_score(runners_with_odds)
        self.assertIsNotNone(score)
        self.assertIn("Value Pick: Horse C", reason)
        self.assertAlmostEqual(score, 100.0)

    def test_score_race_integration(self):
        result = self.scorer.score_race(self.race)
        self.assertIsInstance(result, ScoreResult)
        self.assertGreater(result.score, 0)
        self.assertIsNotNone(result.best_value_score)

if __name__ == '__main__':
    unittest.main()
