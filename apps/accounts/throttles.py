"""Login brute-force protection: 5 failed attempts per 15 minutes per IP.

Only failures are counted, so a correct login is never slowed down until the
limit is reached. Counters live in the shared cache (database table by default).
"""

import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled

from common.throttling import client_ip


def _key(request):
    return f"login-failures:{client_ip(request)}"


def check_login_allowed(request):
    state = cache.get(_key(request))
    if state and state["count"] >= settings.LOGIN_FAILURE_LIMIT:
        wait = max(1, int(state["reset_at"] - time.time()))
        raise Throttled(wait=wait)


def record_login_failure(request):
    now = time.time()
    key = _key(request)
    state = cache.get(key)
    if not state or state["reset_at"] <= now:
        state = {"count": 0, "reset_at": now + settings.LOGIN_FAILURE_WINDOW_SECONDS}
    state["count"] += 1
    cache.set(key, state, timeout=max(1, int(state["reset_at"] - now)))
