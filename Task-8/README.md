# Real-Time Data Streaming Dashboard

A real-time analytics streaming application built using `FastAPI` (backend) and `Chart.js` (frontend).

## Architecture

* **`simulator.py`**: An asynchronous mock generator that simulates an IoT feed (temperature, vibration) with random jitter and injected anomalies.
* **`processor.py`**: Leverages `pandas` to maintain a sliding 5-minute window for incoming telemetry, processing the moving average and computing statistical z-scores (standard deviations) for anomaly detection.
* **`main.py`**: A `FastAPI` app that acts as an event-driven loop tying together the generator and the processor. It exposes an HTML dashboard, runs the `asyncio` loop, and pushes data down to all connected WebSockets.
* **`templates/` & `static/`**: Houses the raw frontend layout for rendering beautiful charts via Chart.js and appending alert history boxes.

## Usage

You can fire up the dashboard with `uvicorn`:

```bash
uvicorn main:app --port 5000 --reload
```

Once started:
- See the server console logs for stream telemetry data.
- Visit `http://localhost:5000/dashboard` in a modern browser to visualize the dashboard. Watch it dynamically populate every second!
