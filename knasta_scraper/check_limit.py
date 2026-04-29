import urllib.request
import json
import re

def check_page(page):
    url = f"https://knasta.cl/results?page={page}"
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if match:
            data = json.loads(match.group(1))
            props = data.get('props', {}).get('pageProps', {}).get('initialData', {})
            products = props.get('products', [])
            total_pages = props.get('total_pages', 0)
            print(f"Page {page}: {len(products)} products, total_pages: {total_pages}")
        else:
            print(f"Page {page}: No NEXT_DATA")
    except Exception as e:
        print(f"Page {page}: Error {e}")

check_page(1)
check_page(100)
check_page(101)
