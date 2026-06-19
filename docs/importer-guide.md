# Importer Guide

The default importers are local CSV, JSON, and HTML files. Crawling is optional
and only available through explicit user-controlled recipes.

## CSV

CSV imports use one row per item. Known columns are mapped to the generic item
model:

- `id`
- `source_name`
- `source_url`
- `title`
- `price`
- `currency`
- `location`
- `seller_type`
- `description`

Additional columns are stored as item attributes.

## JSON

JSON imports accept either a single object, a list of objects, or an object with
an `items` list. The optional `attributes` object is preserved and additional
top-level fields are merged into attributes.

## Local HTML

HTML imports are offline-only. The importer reads local files, strips scripts
and styles, extracts readable text, and stores the source as a normal item
snapshot. It does not fetch URLs or automate browsers.

```bash
opa import html examples/imports/car_listing.html examples/imports/another_listing.html \
  --profile examples/profiles/family_car.yml
```

Future importers may support user-defined feeds, saved local HTML files, browser
bookmarklets, or explicit recipes. They must remain optional and user-controlled.

## Scrapy Recipes

Scrapy support is installed through the `crawler` extra:

```bash
python -m pip install -e ".[crawler]"
opa import scrapy path/to/recipe.yml --profile examples/profiles/family_car.yml
```

Recipes define what to fetch and what to extract. They must include explicit
`start_urls`, `allowed_domains`, field selectors, and conservative crawl
settings:

```yaml
name: example_products
start_urls:
  - https://example.com/products
allowed_domains:
  - example.com
item_selector: ".product"
fields:
  title: ".title::text"
  price: ".price::text"
  source_url: "a.details::attr(href)"
  description: ".description::text"
attributes:
  mileage_km: ".mileage::text"
follow_links:
  - "a.next::attr(href)"
settings:
  obey_robots_txt: true
  download_delay: 5
  max_pages: 10
  concurrent_requests: 1
```

The importer does not include target-specific marketplace recipes, browser
automation, login handling, CAPTCHA handling, or proxy rotation.
