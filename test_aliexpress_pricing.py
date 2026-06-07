import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "aliexpress_scraper" / "aliexpress.py"
spec = importlib.util.spec_from_file_location("aliexpress_under_test", MODULE_PATH)
aliexpress = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(aliexpress)


def test_chile_cost_backs_out_choice_vat_over_500_usd():
    cost = aliexpress._calculate_chile_cost(
        display_total=595,
        currency="USD",
        usd_clp_rate=1000,
        price_includes_chile_vat=True,
        is_choice=True,
    )

    assert cost["over_usd_500"] is True
    assert cost["original_price_usd"] == 500
    assert cost["duty_applied_usd"] == 30
    assert cost["iva_applied_usd"] == 100.7
    assert cost["handling_fee_usd"] == 15
    assert cost["final_price_clp"] == 645700


def test_normalize_product_outputs_chile_fields_and_variant_range():
    item = aliexpress._normalize_product(
        {
            "productId": "100500",
            "title": "Modelo X Basic / Pro",
            "productDetailUrl": "//es.aliexpress.com/item/100500.html",
            "imageUrl": "//ae01.alicdn.com/kf/example.jpg",
            "prices": {
                "salePrice": {
                    "minPrice": "100",
                    "maxPrice": "160",
                    "currencyCode": "USD",
                    "discount": "20",
                }
            },
            "shipping": {"shippingFee": {"value": "10", "currency": "USD"}},
            "skuImages": [{"skuId": "basic"}, {"skuId": "pro"}],
            "sellingPoints": [{"source": "choice_atm"}],
        },
        position=1,
        usd_clp_rate=1000,
        price_includes_chile_vat=False,
    )

    assert item["id"] == "aliexpress#100500"
    assert item["price_original"] == 100
    assert item["shipping"] == 10
    assert item["price_final_clp"] == 110000
    assert item["price_clp_final"] == item["price_final_clp"]
    assert item["tax_estimated"] == 17560
    assert item["is_choice"] is True
    assert item["has_variants"] is True
    assert item["variant_count"] == 2
    assert item["variant_price_max"] == 160
    assert item["max_price_clp"] == 170000
    assert item["url_imagen"].startswith("https:")


def test_extract_variant_details_maps_color_skus_to_prices():
    variants = aliexpress._extract_variant_details_from_payloads(
        [
            {
                "skuModule": {
                    "skuPropertyList": [
                        {
                            "skuPropertyName": "Color",
                            "skuPropertyValues": [
                                {
                                    "propertyValueIdLong": "1",
                                    "skuPropertyValueName": "MARS68 Pro Black",
                                    "skuPropertyImagePath": "//ae01.alicdn.com/kf/black.jpg",
                                },
                                {
                                    "propertyValueIdLong": "2",
                                    "skuPropertyValueName": "Mercury68 Max",
                                    "skuPropertyImagePath": "//ae01.alicdn.com/kf/max.jpg",
                                },
                            ],
                        }
                    ],
                    "skuPriceList": [
                        {
                            "skuId": "sku-basic",
                            "skuPropIds": "14:1",
                            "skuVal": {"skuActivityAmount": {"value": "49600", "currency": "CLP"}},
                            "availQuantity": 3,
                        },
                        {
                            "skuId": "sku-max",
                            "skuPropIds": "14:2",
                            "skuVal": {"skuActivityAmount": {"value": "70870", "currency": "CLP"}},
                            "availQuantity": 5,
                        },
                    ],
                }
            }
        ],
        shipping=0,
        fallback_currency="CLP",
        usd_clp_rate=950,
        price_includes_chile_vat=True,
        is_choice=False,
    )

    assert len(variants) == 2
    assert variants[0]["sku_id"] == "sku-basic"
    assert variants[0]["name"] == "Color: MARS68 Pro Black"
    assert variants[0]["price_original"] == 49600
    assert variants[0]["price_final_clp"] == 49600
    assert variants[0]["image"].startswith("https:")
    assert variants[1]["sku_id"] == "sku-max"
    assert variants[1]["name"] == "Color: Mercury68 Max"
    assert variants[1]["price_original"] == 70870


def test_collect_results_enriches_variants_from_detail_payload():
    search_payload = {
        "productId": "1005009251912811",
        "title": "IROK Mercury68 Max mars68 pro",
        "productDetailUrl": "//es.aliexpress.com/item/1005009251912811.html",
        "imageUrl": "//ae01.alicdn.com/kf/main.jpg",
        "prices": {"salePrice": {"minPrice": "49600", "maxPrice": "70870", "currencyCode": "CLP"}},
        "skuImages": [{"skuId": "a"}, {"skuId": "b"}],
    }
    detail_payload = {
        "skuModule": {
            "skuPropertyList": [
                {
                    "skuPropertyName": "Color",
                    "skuPropertyValues": [
                        {"propertyValueIdLong": "1", "skuPropertyValueName": "MARS68 Pro Black"},
                        {"propertyValueIdLong": "2", "skuPropertyValueName": "Mercury68 Max"},
                    ],
                }
            ],
            "skuPriceList": [
                {
                    "skuId": "sku-basic",
                    "skuPropIds": "14:1",
                    "skuVal": {"skuActivityAmount": {"value": "49600", "currency": "CLP"}},
                },
                {
                    "skuId": "sku-max",
                    "skuPropIds": "14:2",
                    "skuVal": {"skuActivityAmount": {"value": "70870", "currency": "CLP"}},
                },
            ],
        }
    }

    old_fetch_search = aliexpress._fetch_search_html
    old_fetch_detail_payloads = aliexpress._fetch_detail_payloads
    old_extract = aliexpress._extract_json_objects
    try:
        aliexpress._fetch_search_html = lambda *args, **kwargs: "<search>"
        aliexpress._fetch_detail_payloads = lambda *args, **kwargs: [detail_payload]
        aliexpress._extract_json_objects = lambda html: [search_payload]
        items, meta = aliexpress.collect_results(
            "mercury68",
            limit=1,
            max_pages=1,
            enrich_variant_details=True,
            variant_detail_limit=1,
        )
    finally:
        aliexpress._fetch_search_html = old_fetch_search
        aliexpress._fetch_detail_payloads = old_fetch_detail_payloads
        aliexpress._extract_json_objects = old_extract

    assert len(items) == 1
    assert meta["variant_details_enriched"] == 1
    assert items[0]["variant_source"] == "detail"
    assert items[0]["variants"][0]["name"] == "Color: MARS68 Pro Black"
    assert items[0]["variants"][1]["price_original"] == 70870
