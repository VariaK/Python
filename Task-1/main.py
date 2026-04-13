import json
import time
from pathlib import Path
from random import randint
from datetime import datetime
import requests
from sqlitelogic import insert_products
import csv


# from dotenv import load_dotenv

# load_dotenv()

# cookies = os.getenv("cookies")

# headers = os.getenv("headers")

base_url = "https://www.tirabeauty.com/ext/plpoffers/application/api/v1.0/collections/makeup-face/items"
params = {
    "page_id": "1",
    "page_size": "20",
}
output_file = Path(__file__).with_name("products_13-4-26.json")
csv_file = Path(__file__).with_name("products_13-4-26.csv")
products = []
manual_date = datetime(2026, 4, 11, 14, 30, 0)
manual_timestamp = manual_date.strftime("%Y-%m-%d %H:%M:%S")
current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"[ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ] Scraper started — target: www.tirabeauty.com/collection/makeup-face")

while True:
    print(f"Fetching page {params['page_id']}...")
    try:
        response = requests.get(
            base_url,
            params=params,
            # cookies=cookies,
            # headers=headers,
        )
        response.raise_for_status()  
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        break

    data = response.json()
    items = data.get("items", [])
    page_info = data.get("page", {})

    if not items:
        print("No items found on this page. Exiting.")
        break

    for item in items:
        name = item.get("name", "No name")
        price = item.get("price", {}).get("effective", {}).get("min", "N/A")
        custom_json = item.get("_custom_json", {})
        rating = custom_json.get("averageRating", "No rating")

        products.append(
            {
                "product_id": item.get("uid") or item.get("sku") or item.get("slug"),
                "name": name,
                "price_inr": float(price) if price != 'N/A' else None,
                "rating": float(rating) if rating != 'No rating' else None,
                "timestamp": current_timestamp,
            }
        )

    print(f"[ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ] Page{params['page_id']} -- {len(items)} products extracted.")


    if page_info.get("has_next"):
        next_page_id = page_info.get("next_id")
        if next_page_id:
            params["page_id"] = next_page_id
     
            time.sleep(randint(1, 5))
        else:
            print("`has_next` is true, but `next_id` is missing. Stopping.")
            break
    else:
        print("Reached the last page.")
        break

if output_file.exists():
    with output_file.open("r", encoding="utf-8") as file:
        try:
            existing_products = json.load(file)
        except json.JSONDecodeError:
            existing_products = []
else:
    existing_products = []

existing_products.extend(products)

with output_file.open("w", encoding="utf-8") as file:
    json.dump(existing_products, file, ensure_ascii=False, indent=2)

print(f"Stored {len(products)} products in {output_file.name}.")



with csv_file.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "product_id", "name", "price_inr", "rating", "timestamp"
    ])
    
    writer.writeheader()
    writer.writerows(products)

print(f"Stored {len(products)} products in {csv_file.name}")

insert_products(products)
print(f"{len(products)} Data inserted into SQLite DB.")