from functools import wraps
from quart import request, jsonify
import time
from collections import defaultdict
from typing import Dict, List
import threading


class RateLimiter:
    def __init__(self, window_size: int = 60, max_requests: int = 10):
        self.window_size = window_size  # Window size in seconds
        self.max_requests = max_requests
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
        
    def _cleanup_old_requests(self, ip: str, now: float):
        """Remove requests older than the window size."""
        with self.lock:
            self.requests[ip] = [
                req_time for req_time in self.requests[ip]
                if now - req_time <= self.window_size
            ]
    
    def is_rate_limited(self, ip: str) -> bool:
        """Check if an IP has exceeded the rate limit."""
        now = time.time()
        
        # Clean up old requests first
        self._cleanup_old_requests(ip, now)
        
        with self.lock:
            # Add current request
            self.requests[ip].append(now)
            
            # Check if number of requests in window exceeds limit
            return len(self.requests[ip]) > self.max_requests

# Create a global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(func):
    @wraps(func)
    async def decorated_function(*args, **kwargs):
        # Get the IP address from the request
        ip = request.headers.get('CF-Connecting-IP', request.remote_addr)
        
        # Check rate limit
        if rate_limiter.is_rate_limited(ip):
            return jsonify({
                "error": "Rate limit exceeded. Please try again later.",
                "limit": rate_limiter.max_requests,
                "window_size": f"{rate_limiter.window_size} seconds"
            }), 429
        
        # Call the original function
        return await func(*args, **kwargs)
    
    return decorated_function