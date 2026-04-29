import urllib.request
import re

req = urllib.request.Request('https://knasta.cl/results', headers={'User-Agent':'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')

# Search for category patterns
cats = re.findall(r'href="/results\?category=([^"&]+)[^"]*">([^<]+)</a>', html)
print("Categories:", cats)

tiendas = re.findall(r'href="/tienda/([^"]+)"', html)
print("Tiendas:", tiendas)
