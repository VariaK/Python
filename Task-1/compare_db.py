import sqlite3
import csv
from datetime import datetime

conn = sqlite3.connect("products.db")
cursor = conn.cursor()

today = "2026-04-13"
yesterday = "2026-04-12"
report_file = f"price_changes_{datetime.now().strftime('%Y-%m-%d')}.csv"


cursor.execute("""
SELECT product_id, name, price FROM products
WHERE DATE(timestamp) = ?
""", (yesterday,))
old_data = cursor.fetchall()

cursor.execute("""
SELECT product_id, name, price FROM products
WHERE DATE(timestamp) = ?
""", (today,))
new_data = cursor.fetchall()

conn.close()

# Convert to map
old_map = {row[0]: {"name": row[1], "price": row[2]} for row in old_data}

price_changes = []

for row in new_data:
    pid, name, new_price = row

    if pid in old_map:
        old_price = old_map[pid]["price"]

        if old_price is None or new_price is None:
            continue

        if old_price != new_price:
            change_percent = ((new_price - old_price) / old_price) * 100

            price_changes.append({
                "name": name,
                "old_price": old_price,
                "new_price": new_price,
                "change_percent": round(change_percent, 2)
            })

# Print report
print("\n=== Price Change Report ===")

for p in price_changes:
    print(f"{p['name']}")
    print(f"Old: ₹{p['old_price']} → New: ₹{p['new_price']} ({p['change_percent']}%)")
    print("-" * 40)

print(f"Total changes detected: {len(price_changes)}")

with open(report_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "name", "old_price", "new_price", "change_percent"
    ])
    
    writer.writeheader()
    writer.writerows(price_changes)

print(f"Report saved to {report_file}")