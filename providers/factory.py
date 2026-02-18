import threading
import time
from abc import ABC
from collections import deque


class RateLimitExceededError(Exception):
    pass


class RateLimiter:
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.timestamps = deque()
        self.lock = threading.Lock()

    def check(self):
        with self.lock:
            now = time.time()
            while self.timestamps and (now - self.timestamps[0]) > self.time_window:
                self.timestamps.popleft()

            if len(self.timestamps) >= self.max_calls:
                raise RateLimitExceededError(
                    f"Rate limit exceeded: {self.max_calls} calls per {self.time_window} seconds"
                )

            self.timestamps.append(now)


_rate_limiter = RateLimiter(max_calls=2, time_window=60)


class AiFactory(ABC):
    def transcribe_audio(self, audio_file) -> str:
        pass

    def summarize(self, text) -> str:
        pass

    def chat(self, message) -> str:
        _rate_limiter.check()
        return self.chat(message)

    def vision(self, image) -> str:
        pass
