import time

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_failure_time = None

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            if self.state != "OPEN":
                self.state = "OPEN"
                self.last_failure_time = time.time()

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self):
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
                return True
            return False
            
        if self.state == "HALF-OPEN":
            # Allow exactly one request to pass through
            # Next request shouldn't pass until we record success/failure for this one
            # Actually for simple implementation, HALF-OPEN just allows requests but fails quickly if needed
            # For strict one-request:
            self.state = "OPEN"
            self.last_failure_time = time.time()
            return True
            
        return False
