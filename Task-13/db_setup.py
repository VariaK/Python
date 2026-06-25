import sqlite3
import os
import random
from datetime import datetime, timedelta

def setup_db():
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    
    db_path = os.path.join(os.path.dirname(__file__), "sales.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            date TEXT,
            region TEXT,
            revenue REAL,
            units INTEGER
        )
    """)
    
    # Target numbers for Jan 2026:
    # Revenue: ~1,247,832
    # Units: 3,412
    # Breakdown: North (412k), East (338k), South (309k), West (189k)
    
    regions = [
        ("North", 412000),
        ("East", 338000),
        ("South", 309000),
        ("West", 188832) # to exactly match 1,247,832 total
    ]
    
    total_revenue_target = sum(r[1] for r in regions)
    total_units_target = 3412
    
    # We will generate 3412 records distributed among the regions.
    # To hit exact revenue targets, we can distribute the revenue proportionally to each region's records.
    
    region_records = {
        "North": int(3412 * (412/1248)),
        "East": int(3412 * (338/1248)),
        "South": int(3412 * (309/1248))
    }
    region_records["West"] = 3412 - sum(region_records.values())
    
    records = []
    
    start_date = datetime(2026, 1, 1)
    
    for r_name, r_revenue in regions:
        r_count = region_records[r_name]
        
        # Distribute revenue among r_count records
        base_rev = r_revenue / r_count
        
        for i in range(r_count):
            # add some variance to revenue
            rev = round(base_rev * random.uniform(0.5, 1.5), 2)
            # Units usually 1-5
            units = random.randint(1, 5)
            
            # Random date in Jan 2026
            day = random.randint(1, 31)
            date_str = f"2026-01-{day:02d}"
            
            records.append((date_str, r_name, rev, units))
            
    # Now fix the total revenue to be exactly 1247832
    current_total = sum(r[2] for r in records)
    diff = 1247832 - current_total
    
    # Add diff to first record's revenue (or distribute, but one is fine for a mock)
    # Actually let's distribute it evenly
    adj = diff / len(records)
    
    final_records = []
    for i, r in enumerate(records):
        new_rev = round(r[2] + adj, 2)
        final_records.append((r[0], r[1], new_rev, r[3]))
        
    # Ensure final sum is exact (fix rounding errors on the last record)
    final_sum = sum(r[2] for r in final_records)
    final_diff = round(1247832 - final_sum, 2)
    last = final_records[-1]
    final_records[-1] = (last[0], last[1], last[2] + final_diff, last[3])
    
    # Shuffle so it's not all one region then another
    random.shuffle(final_records)
    
    cursor.executemany("INSERT INTO sales (date, region, revenue, units) VALUES (?, ?, ?, ?)", final_records)
    
    # We also need to add a previous month (Dec 2025) to calculate MoM growth (+8.3% total, West declined 12%)
    # Total Jan: 1,247,832
    # Total Dec = Jan / 1.083 = 1,152,199.45
    # West Jan: 189,000 -> Dec = 189,000 / 0.88 = 214,772
    
    dec_records = []
    for _ in range(100):
        dec_records.append(("2025-12-15", "West", 214772 / 100, 1))
        dec_records.append(("2025-12-15", "North", 380000 / 100, 1))
        dec_records.append(("2025-12-15", "East", 300000 / 100, 1))
        dec_records.append(("2025-12-15", "South", 257427.45 / 100, 1))
        
    cursor.executemany("INSERT INTO sales (date, region, revenue, units) VALUES (?, ?, ?, ?)", dec_records)
    
    conn.commit()
    conn.close()
    print("Database sales.db created with mock data.")

if __name__ == "__main__":
    setup_db()
