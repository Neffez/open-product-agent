# Importer Guide

The MVP importers are limited to local CSV and JSON files. This keeps the first
version focused on product understanding, scoring, and reporting rather than web
automation.

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
