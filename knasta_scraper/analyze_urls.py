import urllib.request
import re

req = urllib.request.Request('https://knasta.cl/', headers={'User-Agent':'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')

print('Ofertas URLs:', set(re.findall(r'href="([^"]*oferta[^"]*)"', html)))
print('Tecno URLs:', set(re.findall(r'href="([^"]*tecno[^"]*)"', html)))
print('All URLs:', set(re.findall(r'href="([^"]*)"', html)) - set(['/', '#']))
