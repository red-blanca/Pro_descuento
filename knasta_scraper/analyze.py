import urllib.request
import json
import re

req = urllib.request.Request('https://knasta.cl/', headers={'User-Agent':'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')

match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
if match:
    data = json.loads(match.group(1))
    print("Found NEXT_DATA")
    print("Keys in props:", data.get("props", {}).keys())
    if "pageProps" in data.get("props", {}):
        print("Keys in pageProps:", data["props"]["pageProps"].keys())
else:
    print("No NEXT_DATA found")
    
# Let's also check what urls Knasta uses for 'ofertas de hoy'
# Usually there is an API like https://knasta.cl/api/...
