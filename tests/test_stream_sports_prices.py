import unittest

from src.stream_sports_prices import (
    extract_asset_ids,
    is_sports_market,
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

    def test_is_sports_market_from_category_or_tags(self) -> None:
        self.assertTrue(is_sports_market({"category": "Sports"}, "Sports"))
        self.assertTrue(is_sports_market({"tags": [{"slug": "sports"}]}, "Sports"))
        self.assertFalse(is_sports_market({"category": "Politics"}, "Sports"))

    def test_extract_asset_ids_deduplicates(self) -> None:
        markets = [
            {"clobTokenIds": '["1","2"]'},
            {"tokens": [{"token_id": "2"}, {"tokenId": "3"}]},
        ]
        self.assertEqual(extract_asset_ids(markets), ["1", "2", "3"])

    def test_maybe_collect_events_filters_non_market_payload(self) -> None:
        heartbeat = {"type": "subscribed", "channel": "market"}
        self.assertEqual(maybe_collect_events(heartbeat, connection_id=1), [])

        event = {"asset_id": "abc", "price": "0.5"}
        rows = maybe_collect_events(event, connection_id=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_id"], "abc")


if __name__ == "__main__":
    unittest.main()
