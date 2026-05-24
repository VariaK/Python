import pandas as pd

class DataProcessor:
    def __init__(self, window_size=300):
        self.window_size = window_size
        self.history = []

    def process(self, data_point):
        self.history.append(data_point)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        df = pd.DataFrame(self.history)
        
        # Calculate moving average and std dev
        mean_temp = df['temp'].mean()
        std_temp = df['temp'].std() if len(df) > 1 else 0
        
        mean_vib = df['vibration'].mean()
        std_vib = df['vibration'].std() if len(df) > 1 else 0
        
        temp = data_point['temp']
        vib = data_point['vibration']
        
        # Calculate z-scores
        z_temp = (temp - mean_temp) / std_temp if std_temp > 0 else 0
        z_vib = (vib - mean_vib) / std_vib if std_vib > 0 else 0

        status = "NORMAL"
        alert = None
        
        if temp > 100 or z_temp > 2.5:
            status = "CRITICAL" if temp > 100 else "WARNING"
            if temp > 100:
                alert = {
                    "type": "Temperature",
                    "message": f"Temperature exceeded threshold (>100F)",
                    "current": temp,
                    "avg": round(mean_temp, 1),
                    "sigma": round(z_temp, 1),
                    "sensor": data_point['sensor_id']
                }

        processed_data = {
            "sensor_id": data_point["sensor_id"],
            "timestamp": data_point["timestamp"],
            "temp": temp,
            "vibration": vib,
            "mean_temp": round(mean_temp, 1),
            "z_temp": round(z_temp, 1),
            "status": status,
            "alert": alert
        }
        return processed_data
