import global_search

def test():
    items = [{"title": "Cargador de notebook GE2412035135"}]
    filtered = global_search._filter_words(items, [], [], smart_filter=True, query="notebook")
    print(f"Filtered count: {len(filtered)}")

if __name__ == "__main__":
    test()
