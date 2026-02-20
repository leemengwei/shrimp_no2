import os
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen
# 文件路径
src_path = '/home/feifeichouchou/shrimp_no2/docs_for_all_references'
base_dir = '/home/feifeichouchou/shrimp_no2/docs_tmp'
verbose = True

with open(src_path, 'r', encoding='utf-8') as f:
    text = f.read()

urls = re.findall(r'\((https?://[^)\s]+)\)', text)

if verbose:
    print('Found {} URLs'.format(len(urls)), flush=True)

os.makedirs(base_dir, exist_ok=True)

errors = []
for idx, url in enumerate(urls, start=1):
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path
    if not path or path.endswith('/'):
        path = (path or '/') + 'index.html'
    rel_path = os.path.join(host, path.lstrip('/'))
    dest_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        if verbose:
            print('[{}/{}] GET {} -> {}'.format(idx, len(urls), url, dest_path), flush=True)
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=30) as resp:
            content = resp.read()
        with open(dest_path, 'wb') as out:
            out.write(content)
    except Exception as e:
        errors.append((url, str(e)))
        if verbose:
            print('[{}/{}] FAIL {}: {}'.format(idx, len(urls), url, e), flush=True)

print('Downloaded {} of {} URLs'.format(len(urls) - len(errors), len(urls)))
if errors:
    print('Failures:')
    for url, err in errors:
        print('- {}: {}'.format(url, err))


