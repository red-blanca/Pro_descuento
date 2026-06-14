import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "descuentosrata_scraper"))

import descuentosrata_api as api


def offer(offer_id: int, title: str, active: bool = True) -> dict:
    return {
        "id": offer_id,
        "slug": title.lower().replace(" ", "-"),
        "nombre": title,
        "tienda_nombre": "Tienda",
        "monto": "10000",
        "monto_anterior": "20000",
        "imagen": "https://example.com/image.jpg",
        "activo": active,
    }


class DescuentosRataApiTests(unittest.TestCase):
    def test_fetch_api_offers_follows_pagination(self) -> None:
        pages = [
            {"results": [offer(1, "Oferta uno")], "next": "https://example.com/page-2"},
            {"results": [offer(2, "Oferta dos", active=False)], "next": None},
        ]

        with patch.object(api, "fetch_json", side_effect=pages) as fetch_json:
            results = api.fetch_api_offers()

        self.assertEqual(2, len(results))
        self.assertEqual(["Oferta uno", "Oferta dos"], [item["title"] for item in results])
        self.assertEqual([True, False], [item["active"] for item in results])
        self.assertEqual(2, fetch_json.call_count)

    def test_execute_search_filters_api_results(self) -> None:
        offers = [
            api.normalize_api_offer(offer(1, "Notebook gamer")),
            api.normalize_api_offer(offer(2, "Monitor gamer")),
        ]

        with patch.object(api, "fetch_api_offers", return_value=offers):
            result = api.execute_search(api.SearchOptions(query="monitor", limit=10))

        self.assertEqual(1, result.total_matches)
        self.assertEqual("Monitor gamer", result.items[0]["title"])

    def test_execute_search_falls_back_to_html(self) -> None:
        with (
            patch.object(api, "fetch_api_offers", side_effect=OSError("offline")),
            patch.object(api, "fetch_html", return_value="<html></html>") as fetch_html,
        ):
            result = api.execute_search(api.SearchOptions())

        self.assertEqual([], result.items)
        fetch_html.assert_called_once_with(api.OFFERS_URL)


if __name__ == "__main__":
    unittest.main()
