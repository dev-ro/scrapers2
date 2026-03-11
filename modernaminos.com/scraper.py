from curl_cffi import requests
from bs4 import BeautifulSoup
import time

def scrape_page(page_num, raw_cookie_string):
    url = f"https://modernaminos.com/shop/page/{page_num}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cookie": raw_cookie_string
    }

    try:
        response = requests.get(url, headers=headers, impersonate="chrome")

        if response.status_code != 200:
             print(f"Error {response.status_code} on page {page_num}")
             if response.status_code == 403:
                  print("Cloudflare blocked the request. The cookies in cookie.txt might be expired or invalid.")
             return [], False

        import re
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        urls = set()
        for a in soup.find_all('a'):
            href = a.get('href')
            if href and re.match(r'^https://modernaminos\.com/product/[^/]+/?$', href):
                urls.add(href)
                
        # Check if there is a next page
        next_page = soup.find('a', class_='next page-numbers')
        has_next = next_page is not None
        
        return list(urls), has_next

    except Exception as e:
        print(f"Request Error on page {page_num}: {e}")
        return [], False

def main():
    cookie_file = "cookie.txt"
    try:
        with open(cookie_file, 'r') as f:
            cookie_string = f.read().strip()
            if cookie_string.lower().startswith("cookie:"):
                cookie_string = cookie_string[7:].strip()
    except Exception as e:
        print(f"Error reading cookie file: {e}")
        return
    
    if not cookie_string:
        print("Empty cookie file. Exiting.")
        return

    all_product_urls = set()
    page_num = 1
    has_next_page = True

    while has_next_page:
        print(f"Scraping page {page_num}...")
        urls, has_next_page = scrape_page(page_num, cookie_string)
        
        if urls:
            all_product_urls.update(urls)
            print(f"  Found {len(urls)} products on this page.")
        else:
            print("  No products found on this page. Stopping.")
            break

        if has_next_page:
            page_num += 1
            time.sleep(2) # polite delay
        else:
            print("  No next page found. Finished scraping.")
            
    # Save results
    output_file = "product_urls.txt"
    try:
        with open(output_file, 'w') as f:
            for url in sorted(all_product_urls):
                f.write(f"{url}\n")
        print(f"\nSuccessfully saved {len(all_product_urls)} unique product URLs to {output_file}")
    except Exception as e:
        print(f"Error saving to file: {e}")

if __name__ == "__main__":
    main()
