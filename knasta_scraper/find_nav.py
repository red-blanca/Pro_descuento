import urllib.request
import re

req = urllib.request.Request('https://knasta.cl/', headers={'User-Agent':'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')

# Find all links and their text
links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html)
print("Links found:")
for url, text in links:
    if url.startswith('/'):
        print(f"Text: {text.strip()} -> URL: {url}")
