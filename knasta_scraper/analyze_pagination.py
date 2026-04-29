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
        if 'initialData' in pageProps:
            products = pageProps['initialData'].get('products', [])
            print(f"Page {pageProps['initialData'].get('page')}/{pageProps['initialData'].get('total_pages')}")
            print(f"Number of products: {len(products)}")
            if products:
                p = products[0]
                print(f"First product: {p.get('title')} - ${p.get('current_price')} - https://knasta.cl{p.get('url')}")
    else:
        print("No NEXT_DATA found")

print("Page 1:")
fetch_knasta('https://knasta.cl/results?knastaday=1')
print("\nPage 2:")
fetch_knasta('https://knasta.cl/results?knastaday=1&page=2')

# Let's also test 'ofertas tecno' (category 20000 or similar?)
print("\nOfertas tecno:")
fetch_knasta('https://knasta.cl/results?category=20106&knastaday=7')
