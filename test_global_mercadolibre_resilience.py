import os
import unittest
from unittest.mock import patch

import global_search
import mercadolibre


class GlobalMercadoLibreResilienceTests(unittest.TestCase):
    def test_retries_without_cookie_after_cookie_failure(self) -> None:
        cfg = global_search.build_config(
            {
                "query": "notebook",
                "sources": ["mercadolibre"],
                "scan_scope": "fast",
                "mercadolibre_condition": "new",
            }
        )
        item = {"title": "Notebook", "link": "https://example.test/item", "price": "$ 1"}
        with patch.dict(os.environ, {"ML_COOKIE": "ssid=expired"}, clear=False):
            with patch.object(mercadolibre, "collect_results", side_effect=[RuntimeError("403"), [item]]) as collect:
                result = global_search._run_mercadolibre(cfg)

        self.assertEqual(2, collect.call_count)
        self.assertEqual(1, result["count"])
        self.assertIn("sin cookie", result["warning"])
        self.assertFalse(mercadolibre.has_cookie_header())


if __name__ == "__main__":
    unittest.main()
