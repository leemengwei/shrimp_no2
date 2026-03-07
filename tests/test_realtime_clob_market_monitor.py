import json

from src.realtime_clob_market_monitor import parse_market


def test_parse_market_with_json_strings() -> None:
    raw = {
        "id": "m1",
        "question": "Will BTC be above 120k?",
        "slug": "btc-120k",
        "clobTokenIds": json.dumps(["100", "101"]),
        "outcomes": json.dumps(["Yes", "No"]),
    }
    market = parse_market(raw)
    assert market.market_id == "m1"
    assert market.question == "Will BTC be above 120k?"
    assert len(market.outcomes) == 2
    assert market.outcomes[0].token_id == "100"
    assert market.outcomes[0].outcome == "Yes"


def test_parse_market_with_lists() -> None:
    raw = {
        "conditionId": "m2",
        "name": "Will ETH be above 10k?",
        "clobTokenIds": ["200", "201"],
        "outcomes": ["Yes", "No"],
    }
    market = parse_market(raw)
    assert market.market_id == "m2"
    assert market.question == "Will ETH be above 10k?"
    assert [x.token_id for x in market.outcomes] == ["200", "201"]
