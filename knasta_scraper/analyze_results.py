import urllib.request
import json
import re

def fetch_knasta(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8')

    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if match:
        data = json.loads(match.group(1))
        pageProps = data.get('props', {}).get('pageProps', {})
        print(f"\nURL: {url}")
        print("Keys in pageProps:", pageProps.keys())
        if 'initialData' in pageProps:
            print("Keys in initialData:", pageProps['initialData'].keys())
            products = pageProps['initialData'].get('products', [])
            print(f"Number of products: {len(products)}")
            if products:
                p = products[0]
                print(f"First product keys: {p.keys()}")
                print(f"First product: {p.get('title')} - {p.get('price')} - {p.get('link')}")
                print(f"Product data: {json.dumps(p)[:200]}")
    else:
        print("No NEXT_DATA found")

fetch_knasta('https://knasta.cl/results?knastaday=1')
fetch_knasta('https://knasta.cl/results?category=20106')
