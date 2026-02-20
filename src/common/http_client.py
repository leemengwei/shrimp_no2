import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen, ProxyHandler, build_opener, install_opener


def request_json(method, base_url, path, params=None, body=None, headers=None, timeout=30):
    params = params or {}
    headers = headers or {}
    # Use a browser-like User-Agent and sensible Accept header to avoid simple bot blocks
    headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    )
    headers.setdefault("Accept", "application/json, text/plain, */*")
    url = base_url.rstrip("/") + path
    if params:
        url = f"{url}?{urlencode(params)}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = Request(url, method=method, data=data, headers=headers)

    # Set up proxy if HTTPS_PROXY is set
    proxy_handler = None
    https_proxy = os.getenv("HTTPS_PROXY")
    if https_proxy:
        proxy_handler = ProxyHandler({'https': https_proxy, 'http': https_proxy})
        opener = build_opener(proxy_handler)
        install_opener(opener)

    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {payload}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc


def request_text(method, base_url, path, params=None, headers=None, timeout=30):
    params = params or {}
    headers = headers or {}
    headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    )
    headers.setdefault("Accept", "text/plain, */*")
    url = base_url.rstrip("/") + path
    if params:
        url = f"{url}?{urlencode(params)}"

    req = Request(url, method=method, headers=headers)

    # Set up proxy if HTTPS_PROXY is set
    https_proxy = os.getenv("HTTPS_PROXY")
    if https_proxy:
        proxy_handler = ProxyHandler({'https': https_proxy, 'http': https_proxy})
        opener = build_opener(proxy_handler)
        install_opener(opener)

    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {payload}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc


def download_file(base_url, path, params=None, output_path=None, headers=None, timeout=60):
    params = params or {}
    headers = headers or {}
    headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    )
    headers.setdefault("Accept", "*/*")
    url = base_url.rstrip("/") + path
    if params:
        url = f"{url}?{urlencode(params)}"

    req = Request(url, method="GET", headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
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
