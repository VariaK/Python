## 1. Web Scraper with Anti-Bot Bypass

**Description:** Build a scraper that extracts structured data from dynamic, JavaScript-rendered websites. Handle pagination, rate limiting, retries, and rotating user-agents to avoid detection.

**Prerequisites:**

- HTTP methods, status codes, headers, and cookies
- HTML/CSS selectors (`BeautifulSoup`, `lxml`)
- `requests` or `httpx` library
- `Selenium` or `Playwright` for JS-rendered pages
- Basic `asyncio` for concurrent requests
- Regular expressions for pattern extraction

**Use-Case:**

- Scrape e-commerce product listings on a nightly schedule
- Store product data (name, price, SKU) in SQLite/PostgreSQL
- Compare against previous day's data and flag price changes
- Export a daily price-change report as CSV

**Expected Output:**

```
[2026-02-24 02:00:01] Scraper started — target: electronics.example.com
[2026-02-24 02:00:03] Page 1/47 — 24 products extracted
[2026-02-24 02:00:06] Page 2/47 — 24 products extracted
...
[2026-02-24 02:12:44] Page 47/47 — 11 products extracted
[2026-02-24 02:12:45] Total: 1,107 products saved to DB

=== Price Change Report ===
+-------------------------------+-----------+-----------+--------+
| Product                       | Old Price | New Price | Change |
+-------------------------------+-----------+-----------+--------+
| Sony WH-1000XM5 Headphones   | $348.00   | $279.99   | -19.5% |
| Samsung Galaxy S25 Ultra      | $1,299.99 | $1,199.99 |  -7.7% |
| Logitech MX Master 3S        | $99.99    | $109.99   | +10.0% |
+-------------------------------+-----------+-----------+--------+
3 price changes detected. Report saved to reports/2026-02-24.csv
```
** Output :**
<img width="1210" height="397" alt="Screenshot 2026-04-13 091915" src="https://github.com/user-attachments/assets/12832e69-8d54-467d-a9f6-6618ebb22a10" />
<img width="526" height="434" alt="Screenshot 2026-04-13 094035" src="https://github.com/user-attachments/assets/90d007b6-95a4-4612-afd7-f9f59b11918f" />
<img width="927" height="402" alt="Screenshot 2026-04-13 094210" src="https://github.com/user-attachments/assets/fae35e9f-4411-431c-aa89-5b77712645a8" />

