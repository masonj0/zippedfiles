import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from paddock_parser.adapters.fanduel_adapter import FanDuelAdapter
from paddock_parser.normalizer import NormalizedRace
from paddock_parser.config_manager import ConfigurationManager
from paddock_parser.sources import RawRaceDocument

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
                    },
                ],
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
                        "runners": [
                            {
                                "scratched": False,
                                "horseName": "Speedy",
                                "jockey": "J. Doe",
                                "trainer": "T. Roe",
                            }
                        ],
                    },
                    {
                        "biNumber": 2,
                        "currentOdds": {"numerator": 5, "denominator": 2, "typename": "Odd"},
                        "runners": [
                            {
                                "scratched": True,
                                "horseName": "Pacer",
                                "jockey": "A. Smith",
                                "trainer": "B. Jones",
                            }
                        ],
                    },
                ],
            }
        ]
    }
}


class TestFanDuelAdapter(unittest.TestCase):
    @patch("httpx.AsyncClient")
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

        mock_config_manager = MagicMock(spec=ConfigurationManager)
        adapter = FanDuelAdapter(config_manager=mock_config_manager)
        adapter.initialize()  # Initialize the adapter with the mock config

        # Act
        results = asyncio.run(adapter.fetch())

        # Assert
        # Check that post was called twice (once for schedule, once for details)
        self.assertEqual(mock_client_instance.post.call_count, 2)

        # Check that we got exactly one race (the Harness race)
        self.assertEqual(len(results), 1)

        # Check the raw race document
        raw_doc = results[0]
        self.assertIsInstance(raw_doc, RawRaceDocument)
        self.assertEqual(raw_doc.track_key, "harness_park")
        self.assertEqual(raw_doc.race_key, "harness_park::r2000")
        self.assertEqual(len(raw_doc.runners), 2)

        # Check the first runner
        runner1 = raw_doc.runners[0]
        self.assertEqual(runner1.name.value, "Speedy")
        self.assertEqual(runner1.number.value, 1)


if __name__ == "__main__":
    unittest.main()
