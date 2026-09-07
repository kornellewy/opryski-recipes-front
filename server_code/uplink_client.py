"""Small, server-only HTTP client for the orchard-spraying MVP.

The Anvil app deliberately has no copy of the MVP's domain rules.  This module
keeps the base URL and JWT on the server and returns a small, explicit result
shape for expected HTTP failures so the client can render 401/403/404/409
without treating them as successful state changes.
"""

import time
import uuid
from urllib.parse import urlencode

import anvil.http
from anvil import secrets, server


class MvpClient:
    READ_METHODS = {"GET", "HEAD", "OPTIONS"}
    MAX_READ_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = (0.2, 0.4)

    def __init__(self):
        self.base_url = self._read_base_url()

    @staticmethod
    def _read_base_url():
        value = secrets.get_secret("MVP_BASE_URL")
        return (value or "").strip().rstrip("/")

    @staticmethod
    def _error_kind(status):
        return {
            401: "session_expired",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
        }.get(status, "upstream")

    def request(self, method, path, *, payload=None, query=None):
        if not self.base_url:
            return {
                "ok": False,
                "code": 503,
                "kind": "configuration",
                "message": "Brak sekretu MVP_BASE_URL w konfiguracji Anvil.",
            }

        query_string = urlencode(query or {})
        url = f"{self.base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        method = str(method).upper()
        headers = {"Accept": "application/json"}
        token = server.session.get("mvp_jwt")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Login is intentionally excluded: it must never be replayed with an
        # idempotency key. Every other mutation gets a fresh key per callable
        # request so a server-side replay can safely return the original write.
        if method not in self.READ_METHODS and path != "/auth/login":
            headers["Idempotency-Key"] = str(uuid.uuid4())

        attempts = self.MAX_READ_ATTEMPTS if method in self.READ_METHODS else 1
        for attempt in range(attempts):
            try:
                data = anvil.http.request(
                    url,
                    method=method,
                    data=payload,
                    json=True,
                    headers=headers,
                    timeout=25,
                )
                return {"ok": True, "data": data}
            except anvil.http.HttpError as error:
                status = error.status or 503
                transient = status == 0 or 500 <= status <= 599
                if transient and method in self.READ_METHODS and attempt + 1 < attempts:
                    time.sleep(self.RETRY_BACKOFF_SECONDS[attempt])
                    continue
                return {
                    "ok": False,
                    "code": status,
                    "kind": self._error_kind(status),
                    "message": self._message_for_http_error(status, error),
                }

        # The loop always returns, but keep a defensive result for future
        # changes to the retry policy.
        return {"ok": False, "code": 503, "kind": "upstream", "message": "MVP jest chwilowo niedostępne."}

    @staticmethod
    def _message_for_http_error(status, error):
        defaults = {
            401: "Sesja wygasła. Zaloguj się ponownie.",
            403: "Nie masz uprawnień do tego zasobu.",
            404: "Zasób nie istnieje albo nie jest widoczny.",
            409: "Stan zmienił się na serwerze. Odśwież dane i spróbuj ponownie.",
            503: "MVP jest chwilowo niedostępne.",
        }
        return defaults.get(status, f"MVP zwróciło błąd HTTP {status}.")
