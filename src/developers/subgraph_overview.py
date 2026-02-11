import json

from common.http_client import print_json, request_json, require_env

subgraph_url = require_env("SUBGRAPH_URL")

query = {
    "query": "{ markets(first: 3) { id } }",
}

data = request_json("POST", subgraph_url, "", body=query)
print_json(data)
