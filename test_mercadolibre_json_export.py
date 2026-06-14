import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mercadolibre


class MercadoLibreJsonExportTests(unittest.TestCase):
    def test_json_is_printed_when_xlsx_is_exported(self) -> None:
        item = {
            "title": "Notebook",
            "price": "$ 500.000",
            "link": "https://example.com/notebook",
            "discount_percent": 10,
            "condition": "new",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "notebook.xlsx"
            stdout = io.StringIO()
            with (
                patch.object(mercadolibre, "collect_results", return_value=[item]),
                contextlib.redirect_stdout(stdout),
            ):
                result = mercadolibre.run(
                    query="notebook",
                    limit=50,
                    as_json=True,
                    country="cl",
                    condition_filter="any",
                    fetch_all=True,
                    max_pages=0,
                    include_condition=False,
                    exclude_international=False,
                    min_price=0,
                    max_price=0,
                    word_filter="",
                    include_words=[],
                    exclude_words=[],
                    min_discount=0,
                    sort_price=False,
                    export_xlsx_path=str(output),
                    condition_workers=1,
                    skip_condition_in_export=True,
                    search_url=None,
                )

            self.assertEqual(0, result)
            self.assertTrue(output.exists())
            self.assertEqual("Notebook", json.loads(stdout.getvalue())[0]["title"])


if __name__ == "__main__":
    unittest.main()
