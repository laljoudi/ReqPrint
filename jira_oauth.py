"""Jira OAuth 2.0 (3LO) connection for ReqPrint - stage 1: connect only.

The only state is an encrypted cookie in the user's browser: no database, no
server-side session. Nothing here calls Jira's REST API yet - it completes the
Atlassian authorization flow and remembers which site was connected.

Tokens, the client secret, and cookie contents are never logged, never put in a
URL, and never sent to the browser in the clear.
"""
import json
import logging
import os
import secrets
from html import escape
from string import Template
from urllib.parse import quote, urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, Response

load_dotenv()

logger = logging.getLogger(__name__)


# ---------- Config (fails fast at import) ----------

_REQUIRED_ENV = (
    "JIRA_CLIENT_ID",
    "JIRA_CLIENT_SECRET",
    "JIRA_REDIRECT_URI",
    "FRONTEND_ORIGIN",
    "SESSION_SECRET",
    "APP_ENV",
)

_missing = [name for name in _REQUIRED_ENV if not (os.getenv(name) or "").strip()]
if _missing:
    raise RuntimeError(
        "Jira OAuth is not configured - missing environment variable(s): "
        + ", ".join(_missing)
        + ". Add them to your .env file (see .env.example)."
    )

JIRA_CLIENT_ID = os.environ["JIRA_CLIENT_ID"].strip()
JIRA_CLIENT_SECRET = os.environ["JIRA_CLIENT_SECRET"].strip()
JIRA_REDIRECT_URI = os.environ["JIRA_REDIRECT_URI"].strip()
FRONTEND_ORIGIN = os.environ["FRONTEND_ORIGIN"].strip().rstrip("/")
APP_ENV = os.environ["APP_ENV"].strip().lower()

if APP_ENV not in ("local", "prod"):
    raise RuntimeError('APP_ENV must be "local" or "prod".')

_origin = urlsplit(FRONTEND_ORIGIN)
if _origin.scheme not in ("http", "https") or not _origin.netloc or _origin.path or _origin.query or _origin.fragment:
    raise RuntimeError(
        "FRONTEND_ORIGIN must be an origin - scheme and host[:port], no path - "
        "e.g. http://localhost:8000."
    )

try:
    _fernet = Fernet(os.environ["SESSION_SECRET"].strip().encode())
except ValueError:
    raise RuntimeError(
        "SESSION_SECRET is not a valid Fernet key (32 url-safe base64-encoded bytes). "
        'Generate one with: python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"'
    ) from None

COOKIE_SECURE = APP_ENV == "prod"

AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
# Every scope the app asks for at consent - the one place to change the list.
# A scope only counts if it is also enabled under Permissions in the Atlassian
# developer console, and existing connections keep the scopes they were
# granted until the user reconnects.
JIRA_SCOPES = (
    "read:jira-work",
    "write:jira-work",
    "read:jira-user",
    "manage:jira-project",
    "manage:jira-configuration",
    "read:board-scope:jira-software",
    "read:sprint:jira-software",
    "write:sprint:jira-software",
    "read:project:jira",
    "read:issue-details:jira",
    "read:jql:jira",
    "write:board-scope:jira-software",
    "write:issue:jira-software",
    "offline_access",
)

CONNECTION_COOKIE = "jira_conn"
CONNECTION_MAX_AGE = 90 * 24 * 60 * 60  # 90 days
STATE_COOKIE = "jira_oauth_state"
STATE_MAX_AGE = 10 * 60  # 10 minutes
STATE_COOKIE_PATH = "/api/jira"  # only ever needed by the callback

_CONNECTION_FIELDS = ("refresh_token", "cloud_id", "site_url", "site_name")
_HTTP_TIMEOUT = httpx.Timeout(10.0)


# ---------- Encrypted cookie helpers ----------

def encrypt_payload(data: dict) -> str:
    return _fernet.encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()


