import json
import os
import time

class WAL:
    def __init__(self, filename="graph.wal"):
        self.filename = filename
        self.file = None
        self.last_snapshot_time = time.time()
        
        if not os.path.exists(self.filename):
            open(self.filename, 'a').close()
            
    def open(self):
        if self.file is None:
            self.file = open(self.filename, 'a')
            
    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None
            
    def log(self, op: str, data: dict):
        self.open()
        entry = {"op": op, "data": data, "ts": time.time()}
        self.file.write(json.dumps(entry) + '\n')
        self.file.flush()
        
    def read_all(self):
        if not os.path.exists(self.filename):
            return []
        entries = []
        with open(self.filename, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
        
    def get_size_bytes(self):
        if os.path.exists(self.filename):
            return os.path.getsize(self.filename)
        return 0
        
    def get_entry_count(self):
        return len(self.read_all())
