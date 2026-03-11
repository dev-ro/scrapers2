import sqlite3
import time
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
import sys

def init_db():
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            price TEXT,
            categories TEXT,
            description TEXT,
            image_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def get_cookie_string():
    try:
        with open("cookie.txt", "r") as f:
            cookie_string = f.read().strip()
            if cookie_string.lower().startswith("cookie:"):
                return cookie_string[7:].strip()
            return cookie_string
    except FileNotFoundError:
        print("Error: cookie.txt not found. Cannot bypass Cloudflare without cookies.")
        sys.exit(1)

def scrape_product_details(url, headers):
    try:
        response = cffi_requests.get(url, headers=headers, impersonate="chrome")
        if response.status_code != 200:
            print(f"Error {response.status_code} fetching {url}")
            return None
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        product = {"url": url}
        
        # Title
        title_elem = soup.find("h1", class_="product_title")
        product["title"] = title_elem.get_text(strip=True) if title_elem else ""
            
        # Price
        price_elem = soup.find("p", class_="price")
        product["price"] = price_elem.get_text(strip=True) if price_elem else ""
            
        # Categories
        meta_span = soup.find("span", class_="posted_in")
        if meta_span:
            categories = [a.get_text(strip=True) for a in meta_span.find_all("a")]
            product["categories"] = ", ".join(categories)
        else:
            product["categories"] = ""
            
        # Description
        desc_div = soup.find("div", class_="woocommerce-product-details__short-description")
        if not desc_div:
            desc_div = soup.find("div", id="tab-description")
        product["description"] = desc_div.get_text(strip=True) if desc_div else ""
            
        # Image URL
        img_div = soup.find("div", class_="woocommerce-product-gallery__image")
        if img_div and img_div.find("img"):
            product["image_url"] = img_div.find("img").get("src")
        else:
            product["image_url"] = ""
            
        return product
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None

def main():
    conn = init_db()
    c = conn.cursor()
    
    try:
        with open("product_urls.txt", "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: product_urls.txt not found. Please run the original scraper first.")
        sys.exit(1)
        
    print(f"Found {len(urls)} URLs to scrape")
    
    cookie_string = get_cookie_string()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cookie": cookie_string
    }
    
    success_count = 0
    for i, url in enumerate(urls, 1):
        # Check if already scraped
        c.execute("SELECT id FROM products WHERE url=?", (url,))
        if c.fetchone():
            print(f"[{i}/{len(urls)}] Skipping already scraped: {url}")
            continue
            
        print(f"[{i}/{len(urls)}] Scraping: {url}")
        
        product = scrape_product_details(url, headers)
        if product:
            try:
                c.execute('''
                    INSERT INTO products (url, title, price, categories, description, image_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    product["url"],
                    product["title"],
                    product["price"],
                    product["categories"],
                    product["description"],
                    product["image_url"]
                ))
                conn.commit()
                success_count += 1
            except sqlite3.Error as e:
                print(f"Database error saving {url}: {e}")
        
        # Rate limit
        time.sleep(2)
        
    print(f"\nFinished scraping details! Successfully added {success_count} new products to database.")
    conn.close()

if __name__ == "__main__":
    main()
