import unittest
from dataclasses import dataclass
from typing import List

# Add the project root to the path if necessary to find the analysis module
# import sys
# sys.path.insert(0, '..')
from analysis import V2Scorer, NormalizedRace, ScoreResult

# --- Mock Data Structures ---
# These mock objects simulate the necessary attributes of the real data classes
# for testing purposes without needing the full normalization pipeline.

@dataclass
class MockRunner:
    """A simplified runner object for testing."""
    odds_decimal: float

@dataclass
class MockRace:
    """A simplified race object for testing."""
    runners: List[MockRunner]

# --- Test Cases ---

class TestV2Scorer(unittest.TestCase):

    def setUp(self):
        """Set up a V2Scorer instance before each test."""
        # The config is not used by the scoring methods themselves, so an empty dict is fine.
        self.scorer = V2Scorer(config={})

    def test_fav_vs_field_ratio_score_strong_favorite(self):
        """
        Test with a strong favorite (e.g., 1.5 odds) against a field of outsiders.
        The ratio should be low, resulting in a low score.
        """
        runners = [MockRunner(1.5), MockRunner(5.0), MockRunner(8.0), MockRunner(12.0)]
        expected_score = 40.0
        score, ratio = self.scorer._get_fav_vs_field_ratio_score(runners)
        self.assertEqual(score, expected_score)
        self.assertAlmostEqual(ratio, 0.226, places=3)

    def test_fav_vs_field_ratio_score_open_race(self):
        """
        Test with an open race where the favorite's odds are close to the average.
        The ratio should be high, resulting in a high score.
        """
        runners = [MockRunner(3.5), MockRunner(4.0), MockRunner(5.0), MockRunner(6.0)]
        expected_score = 90.0
        score, ratio = self.scorer._get_fav_vs_field_ratio_score(runners)
        self.assertEqual(score, expected_score)
        self.assertAlmostEqual(ratio, 0.757, places=3)

    def test_fav_vs_field_ratio_score_very_open_race(self):
        """
        Test with a very open race where the favorite's odds are near the average.
        The ratio should be close to 1.0, resulting in the max score.
        """
        runners = [MockRunner(4.0), MockRunner(4.5), MockRunner(5.0), MockRunner(5.5)]
        expected_score = 100.0
        score, ratio = self.scorer._get_fav_vs_field_ratio_score(runners)
        self.assertEqual(score, expected_score)
        self.assertAlmostEqual(ratio, 0.842, places=3)

    def test_fav_vs_field_ratio_score_insufficient_runners(self):
        """
        Test the edge case where there are fewer than 3 runners with odds.
        The function should return a default low score.
        """
        runners = [MockRunner(2.0), MockRunner(3.0)]
        expected_score = 20.0
        score, ratio = self.scorer._get_fav_vs_field_ratio_score(runners)
        self.assertEqual(score, expected_score)
        self.assertEqual(ratio, 0.0)

    def test_full_score_race_integration(self):
        """
        Test the main `score_race` method to ensure all signals are
        integrated correctly with the weights.
        """
        runners_data = [
            {'name': 'Horse A', 'saddle_cloth': '1', 'odds_decimal': 3.5},
            {'name': 'Horse B', 'saddle_cloth': '2', 'odds_decimal': 4.0},
            {'name': 'Horse C', 'saddle_cloth': '3', 'odds_decimal': 5.0},
            {'name': 'Horse D', 'saddle_cloth': '4', 'odds_decimal': 6.0},
        ]

        # Use a more robust mock that can be created dynamically
        runners = [type('NormalizedRunner', (object,), r)() for r in runners_data]

        race = NormalizedRace(
            race_key="test_track::r1430",
            track_key="test_track",
            start_time_iso="2025-01-01T14:30:00Z",
            runners=runners
        )

        # Expected scores for each component
        field_size_score = 60.0  # 4 runners
        fav_odds_score = 80.0    # 3.5 odds
        spread_score = 50.0      # 0.5 spread
        fav_ratio_score = 90.0   # From the open_race test

        # Calculate expected final score using the default weights from V2Scorer
        weights = self.scorer.weights
        expected_final_score = (
            (field_size_score * weights["FIELD_SIZE"]) +
            (fav_odds_score * weights["FAVORITE_ODDS"]) +
            (spread_score * weights["ODDS_SPREAD"]) +
            (fav_ratio_score * weights["VALUE_VS_SP"])
        ) # (60*0.25)+(80*0.35)+(50*0.10)+(90*0.30) = 15+28+5+27 = 75.0

        result = self.scorer.score_race(race)
        self.assertIsInstance(result, ScoreResult)
        self.assertEqual(result.score, round(expected_final_score, 2))

        # Check that the reason string now uses the new, clearer label
        self.assertIn("FavRatio: 0.76(90)", result.reason)


if __name__ == '__main__':
    unittest.main(verbosity=2)
