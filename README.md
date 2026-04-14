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

**Output :**

<img width="1210" height="397" alt="Screenshot 2026-04-13 091915" src="https://github.com/user-attachments/assets/12832e69-8d54-467d-a9f6-6618ebb22a10" />
<img width="526" height="434" alt="Screenshot 2026-04-13 094035" src="https://github.com/user-attachments/assets/90d007b6-95a4-4612-afd7-f9f59b11918f" />
<img width="927" height="402" alt="Screenshot 2026-04-13 094210" src="https://github.com/user-attachments/assets/fae35e9f-4411-431c-aa89-5b77712645a8" />

## 2. Real-Time Chat Application with WebSockets

**Description:** Create a multi-room chat server using WebSockets. Support private messaging, typing indicators, user presence tracking, and message history persistence.

**Prerequisites:**

- TCP/IP and WebSocket protocol basics
- `asyncio` and `async/await` syntax
- `websockets` or `FastAPI WebSocket` library
- JSON serialization/deserialization
- SQLite or Redis for message persistence
- Basic HTML/JS for the client UI

**Use-Case:**

- Users connect via browser and join named chat rooms
- Support direct messages between two users
- Show real-time "typing..." indicators
- Display online/away/offline presence status
- Persist and search message history

**Expected Output:**

```
=== Server Log ===
[INFO] Chat server started on ws://0.0.0.0:8765
[INFO] User "alice" connected (session: a3f8c1)
[INFO] User "bob" connected (session: d92eb4)
[INFO] alice joined room #general
[INFO] bob joined room #general

=== Client View (Alice) ===
#general | 2 members online
──────────────────────────────
[14:32:01] bob: Hey team, anyone available for a code review?
[14:32:05] bob is typing...
[14:32:08] alice: Sure! Send me the PR link.
[14:32:15] bob: https://github.com/org/repo/pull/142
──────────────────────────────
Online: alice, bob | carol (away)

=== Private Message (Bob -> Alice) ===
[DM] bob -> alice: Thanks for the quick review!
[DM] alice -> bob: No problem!
```
