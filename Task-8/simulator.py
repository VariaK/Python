import asyncio
import random
import time

class SensorSimulator:
    def __init__(self, sensor_id):
        self.sensor_id = sensor_id
        self.base_temp = 72.0
        self.base_vib = 0.1

    async def generate_data(self):
        while True:
            # Randomly create anomalies
            if random.random() < 0.05:
                # Anomaly!
                temp = self.base_temp + random.uniform(15, 35)
                vib = self.base_vib + random.uniform(0.2, 0.6)
            else:
                temp = self.base_temp + random.uniform(-2, 2)
                vib = self.base_vib + random.uniform(-0.02, 0.02)
            
            yield {
                "sensor_id": self.sensor_id,
                "timestamp": time.time(),
                "temp": round(temp, 1),
                "vibration": round(vib, 2)
            }
            await asyncio.sleep(1)
