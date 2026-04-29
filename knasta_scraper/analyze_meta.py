import urllib.request
import json
import re

req = urllib.request.Request('https://knasta.cl/', headers={'User-Agent':'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')

match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
if match:
    data = json.loads(match.group(1))
    pageProps = data.get('props', {}).get('pageProps', {})
    if 'initialData' in pageProps:
        initialData = pageProps['initialData']
        # Categories
        cat_tree = initialData.get('categories_tree', [])
        for c in cat_tree:
            print(f"Cat {c['category_id']}: {c['title']} (parent {c['parent_category_id']})")
        # Retails
        retails = initialData.get('retails', [])
        print("\nRetails:", [r['retail'] for r in retails[:20]])
