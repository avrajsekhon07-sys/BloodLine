"""Login rate limiting: counts FAILED attempts in a sliding window.

* per account+IP: LOGIN_MAX_ATTEMPTS (default 5) within LOGIN_WINDOW_SECONDS (default 900 = 15 min)
* per IP:         LOGIN_MAX_ATTEMPTS_PER_IP (default 20) within the same window
A successful login clears that account's counter. State is in memory: it resets when the server
restarts and is not shared between worker processes (use Redis or a gateway limit for multi-instance
deployments). Behind a reverse proxy every client shares the proxy's IP unless the proxy is trusted.
Set LOGIN_RATE_LIMIT=0 to turn it off."""
import os
import time
from collections import defaultdict, deque


class LoginLimiter:
    def __init__(self, max_per_account: int = 5, max_per_ip: int = 20, window_s: int = 900):
        self.max_account, self.max_ip, self.window = max_per_account, max_per_ip, window_s
        self.fails = defaultdict(deque)

    def _prune(self, q, now):
        while q and now - q[0] > self.window:
            q.popleft()

    def _keys(self, ip, email):
        return ((("a", ip, (email or "").lower()), self.max_account), (("i", ip), self.max_ip))

    def check(self, ip: str, email: str, now: float = None) -> int:
        """Seconds the caller must wait, or 0 if the attempt is allowed."""
        now = time.time() if now is None else now
        wait = 0
        for key, limit in self._keys(ip, email):
            q = self.fails.get(key)
            if not q:
                continue
            self._prune(q, now)
            if len(q) >= limit:
                wait = max(wait, int(q[0] + self.window - now) + 1)
        return wait

    def record_failure(self, ip: str, email: str, now: float = None):
        now = time.time() if now is None else now
        if len(self.fails) > 10000:  # drop empty/expired entries so random emails can't grow memory forever
            for k in [k for k, q in self.fails.items() if not q or now - q[-1] > self.window]:
                self.fails.pop(k, None)
        for key, _ in self._keys(ip, email):
            self.fails[key].append(now)

    def reset(self, ip: str, email: str):
        self.fails.pop(("a", ip, (email or "").lower()), None)

    def clear(self):
        self.fails.clear()


limiter = LoginLimiter(
    int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")),
    int(os.getenv("LOGIN_MAX_ATTEMPTS_PER_IP", "20")),
    int(os.getenv("LOGIN_WINDOW_SECONDS", "900")),
)


def enabled() -> bool:
    return os.getenv("LOGIN_RATE_LIMIT", "1") != "0"
