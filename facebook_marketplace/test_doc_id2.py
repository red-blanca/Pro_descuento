import facebook_api as fb
import json

cookies = fb.load_cookies()
html = fb._http_get('https://www.facebook.com/marketplace/santiago/search/?query=notebook+gamer', cookies)
listings, cursor, payloads = fb._extract_listings_from_html(html)

doc_id = "27402946195973808"
vars_found = None

def _search(obj, depth=0):
    global vars_found
    if depth > 15: return
    if isinstance(obj, dict):
        qid = obj.get("queryID") or obj.get("query_id") or obj.get("id")
        if str(qid) == doc_id:
            vars_found = obj.get("variables")
        for v in obj.values():
            _search(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _search(item, depth + 1)

for p in payloads:
    _search(p)

if vars_found:
    print("Found vars!")
    vars_found["cursor"] = cursor
    vars_found["count"] = 24
    
    data = {
        "fb_dtsg": fb._extract_fb_dtsg(html),
        "doc_id": doc_id,
        "variables": json.dumps(vars_found),
        "__user": cookies.get("c_user"),
        "__a": "1"
    }
    
    raw = fb._http_post_graphql('https://www.facebook.com/api/graphql/', cookies, data, timeout=30)
    print("RAW length:", len(raw))
    print("Error:", "error" in raw.lower())
    
    # Try parsing
    page_items = []
    for line in raw.splitlines():
        if line.startswith("{"):
            try:
                p = json.loads(line)
                edges = fb._deep_find_edges(p)
                for edge in edges:
                    it = fb._listing_from_edge(edge)
                    if it: page_items.append(it)
            except: pass
    print("Extracted items:", len(page_items))
else:
    print("Vars not found")
