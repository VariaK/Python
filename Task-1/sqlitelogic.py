import sqlite3
import os

conn = sqlite3.connect("products.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT,
    name TEXT,
    price REAL,
    rating REAL,
    timestamp TEXT,
    UNIQUE(product_id, timestamp)
)
""")

conn.commit()


def insert_products(products):
    conn = sqlite3.connect("products.db")
    cursor = conn.cursor()

    for p in products:
        cursor.execute("""
            INSERT OR IGNORE INTO products (product_id, name, price, rating, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            p["product_id"],
            p["name"],
            p["price_inr"],
            p["rating"],
            p["timestamp"]
        ))

    conn.commit()
    conn.close()
