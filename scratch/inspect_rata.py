import urllib.request
import ssl
import re

BASE_URL = "https://descuentosrata.com"
OFFERS_URL = f"{BASE_URL}/oferta"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

headers = {"User-Agent": USER_AGENT}
req = urllib.request.Request(OFFERS_URL, headers=headers)
context = ssl._create_unverified_context()
with urllib.request.urlopen(req, timeout=20, context=context) as response:
    html = response.read().decode("utf-8", errors="ignore")

def clean_html(raw_html: str) -> str:
    clean = re.sub(r'<[^>]+>', '', raw_html)
    clean = " ".join(clean.split())
    return clean

def parse_price(price_str: str) -> int:
    digits = "".join(ch for ch in price_str if ch.isdigit())
    return int(digits) if digits else 0

new_regex = re.compile(r'<a[^>]+href="(/oferta/[^"]+)"[^>]*class="[^"]*text-decoration-none[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
matches = list(new_regex.finditer(html))

offers = []
for match in matches:
    link_path = match.group(1)
    content = match.group(2)
    link = urllib.parse.urljoin(BASE_URL, link_path)
    
    store_match = re.search(r'<h6[^>]*>(.*?)</h6>', content, re.IGNORECASE | re.DOTALL)
    store = clean_html(store_match.group(1)) if store_match else "Desconocido"
    
    title_match = re.search(r'<div[^>]*class="[^"]*line-clamp--3[^"]*"[^>]*>(.*?)</div>', content, re.IGNORECASE | re.DOTALL)
    title = clean_html(title_match.group(1)) if title_match else ""
    
    price_match = re.search(r'<span[^>]*class="[^"]*rata-font-poppins[^"]*"[^>]*>(.*?)</span>', content, re.IGNORECASE | re.DOTALL)
    current_price_str = price_match.group(1) if price_match else ""
    current_price = parse_price(current_price_str)
    
    old_price_match = re.search(r'aria-label="Precio anterior"[^>]*>.*?<small[^>]*>(.*?)</small>', content, re.IGNORECASE | re.DOTALL)
    original_price_str = old_price_match.group(1) if old_price_match else ""
    original_price = parse_price(original_price_str)
    
    img_match = re.search(r'<img[^>]+src="([^"]+)"', content, re.IGNORECASE)
    image = img_match.group(1) if img_match else ""

    discount = 0
    if original_price > current_price and original_price > 0:
        discount = round(((original_price - current_price) / original_price) * 100)

    if title:
        offers.append({
            "title": title,
            "store": store,
            "price": current_price,
            "original_price": original_price,
            "discount_percentage": discount,
            "link": link,
            "image": image,
        })

print("Extracted", len(offers), "offers.")
print("First 5 offers:")
for o in offers[:5]:
    print(o)
