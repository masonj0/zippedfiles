import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from datetime import datetime

from paddock_parser.adapters.fanduel_adapter import FanDuelAdapter
from paddock_parser.normalizer import NormalizedRace

# Sample JSON response for the schedule (Phase 1)
SAMPLE_SCHEDULE_RESPONSE = {
    "data": {
        "scheduleRaces": [
            {
                "id": "T1",
                "name": "Harness Park",
                "races": [
                    {
                        "id": "HP-1",
                        "tvgRaceId": 12345,
                        "number": 1,
                        "postTime": "2025-08-26T20:00:00Z",
                        "type": {"code": "H"},
                    },
                    {
                        "id": "HP-2",
                        "tvgRaceId": 67890,
                        "number": 2,
                        "postTime": "2025-08-26T20:30:00Z",
                        "type": {"code": "Q"},  # Should be filtered out
                    }
                ]
            }
        ]
    }
}

# Sample JSON response for race details (Phase 2)
SAMPLE_DETAILS_RESPONSE = {
    "data": {
        "races": [
            {
                "id": "HP-1",
                "tvgRaceId": 12345,
                "bettingInterests": [
                    {
                        "biNumber": 1,
                        "currentOdds": {"numerator": 12, "denominator": 1, "typename": "Odd"},
                        "runners": [{"scratched": False, "horseName": "Speedy", "jockey": "J. Doe", "trainer": "T. Roe"}]
                    },
                    {
                        "biNumber": 2,
                        "currentOdds": {"numerator": 5, "denominator": 2, "typename": "Odd"},
                        "runners": [{"scratched": True, "horseName": "Pacer", "jockey": "A. Smith", "trainer": "B. Jones"}]
                    }
                ]
            }
        ]
    }
}


class TestFanDuelAdapter(unittest.TestCase):

    @patch('httpx.AsyncClient')
    def test_fetch_two_stage_process(self, mock_async_client):
        # Arrange
        # This mock will handle both API calls by inspecting the request payload
        async def side_effect(*args, **kwargs):
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200

            payload = kwargs.get("json", {})
            operation_name = payload.get("operationName")

            if operation_name == "getLhnInfo":
                mock_response.json.return_value = SAMPLE_SCHEDULE_RESPONSE
            elif operation_name == "getGraphRaceBettingInterest":
                mock_response.json.return_value = SAMPLE_DETAILS_RESPONSE
            else:
                mock_response.status_code = 400
                mock_response.json.return_value = {"error": "Unknown operation"}

            return mock_response

        mock_post = AsyncMock(side_effect=side_effect)
        mock_client_instance = AsyncMock()
        mock_client_instance.post = mock_post
        mock_async_client.return_value.__aenter__.return_value = mock_client_instance

        adapter = FanDuelAdapter()

        # Act
        results = asyncio.run(adapter.fetch())

        # Assert
        # Check that post was called twice (once for schedule, once for details)
        self.assertEqual(mock_client_instance.post.call_count, 2)

        # Check that we got exactly one race (the Harness race)
        self.assertEqual(len(results), 1)

        # Check the normalized race object
        race = results[0].document
        self.assertIsInstance(race, NormalizedRace)
        self.assertEqual(race.race_id, "HP-1")
        self.assertEqual(race.track_name, "Harness Park")
        self.assertEqual(race.race_number, 1)
        self.assertEqual(race.race_type, "H")
        self.assertEqual(len(race.runners), 2)

        # Check the first runner
        runner1 = race.runners[0]
        self.assertEqual(runner1.name, "Speedy")
        self.assertEqual(runner1.runner_number, 1)
        self.assertEqual(runner1.jockey, "J. Doe")
        self.assertEqual(runner1.trainer, "T. Roe")
        self.assertFalse(runner1.is_scratched)
        self.assertEqual(runner1.odds, 12.0) # 12 / 1

        # Check the second runner (scratched)
        runner2 = race.runners[1]
        self.assertEqual(runner2.name, "Pacer")
        self.assertEqual(runner2.runner_number, 2)
        self.assertTrue(runner2.is_scratched)
        self.assertEqual(runner2.odds, 2.5) # 5 / 2


if __name__ == '__main__':
    unittest.main()
