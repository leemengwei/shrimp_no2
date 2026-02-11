import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(method, base_url, path, params=None, body=None, headers=None):
    params = params or {}
    headers = headers or {}
    url = base_url.rstrip("/") + path
    if params:
        url = f"{url}?{urlencode(params)}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = Request(url, method=method, data=data, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {payload}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc


def request_text(method, base_url, path, params=None, headers=None):
    params = params or {}
    headers = headers or {}
    url = base_url.rstrip("/") + path
    if params:
        url = f"{url}?{urlencode(params)}"

    req = Request(url, method=method, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {payload}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc


def download_file(base_url, path, params=None, output_path=None, headers=None):
    params = params or {}
    headers = headers or {}
    url = base_url.rstrip("/") + path
    if params:
        url = f"{url}?{urlencode(params)}"

    req = Request(url, method="GET", headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            content = resp.read()
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {payload}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc

    if output_path:
        with open(output_path, "wb") as handle:
            handle.write(content)
        return output_path
    return content


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Set {name} in your environment.")
    return value


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=True))
