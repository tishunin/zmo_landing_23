#!/usr/bin/env python3
"""Static site server with a validated registration proxy."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parent
CRM_ENDPOINT = "https://event.kpgreenwood.ru/assets/ajax/feedback.php"
EVENTS_ENDPOINT = "https://ingeni.app/6/sites/events/"
MAX_BODY_BYTES = 8 * 1024
RATE_WINDOW_SECONDS = 60 * 60
RATE_MAX_REQUESTS = 5
RATE_MIN_INTERVAL_SECONDS = 20

_requests_by_ip: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()


class ValidationError(ValueError):
    pass


def normalize_payload(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Некорректный формат данных.")

    allowed = {"name", "phone", "email", "consent", "lastname"}
    if set(payload) - allowed:
        raise ValidationError("Переданы неизвестные поля.")

    lastname = str(payload.get("lastname", "")).strip()
    if lastname:
        # Honeypot: callers receive a generic success without an upstream request.
        return {"honeypot": "1"}

    name = " ".join(str(payload.get("name", "")).split())
    phone = " ".join(str(payload.get("phone", "")).split())
    email = str(payload.get("email", "")).strip().lower()
    consent = payload.get("consent") is True

    if not 2 <= len(name) <= 80 or any(ord(char) < 32 for char in name):
        raise ValidationError("Укажите корректное имя.")

    digits = re.sub(r"\D", "", phone)
    if not 10 <= len(digits) <= 15 or len(phone) > 30:
        raise ValidationError("Укажите корректный телефон.")

    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValidationError("Укажите корректную электронную почту.")

    if not consent:
        raise ValidationError("Необходимо согласие на обработку данных.")

    return {
        "date": "19.09.2026 11:30",
        "event": "День рождения ЗЕМЛЯ МО 23 года вместе",
        "source": "Регистрация",
        "lastname": "",
        "name": name,
        "phone": phone,
        "email": email,
    }


def rate_limit_exceeded(client_ip: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _rate_lock:
        entries = _requests_by_ip[client_ip]
        while entries and now - entries[0] >= RATE_WINDOW_SECONDS:
            entries.popleft()
        if entries and now - entries[-1] < RATE_MIN_INTERVAL_SECONDS:
            return True
        if len(entries) >= RATE_MAX_REQUESTS:
            return True
        entries.append(now)
    return False


def post_registration(data: dict[str, str]) -> None:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        CRM_ENDPOINT,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "zmo-landing-23/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = response.read(32).decode("utf-8", errors="replace").strip().lower()
    if result != "true":
        raise RuntimeError("CRM handler rejected the request")

    # The original landing also reports the event. This is best-effort and does
    # not change the successful CRM result.
    event_request = urllib.request.Request(
        EVENTS_ENDPOINT,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "zmo-landing-23/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(event_request, timeout=5):
            pass
    except (OSError, urllib.error.URLError):
        pass


class LandingHandler(SimpleHTTPRequestHandler):
    server_version = "ZmoLanding/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'",
        )
        super().end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if urllib.parse.urlsplit(self.path).path != "/api/registration":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not self._is_same_origin_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "message": "Запрос отклонён."})
            return

        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"ok": False, "message": "Некорректный формат."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "message": "Некорректный размер запроса."})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            data = normalize_payload(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
            message = str(error) if isinstance(error, ValidationError) else "Некорректные данные."
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"ok": False, "message": message})
            return

        if data.get("honeypot"):
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        client_ip = self.client_address[0]
        if rate_limit_exceeded(client_ip):
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"ok": False, "message": "Слишком много запросов. Попробуйте позже."})
            return

        try:
            post_registration(data)
        except (OSError, RuntimeError, urllib.error.URLError):
            self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "message": "Не удалось отправить заявку. Попробуйте позже."})
            return

        self._send_json(HTTPStatus.OK, {"ok": True})

    def _is_same_origin_request(self) -> bool:
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            return False

        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if not origin or not host:
            return False
        parsed = urllib.parse.urlsplit(origin)
        return parsed.scheme in {"http", "https"} and parsed.netloc == host

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        # Do not log request bodies or other submitted personal information.
        super().log_message(format, *args)


def main() -> None:
    host = os.getenv("LANDING_HOST", "0.0.0.0")
    port = int(os.getenv("LANDING_PORT", "8433"))
    server = ThreadingHTTPServer((host, port), LandingHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
