"""Authenticated HTTP client for the Online Picasso Project.

One sequential client with: login, polite rate limiting, exponential backoff on
429/5xx/connection errors, automatic re-login when the session expires, and a stop
condition if the site presents a CAPTCHA or a block page.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from . import config
from .transform import is_server_error_page

log = logging.getLogger(__name__)


class BlockedError(RuntimeError):
    """The site answered with a CAPTCHA, a block page or a hard 403. Stop and ask."""


class LoginError(RuntimeError):
    """Login did not succeed (bad credentials or changed form)."""


def _looks_like_login_form(html: str) -> bool:
    return 'name="frontusername"' in html


def _looks_blocked(status: int, html: str) -> bool:
    lowered = html.lower()
    return status == 403 or "captcha" in lowered or "access denied" in lowered


class OppClient:
    """Thin wrapper over `requests.Session` that knows how to talk to the OPP."""

    def __init__(self, rate_limit_seconds: float = config.RATE_LIMIT_SECONDS) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_at = 0.0
        self.request_count = 0
        self.logged_in = False
        self.cookie_path = config.DATA_DIR / ".cookies.json"

    # --- rate limiting / low level -------------------------------------------
    def _wait_for_slot(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Perform one request with rate limit and exponential backoff."""
        kwargs.setdefault("timeout", config.REQUEST_TIMEOUT_SECONDS)
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._wait_for_slot()
            self.request_count += 1
            try:
                response = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                log.warning("Error de red (%s), intento %d/%d", exc.__class__.__name__,
                            attempt, config.MAX_RETRIES)
                self._sleep_backoff(attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                log.warning("HTTP %d en %s, intento %d/%d", response.status_code,
                            url, attempt, config.MAX_RETRIES)
                self._sleep_backoff(attempt, response.headers.get("Retry-After"))
                continue
            return response
        raise RuntimeError(f"Agotados los reintentos para {url}")

    @staticmethod
    def _sleep_backoff(attempt: int, retry_after: str | None = None) -> None:
        delay = config.BACKOFF_BASE_SECONDS ** attempt
        if retry_after and retry_after.isdigit():
            delay = max(delay, float(retry_after))
        time.sleep(delay)

    # --- authentication -------------------------------------------------------
    def _save_cookies(self) -> None:
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_path.write_text(json.dumps(self.session.cookies.get_dict()))

    def _load_cookies(self) -> bool:
        if not self.cookie_path.exists():
            return False
        self.session.cookies.update(json.loads(self.cookie_path.read_text()))
        return True

    def _session_is_active(self) -> bool:
        """True when the home page no longer offers the login form."""
        probe = self._request("GET", config.INDEX_URL)
        return not _looks_like_login_form(probe.text)

    def login(self, attempts: int = 3) -> None:
        """POST the credentials to frontlogin.php; the site answers with a cookFRONTIT cookie.

        The site answers 302 -> http://... ; following it over plain HTTP would drop the
        Secure session cookie, so the redirect is deliberately not followed. Logins are
        occasionally rejected for no visible reason, hence the small retry loop.
        """
        user, password = config.get_credentials()
        for attempt in range(1, attempts + 1):
            self.session.cookies.clear()
            self._request("GET", config.BASE_URL + "/")  # obtain PHPSESSID cookie
            self._request(
                "POST",
                config.LOGIN_URL,
                data={"frontusername": user, "frontpassword": password, "submit": "Log In"},
                headers={"Referer": config.INDEX_URL},
                allow_redirects=False,
            )
            if "cookFRONTIT" in self.session.cookies and self._session_is_active():
                self.logged_in = True
                self._save_cookies()
                log.info("Sesión iniciada en el Online Picasso Project.")
                return
            log.warning("Login rechazado (intento %d/%d); esperando antes de reintentar.",
                        attempt, attempts)
            time.sleep(5 * attempt)
        raise LoginError("El login no fue aceptado por el sitio tras varios intentos.")

    def ensure_logged_in(self) -> None:
        """Reuse the cookies saved by a previous run when they are still valid."""
        if self._load_cookies() and self._session_is_active():
            self.logged_in = True
            log.info("Sesión reutilizada desde cookies guardadas.")
            return
        self.login()

    # --- public API -----------------------------------------------------------
    def get_view(self, view: str, **params) -> str:
        """Fetch `index.php?view=<view>&...` and return the HTML text.

        Re-logs in when the session expired and retries the occasional bare MySQL
        error page ("Commands out of sync") the server returns under load.
        """
        for attempt in range(1, 4):
            response = self._request("GET", config.INDEX_URL, params={"view": view, **params})
            html = response.text
            if _looks_blocked(response.status_code, html):
                raise BlockedError(f"El sitio bloqueó la petición a view={view} "
                                   f"(HTTP {response.status_code}). Detenido.")
            if self.logged_in and _looks_like_login_form(html) and view != "Copyright":
                log.info("La sesión expiró; reintentando login.")
                self.login()
                continue
            if is_server_error_page(html):
                log.warning("Página de error del servidor en view=%s; reintento %d/3", view, attempt)
                time.sleep(3 * attempt)
                continue
            return html
        raise RuntimeError(f"No se pudo obtener view={view} {params}")

    def get_view_cached(self, path: Path, view: str, **params) -> str:
        """Like `get_view`, but reuse `path` when it already exists and save it otherwise."""
        if path.exists():
            return path.read_text(encoding="utf-8")
        html = self.get_view(view, **params)
        save_raw(path, html)
        return html

    def get_bytes(self, url: str) -> bytes:
        """Download a binary resource (image) relative or absolute to the site."""
        if not url.startswith("http"):
            url = config.BASE_URL + "/" + url.lstrip("./")
        response = self._request("GET", url)
        if _looks_blocked(response.status_code, response.text[:500] if "text" in
                          response.headers.get("Content-Type", "") else ""):
            raise BlockedError(f"El sitio bloqueó la descarga de {url}.")
        response.raise_for_status()
        return response.content


def save_raw(path: Path, html: str) -> None:
    """Persist raw HTML so it can be re-parsed later without re-downloading."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
