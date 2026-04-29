import facebook_api as fb
import json

cookies = fb.load_cookies()
html = fb._http_get('https://www.facebook.com/marketplace/santiago/search/?query=notebook+gamer', cookies)
_, _, payloads = fb._extract_listings_from_html(html)

def _search(obj, depth=0):
    if depth > 15:
        return
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and item.isdigit() and len(item) > 10:
                print(f"Found doc_id: {item}")
                # check nearby
                for j in range(max(0, i-2), min(len(obj), i+3)):
                    if isinstance(obj[j], dict):
                        print("Neighbor:", json.dumps(obj[j])[:100])
            _search(item, depth + 1)
    elif isinstance(obj, dict):
        qid = obj.get("queryID") or obj.get("query_id") or obj.get("id")
        if isinstance(qid, str) and qid.isdigit() and len(qid) > 10:
            print(f"Found queryID: {qid} in dict: {json.dumps(obj)[:200]}")
            
        for v in obj.values():
            _search(v, depth + 1)

for p in payloads:
    _search(p)
