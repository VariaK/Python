import json

# Load data
with open("products.json", "r", encoding="utf-8") as f:
    old_data = json.load(f)

with open("products2.json", "r", encoding="utf-8") as f:
    new_data = json.load(f)

# Convert old data into lookup dictionary
old_map = {
    item["product_id"]: item
    for item in old_data
    if item.get("product_id") is not None
}

price_changes = []

# Compare
for item in new_data:
    pid = item.get("product_id")
    new_price = item.get("price_inr")

    if pid in old_map:
        old_price = old_map[pid].get("price_inr")

        # Skip invalid data
        if old_price is None or new_price is None:
            continue

        if old_price != new_price:
            change_percent = ((new_price - old_price) / old_price) * 100

            price_changes.append({
                "name": item.get("name"),
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