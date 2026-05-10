import json
import re
import unicodedata

def normalize(v: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(v))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()

ACCESSORY_WORDS = {
    "repuesto", "carcasa", "funda", "bolso", "estuche", "mica", "protector",
    "cargador", "cable", "servicio", "reparacion", "arreglo", "tecnico",
    "manual", "caja", "sticker", "calcomania", "mini", "compatible", "para",
    "soporte", "adaptador", "bateria", "vidrio", "templado", "lamina",
    "desarme", "placa", "pantalla", "teclado", "bisagra", "flex", "cooler",
    "ventilador", "pin", "jack", "motherboard", "correa"
}

with open("global_search_1778039663714.json", "r", encoding="utf-8") as f:
    items = json.load(f)

query_words = {"notebook"}

junk_passed = []
suspicious_items = []

good_keywords = {"notebook", "laptop", "macbook", "hp", "lenovo", "asus", "acer", "dell", "msi", "samsung", "lg", "huawei", "apple", "thinkpad", "ideapad", "pavilion", "omen", "predator", "alienware", "nitro", "vivobook", "zenbook", "probook", "elitebook", "chromebook", "netbook", "ultrabook", "yoga", "spectre", "envy", "xps", "surface"}

for item in items:
    title = item.get("title") or item.get("name") or ""
    title_lc = normalize(title)
    title_words_list = title_lc.split()
    title_words = set(title_words_list)
    
    # Simulate smart filter
    found_accessories = title_words & ACCESSORY_WORDS
    filtered_out = False
    if found_accessories and not (found_accessories & query_words):
        if "para" in found_accessories or "compatible" in found_accessories:
            filtered_out = True
        else:
            is_bundle = any(w in title_words for w in ["+", "mas", "regalo", "incluye", "gratis"]) or "+" in title_lc
            if not is_bundle:
                filtered_out = True
            else:
                first_acc_idx = min([title_words_list.index(w) for w in found_accessories if w in title_words_list], default=999)
                first_query_idx = min([title_words_list.index(w) for w in query_words if w in title_words_list], default=999)
                if first_acc_idx < first_query_idx:
                    filtered_out = True

    if not filtered_out:
        junk_passed.append(title)
        if not any(kw in title_lc for kw in good_keywords):
             suspicious_items.append(title)

print(f"Total items: {len(items)}")
print(f"Items passing smart filter: {len(junk_passed)}")
print(f"Suspicious items (no brand/keyword) passing: {len(suspicious_items)}")
print("\nSample of suspicious items:")
for t in suspicious_items[:100]:
    print(" -", t)
