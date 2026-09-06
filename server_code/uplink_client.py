"""Small, server-only HTTP client for the orchard-spraying MVP.

The Anvil app deliberately has no copy of the MVP's domain rules.  This module
keeps the base URL and JWT on the server and returns a small, explicit result
shape for expected HTTP failures so the client can render 401/403/404/409
without treating them as successful state changes.
"""

from urllib.parse import urlencode

import anvil.http
from anvil import secrets, server


class MvpClient:
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

        headers = {"Accept": "application/json"}
        token = server.session.get("mvp_jwt")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            data = anvil.http.request(
                url,
                method=method,
                data=payload,
                json=True,
                headers=headers,
                timeout=25,
            )
        except anvil.http.HttpError as error:
            status = error.status or 503
            return {
                "ok": False,
                "code": status,
                "kind": self._error_kind(status),
                "message": self._message_for_http_error(status, error),
            }

        return {"ok": True, "data": data}

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
