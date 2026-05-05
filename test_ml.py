import urllib.request
from mercadolibre import fetch_url_html

url = "https://listado.mercadolibre.cl/audifonos_ITEM*CONDITION_2230581"
try:
    html = fetch_url_html(url)
    print("HTML length:", len(html))
    print("Has _n.ctx.r=", "_n.ctx.r=" in html)
    print("Has window.__PRELOADED_STATE__", "window.__PRELOADED_STATE__" in html)
    print("Has initialState", "initialState" in html)
    if not "_n.ctx.r=" in html:
        print("Looking for other JSON patterns...")
        with open('out.html', 'w', encoding='utf-8') as f:
            f.write(html)
except Exception as e:
    print("ERROR:", e)
