import unittest

import mercadolibre


class MercadoLibreDiagnosticsTests(unittest.TestCase):
    def test_classifies_common_failure_pages(self) -> None:
        self.assertEqual("anti_bot", mercadolibre.classify_html_failure("<div>suspicious-traffic-frontend</div>"))
        self.assertEqual("challenge", mercadolibre.classify_html_failure("<title>Captcha</title>"))
        self.assertEqual("cookie_consent", mercadolibre.classify_html_failure("<button>Aceptar cookies</button>"))
        self.assertEqual("site_error", mercadolibre.classify_html_failure("<h1>Algo salió mal</h1>"))

    def test_classifies_results_page_with_empty_parser_as_selector_failure(self) -> None:
        html = '<main class="ui-search-layout">new markup without the old title selector</main>'
        self.assertEqual("selector_or_parse_empty", mercadolibre.classify_html_failure(html))
        self.assertEqual([], mercadolibre.parse_results_from_html(html))


if __name__ == "__main__":
    unittest.main()
