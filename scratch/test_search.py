import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import global_search

config = {
    "query": "teclado",
    "sources": ["mercadolibre", "travel", "tuganga"],
    "scan_scope": "complete",
    "max_items_per_source": 10000,
    "min_price": 0,
    "max_price": 0,
    "min_discount": 0,
    "include_words": [],
    "exclude_words": [],
    "sort_price": False,
    "include_international": False,
    "travel_category_id": "",
    "tuganga_mode": "search",
    "tuganga_categories": [],
    "strict_mode": False,
    "smart_filter": True
}

print("Running global search...")
try:
    res = global_search.run_global_search(config)
    print("Search completed successfully!")
    print(f"Total count: {res['total_count']}")
    for run in res['runs']:
        print(f"Source: {run['source']}, ok: {run['ok']}, count: {run['count']}, error: {run.get('error')}")
except Exception as e:
    import traceback
    print("Search crashed with exception:")
    traceback.print_exc()
