# Modern Aminos Scraper

This is a Python scraper built with `uv`, `curl_cffi`, and `BeautifulSoup` to bypass Cloudflare and extract all product URLs from `modernaminos.com`.

## Prerequisites

1. Install [uv](https://docs.astral.sh/uv/) for dependency management.
2. Obtain a valid set of cookies for `modernaminos.com` bypassing Cloudflare from your browser and save them in a file named `cookie.txt` in the same directory as the script. The file should contain the raw `cookie:` header string (e.g. `Cookie: key=value; key2=value2`).

## Installation

```bash
uv sync
```

## Usage

### Phase 1: URL Discovery
Extract all product links from the shop catalog:
```bash
uv run scraper.py
```
The script will iterate through all shop pages and save the extracted product URLs to `product_urls.txt`.

### Phase 2: Product Data Extraction
Scrape detailed metadata and save to SQLite:
```bash
uv run scrape_details.py
```
This stores structured data (title, price, description, images, categories) in `products.db`.
