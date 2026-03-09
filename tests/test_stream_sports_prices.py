import unittest

from src.stream_sports_prices import (
    extract_asset_ids,
    make_connection_batches,
    maybe_collect_events,
)


class StreamSportsPricesTests(unittest.TestCase):
    def test_make_connection_batches_keeps_all_assets(self) -> None:
        asset_ids = [str(i) for i in range(10)]
        batches = make_connection_batches(asset_ids, batch_size=2, max_connections=2)
        flattened = [item for batch in batches for item in batch]
        self.assertEqual(set(flattened), set(asset_ids))
        self.assertEqual(len(flattened), len(asset_ids))
        self.assertLessEqual(len(batches), 2)

    def test_extract_asset_ids_deduplicates(self) -> None:
        markets = [
            {"clobTokenIds": '["1","2"]'},
            {"tokens": [{"token_id": "2"}, {"tokenId": "3"}]},
        ]
        self.assertEqual(extract_asset_ids(markets), ["1", "2", "3"])

    def test_maybe_collect_events_filters_non_market_payload(self) -> None:
        heartbeat = {"type": "subscribed", "channel": "market"}
        self.assertEqual(maybe_collect_events(heartbeat, connection_id=1), [])

        event = {"event_type": "book", "asset_id": "abc", "price": "0.5"}
        rows = maybe_collect_events(event, connection_id=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_id"], "abc")

    def test_maybe_collect_events_expands_price_change_payload(self) -> None:
        payload = {
            "event_type": "price_change",
            "market": "m1",
            "timestamp": 123456,
            "price_changes": [
                {"asset_id": "a1", "price": "0.4", "best_bid": "0.39", "best_ask": "0.41"},
                {"asset_id": "a2", "price": "0.6", "best_bid": "0.59", "best_ask": "0.61"},
            ],
        }
        rows = maybe_collect_events(payload, connection_id=7)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["market"], "m1")
        self.assertEqual(rows[0]["event_type"], "price_change")
        self.assertEqual(rows[1]["asset_id"], "a2")


if __name__ == "__main__":
    unittest.main()