def decrypt_payload(token: str | None) -> dict | None:
    """Inverse of encrypt_payload. Returns None - never raises - for a missing,
    tampered, expired (older than the cookie's 90 days), or malformed value."""
    if not token:
        return None
    try:
        data = json.loads(_fernet.decrypt(token.encode(), ttl=CONNECTION_MAX_AGE))
    except (InvalidToken, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def set_connection_cookie(response: Response, payload: dict) -> None:
    response.set_cookie(
        key=CONNECTION_COOKIE,
        value=encrypt_payload({k: payload[k] for k in _CONNECTION_FIELDS}),
        max_age=CONNECTION_MAX_AGE,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_connection_cookie(response: Response) -> None:
    response.delete_cookie(
        CONNECTION_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax"
    )


def load_connection(cookie_value: str | None) -> dict | None:
    """The decrypted connection ({refresh_token, cloud_id, site_url, site_name})
    or None if there's no valid one. Callers must never send it to the browser
    as-is - it contains the refresh token."""
    data = decrypt_payload(cookie_value)
    if not data:
        return None
    if not all(isinstance(data.get(k), str) and data[k] for k in _CONNECTION_FIELDS):
        return None
    return {k: data[k] for k in _CONNECTION_FIELDS}


# ---------- OAuth state (CSRF) ----------

def new_state() -> str:
    return secrets.token_urlsafe(32)


def set_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=STATE_MAX_AGE,
        path=STATE_COOKIE_PATH,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_state_cookie(response: Response) -> None:
    response.delete_cookie(
        STATE_COOKIE, path=STATE_COOKIE_PATH, secure=COOKIE_SECURE, httponly=True, samesite="lax"
    )


def states_match(returned: str | None, expected: str | None) -> bool:
    if not returned or not expected:
        return False
    # compare_digest on str raises for non-ASCII input, so compare bytes.
    return secrets.compare_digest(returned.encode(), expected.encode())


# ---------- Authorize URL + code exchange ----------

def build_authorize_url(state: str) -> str:
    params = {
        "audience": "api.atlassian.com",
        "client_id": JIRA_CLIENT_ID,
        "scope": " ".join(JIRA_SCOPES),
        "redirect_uri": JIRA_REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"


class JiraOAuthError(Exception):
    """Any failure completing the flow. `reason` is a short fixed code that is
    safe to show the user - never provider response text."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


async def exchange_code(code: str) -> dict:
    """Trade the authorization code for tokens, then look up which Jira site
    was granted. Returns {refresh_token, cloud_id, site_url, site_name} - the
    short-lived access token is used here and discarded."""
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            token_resp = await client.post(
                TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": JIRA_CLIENT_ID,
                    "client_secret": JIRA_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": JIRA_REDIRECT_URI,
                },
            )
            if token_resp.status_code != 200:
                logger.warning("Jira token exchange failed: HTTP %s", token_resp.status_code)
                raise JiraOAuthError("token_exchange_failed")
            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            if not access_token or not refresh_token:
                # No refresh token means offline_access wasn't granted.
                logger.warning("Jira token response was missing a required token")
                raise JiraOAuthError("token_exchange_failed")

            res_resp = await client.get(
                RESOURCES_URL,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            if res_resp.status_code != 200:
                logger.warning("Jira accessible-resources failed: HTTP %s", res_resp.status_code)
                raise JiraOAuthError("site_lookup_failed")
            resources = res_resp.json()
    except httpx.HTTPError as e:
        logger.warning("Jira OAuth request failed: %s", type(e).__name__)
        raise JiraOAuthError("network_error") from None
    except (ValueError, AttributeError):
        logger.warning("Jira OAuth response was not the expected JSON")
        raise JiraOAuthError("bad_response") from None

    if not isinstance(resources, list) or not resources:
        raise JiraOAuthError("no_jira_site")
    site = resources[0]
    cloud_id, site_url, site_name = site.get("id"), site.get("url"), site.get("name")
    if not (cloud_id and site_url and site_name):
        raise JiraOAuthError("bad_response")
    return {
        "refresh_token": refresh_token,
        "cloud_id": cloud_id,
        "site_url": site_url,
        "site_name": site_name,
    }


# ---------- Popup result page ----------

# `error` on the callback URL is attacker-controllable, so only these standard
# OAuth codes are ever passed through; everything else becomes "unknown_error".
_PROVIDER_ERRORS = {
    "access_denied",
    "invalid_request",
    "unauthorized_client",
    "unsupported_response_type",
    "invalid_scope",
    "server_error",
    "temporarily_unavailable",
}


def provider_error_reason(error: str) -> str:
    return error if error in _PROVIDER_ERRORS else "unknown_error"


_POPUP_PAGE = Template("""<!doctype html>
<meta charset="utf-8">
<title>ReqPrint - Jira</title>
<p>$text</p>
<script>
(function () {
  var message = $message;
  try {
    if (window.opener) { window.opener.postMessage(message, $origin); }
  } catch (e) {}
  window.close();
})();
</script>
""")


def _js_literal(value) -> str:
    """JSON for embedding in an inline <script>: json.dumps already escapes
    non-ASCII (incl. U+2028/9); < > & are escaped so nothing can close the tag."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def finish_popup(message: dict, *, status_code: int = 200, connection: dict | None = None) -> HTMLResponse:
    """The callback's response: a tiny page that posts `message` to the app
    window that opened this popup - always to FRONTEND_ORIGIN explicitly, never
    "*" - and closes itself. Also clears the one-time state cookie, and sets the
    connection cookie when `connection` is given."""
    if message.get("type") == "jira-connected":
        text = "Jira is connected. You can close this window and return to ReqPrint."
    else:
        text = f"Jira could not be connected ({escape(str(message.get('reason', 'unknown_error')))}). You can close this window and try again."
    response = HTMLResponse(
        _POPUP_PAGE.substitute(
            text=text, message=_js_literal(message), origin=_js_literal(FRONTEND_ORIGIN)
        ),
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )
    clear_state_cookie(response)
    if connection is not None:
        set_connection_cookie(response, connection)
    return response
