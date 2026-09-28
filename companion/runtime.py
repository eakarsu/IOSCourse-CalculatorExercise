from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

CANONICAL_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BEARER_PATTERN = re.compile(r"^Bearer\s+(isc_[A-Za-z0-9_-]{40,160})$", re.IGNORECASE)
MAX_BODY_BYTES = 64 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Config:
    api_port: int
    ui_port: int
    database_path: Path
    admin_email: str
    admin_password: str
    session_ttl_hours: int
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str

    @property
    def ui_origin(self) -> str:
        return f"http://127.0.0.1:{self.ui_port}"

    @classmethod
    def from_env(cls, environment: dict[str, str] | os._Environ[str] = os.environ) -> Config:
        def integer(name: str, minimum: int, maximum: int) -> int:
            raw = str(environment.get(name, ""))
            if not raw.isdigit():
                raise ValueError(f"{name} must be an integer")
            value = int(raw)
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")
            return value

        api_port = integer("API_PORT", 1024, 65535)
        ui_port = integer("UI_PORT", 1024, 65535)
        if api_port == ui_port:
            raise ValueError("API_PORT and UI_PORT must be distinct")
        database_path = Path(str(environment.get("DATABASE_PATH", "")))
        if not database_path.is_absolute():
            raise ValueError("DATABASE_PATH must be absolute")
        email = str(environment.get("ADMIN_EMAIL", "")).strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise ValueError("ADMIN_EMAIL must be valid")
        password = str(environment.get("ADMIN_PASSWORD", ""))
        if len(password) < 12 or re.search(r"replace|placeholder|change-me", password, re.IGNORECASE):
            raise ValueError("ADMIN_PASSWORD must contain at least 12 non-placeholder characters")
        api_key = str(environment.get("OPENROUTER_API_KEY", "")).strip()
        model = str(environment.get("OPENROUTER_MODEL", "")).strip()
        base_url = str(environment.get("OPENROUTER_BASE_URL", "")).rstrip("/")
        if not api_key or not model or api_key.startswith("load-from-") or model.startswith("load-from-"):
            raise ValueError("OPENROUTER_API_KEY and OPENROUTER_MODEL are required")
        if base_url != CANONICAL_OPENROUTER_BASE:
            raise ValueError(f"OPENROUTER_BASE_URL must equal {CANONICAL_OPENROUTER_BASE}")
        return cls(
            api_port=api_port,
            ui_port=ui_port,
            database_path=database_path,
            admin_email=email,
            admin_password=password,
            session_ttl_hours=integer("SESSION_TTL_HOURS", 1, 168),
            openrouter_api_key=api_key,
            openrouter_model=model,
            openrouter_base_url=base_url,
        )


def password_record(password: str, salt: bytes | None = None) -> tuple[str, str]:
    resolved_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=resolved_salt, n=16_384, r=8, p=1, dklen=64)
    return resolved_salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hex: str) -> bool:
    try:
        _, actual = password_record(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(actual, expected_hex)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, config: Config):
        self.config = config
        config.database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._migrate()
        self._bootstrap_admin()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _migrate(self) -> None:
        with closing(self.connect()) as db, db:
            db.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                ) STRICT;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('ADMIN')),
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                ) STRICT;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                    token_digest TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT
                ) STRICT;
                CREATE INDEX IF NOT EXISTS sessions_active_idx
                    ON sessions(token_digest, expires_at) WHERE revoked_at IS NULL;
                CREATE TABLE IF NOT EXISTS ai_interactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
                    prompt TEXT NOT NULL,
                    requested_model TEXT NOT NULL,
                    provider_model TEXT,
                    provider_receipt TEXT UNIQUE,
                    output_text TEXT,
                    status TEXT NOT NULL CHECK (status IN ('PENDING', 'SUCCEEDED', 'FAILED')),
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    latency_ms INTEGER
                ) STRICT;
                CREATE INDEX IF NOT EXISTS ai_interactions_owner_idx
                    ON ai_interactions(user_id, created_at DESC);
                INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, CURRENT_TIMESTAMP);
                """
            )
        os.chmod(self.config.database_path, 0o600)

    def _bootstrap_admin(self) -> None:
        now = iso()
        with closing(self.connect()) as db, db:
            existing = db.execute("SELECT * FROM users WHERE email = ?", (self.config.admin_email,)).fetchone()
            if existing is None:
                salt, digest = password_record(self.config.admin_password)
                db.execute(
                    "INSERT INTO users(id,email,password_salt,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), self.config.admin_email, salt, digest, "ADMIN", now, now),
                )
            elif not verify_password(self.config.admin_password, existing["password_salt"], existing["password_hash"]):
                salt, digest = password_record(self.config.admin_password)
                db.execute(
                    "UPDATE users SET password_salt=?, password_hash=?, updated_at=? WHERE id=?",
                    (salt, digest, now, existing["id"]),
                )
                db.execute("UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, existing["id"]))

    def readiness(self) -> dict[str, object]:
        with closing(self.connect()) as db, db:
            migrations = db.execute("SELECT count(*) AS count FROM schema_migrations").fetchone()["count"]
            users = db.execute("SELECT count(*) AS count FROM users WHERE active=1").fetchone()["count"]
        return {"ready": migrations == 1 and users >= 1, "migrations": migrations, "activeUsers": users}

    def login(self, email: str, password: str) -> tuple[str, dict[str, object]] | None:
        normalized = email.strip().lower()
        with closing(self.connect()) as db, db:
            user = db.execute("SELECT * FROM users WHERE email=? AND active=1", (normalized,)).fetchone()
            if user is None or not verify_password(password, user["password_salt"], user["password_hash"]):
                return None
            now = utc_now()
            token = f"isc_{secrets.token_urlsafe(48)}"
            session_id = str(uuid.uuid4())
            expires = now + timedelta(hours=self.config.session_ttl_hours)
            db.execute("UPDATE users SET last_login_at=?, updated_at=? WHERE id=?", (iso(now), iso(now), user["id"]))
            db.execute(
                "INSERT INTO sessions(id,user_id,token_digest,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                (session_id, user["id"], token_digest(token), iso(now), iso(expires), iso(now)),
            )
            return token, {
                "id": user["id"], "email": user["email"], "role": user["role"],
                "sessionId": session_id, "expiresAt": iso(expires),
            }

    def identity(self, token: str) -> dict[str, object] | None:
        now = iso()
        with closing(self.connect()) as db, db:
            row = db.execute(
                """SELECT s.id AS session_id,s.expires_at,u.id AS user_id,u.email,u.role
                   FROM sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.token_digest=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.active=1""",
                (token_digest(token), now),
            ).fetchone()
            if row is None:
                return None
            db.execute("UPDATE sessions SET last_seen_at=? WHERE id=?", (now, row["session_id"]))
            return {
                "id": row["user_id"], "email": row["email"], "role": row["role"],
                "sessionId": row["session_id"], "authType": "SESSION",
            }

    def revoke(self, token: str) -> bool:
        with closing(self.connect()) as db, db:
            result = db.execute(
                "UPDATE sessions SET revoked_at=? WHERE token_digest=? AND revoked_at IS NULL",
                (iso(), token_digest(token)),
            )
            return result.rowcount == 1

    def begin_ai(self, identity: dict[str, object], prompt: str) -> str:
        interaction_id = str(uuid.uuid4())
        with closing(self.connect()) as db, db:
            db.execute(
                """INSERT INTO ai_interactions
                   (id,user_id,session_id,prompt,requested_model,status,created_at)
                   VALUES(?,?,?,?,?,'PENDING',?)""",
                (interaction_id, identity["id"], identity["sessionId"], prompt, self.config.openrouter_model, iso()),
            )
        return interaction_id

    def complete_ai(self, interaction_id: str, result: dict[str, object], latency_ms: int) -> None:
        with closing(self.connect()) as db, db:
            db.execute(
                """UPDATE ai_interactions SET provider_model=?,provider_receipt=?,output_text=?,status='SUCCEEDED',
                   completed_at=?,latency_ms=? WHERE id=? AND status='PENDING'""",
                (result["model"], result["receipt"], result["content"], iso(), latency_ms, interaction_id),
            )

    def fail_ai(self, interaction_id: str, code: str, latency_ms: int) -> None:
        with closing(self.connect()) as db, db:
            db.execute(
                """UPDATE ai_interactions SET status='FAILED',error_code=?,completed_at=?,latency_ms=?
                   WHERE id=? AND status='PENDING'""",
                (code, iso(), latency_ms, interaction_id),
            )

    def interaction(self, interaction_id: str, user_id: str) -> dict[str, object] | None:
        with closing(self.connect()) as db, db:
            row = db.execute(
                """SELECT id,requested_model,provider_model,provider_receipt,output_text,status,error_code,
                          created_at,completed_at,latency_ms
                   FROM ai_interactions WHERE id=? AND user_id=?""",
                (interaction_id, user_id),
            ).fetchone()
        return dict(row) if row else None


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def invoke_openrouter(config: Config, prompt: str) -> dict[str, object]:
    payload = json.dumps({
        "model": config.openrouter_model,
        "messages": [
            {"role": "system", "content": "Review calculator-adjacent AI features for arithmetic integrity, privacy, accessibility, evidence, rollback, and accountable human approval."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 650,
    }).encode()
    request = urllib.request.Request(
        f"{config.openrouter_base_url}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": "iOS Calculator Runtime Verification Companion",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=110, context=ssl.create_default_context()) as response:
            encoded_body = response.read()
    except urllib.error.HTTPError as error:
        raise ProviderError("OPENROUTER_HTTP_ERROR", f"OpenRouter returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ProviderError("OPENROUTER_REQUEST_FAILED", "OpenRouter request failed") from error
    try:
        body = json.loads(encoded_body.decode())
        if not isinstance(body, dict):
            raise TypeError("provider body must be an object")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise TypeError("provider choices must be a non-empty object array")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise TypeError("provider message must be an object")
        content_value = message.get("content", "")
    except (AttributeError, IndexError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderError("OPENROUTER_RESPONSE_INVALID", "OpenRouter response shape was invalid") from error
    receipt = str(body.get("id") or "").strip()
    model = str(body.get("model") or config.openrouter_model).strip()
    if isinstance(content_value, list):
        content = "\n".join(str(item.get("text", "")) for item in content_value if isinstance(item, dict)).strip()
    else:
        content = str(content_value).strip()
    if not receipt or not content:
        raise ProviderError("OPENROUTER_RESPONSE_INVALID", "OpenRouter response lacked a receipt or content")
    return {"receipt": receipt, "model": model, "content": content}


class RuntimeService:
    def __init__(self, config: Config, provider: Callable[[Config, str], dict[str, object]] = invoke_openrouter):
        self.config = config
        self.store = Store(config)
        self.provider = provider

    def bearer_identity(self, authorization: str | None) -> tuple[str, dict[str, object]] | None:
        match = BEARER_PATTERN.fullmatch(authorization or "")
        if not match:
            return None
        token = match.group(1)
        identity = self.store.identity(token)
        return (token, identity) if identity else None

    def ask(self, identity: dict[str, object], prompt: str) -> dict[str, object]:
        interaction_id = self.store.begin_ai(identity, prompt)
        started = time.monotonic()
        try:
            provider_result = self.provider(self.config, prompt)
            latency_ms = int((time.monotonic() - started) * 1000)
            self.store.complete_ai(interaction_id, provider_result, latency_ms)
            return {
                "interactionId": interaction_id,
                "content": provider_result["content"],
                "providerReceipt": {
                    "requestId": provider_result["receipt"], "provider": "openrouter",
                    "upstreamModel": provider_result["model"],
                },
                "model": self.config.openrouter_model,
            }
        except ProviderError as error:
            self.store.fail_ai(interaction_id, error.code, int((time.monotonic() - started) * 1000))
            raise
        # This is the outer provider/persistence boundary: unexpected failures must
        # become durable terminal evidence rather than escaping the request thread.
        except Exception as error:
            self.store.fail_ai(interaction_id, "AI_INTERNAL_ERROR", int((time.monotonic() - started) * 1000))
            raise ProviderError("AI_INTERNAL_ERROR", "AI processing failed safely") from error


def api_handler(service: RuntimeService) -> type[BaseHTTPRequestHandler]:
    class ApiHandler(BaseHTTPRequestHandler):
        server_version = "IOSCalculatorVerification/1"
        sys_version = ""

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def request_log(self, status: int, started: float) -> None:
            print(json.dumps({
                "event": "http_request", "method": self.command, "path": urlsplit(self.path).path,
                "status": status, "durationMs": int((time.monotonic() - started) * 1000),
            }), flush=True)

        def send_json(self, status: int, body: dict[str, object], started: float) -> None:
            encoded = json.dumps(body, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if self.headers.get("Origin") == service.config.ui_origin:
                self.send_header("Access-Control-Allow-Origin", service.config.ui_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(encoded)
            self.request_log(status, started)

        def read_json(self) -> dict[str, object]:
            raw_length = self.headers.get("Content-Length", "")
            if not raw_length.isdigit() or int(raw_length) > MAX_BODY_BYTES:
                raise ValueError("invalid request body length")
            body = json.loads(self.rfile.read(int(raw_length)))
            if not isinstance(body, dict):
                raise TypeError("request body must be an object")
            return body

        def require_identity(self, started: float) -> tuple[str, dict[str, object]] | None:
            authenticated = service.bearer_identity(self.headers.get("Authorization"))
            if authenticated is None:
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "AUTHENTICATION_REQUIRED"}, started)
            return authenticated

        def do_OPTIONS(self) -> None:
            started = time.monotonic()
            if self.headers.get("Origin") != service.config.ui_origin:
                self.send_json(HTTPStatus.FORBIDDEN, {"error": "ORIGIN_REJECTED"}, started)
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", service.config.ui_origin)
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.request_log(HTTPStatus.NO_CONTENT, started)

        def do_GET(self) -> None:
            started = time.monotonic()
            path = urlsplit(self.path).path
            if path == "/health/live":
                self.send_json(HTTPStatus.OK, {"status": "live"}, started)
                return
            if path == "/health/ready":
                readiness = service.store.readiness()
                self.send_json(HTTPStatus.OK if readiness["ready"] else HTTPStatus.SERVICE_UNAVAILABLE, readiness, started)
                return
            if path == "/api/auth/demo-credentials":
                if os.environ.get("NODE_ENV") == "production":
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"}, started)
                else:
                    self.send_json(HTTPStatus.OK, {"email": service.config.admin_email, "password": service.config.admin_password}, started)
                return
            if path == "/api/auth/me":
                authenticated = self.require_identity(started)
                if authenticated:
                    self.send_json(HTTPStatus.OK, {"user": authenticated[1]}, started)
                return
            prefix = "/api/ai/interactions/"
            if path.startswith(prefix):
                authenticated = self.require_identity(started)
                if not authenticated:
                    return
                interaction_id = path.removeprefix(prefix)
                if not re.fullmatch(r"[a-f0-9-]{36}", interaction_id):
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"}, started)
                    return
                row = service.store.interaction(interaction_id, str(authenticated[1]["id"]))
                if row is None:
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"}, started)
                    return
                self.send_json(HTTPStatus.OK, {"interaction": row}, started)
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"}, started)

        def do_POST(self) -> None:
            started = time.monotonic()
            path = urlsplit(self.path).path
            try:
                body = self.read_json()
            except (TypeError, ValueError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_JSON"}, started)
                return
            if path == "/api/auth/login":
                email, password = body.get("email"), body.get("password")
                result = service.store.login(str(email or ""), str(password or ""))
                if result is None:
                    self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "INVALID_CREDENTIALS"}, started)
                    return
                token, identity = result
                self.send_json(HTTPStatus.OK, {"accessToken": token, "tokenType": "Bearer", "user": identity}, started)
                return
            if path == "/api/auth/logout":
                authenticated = self.require_identity(started)
                if not authenticated:
                    return
                service.store.revoke(authenticated[0])
                self.send_json(HTTPStatus.OK, {"revoked": True}, started)
                return
            if path == "/api/ai/calculator-safety-review":
                authenticated = self.require_identity(started)
                if not authenticated:
                    return
                prompt = str(body.get("prompt") or "").strip()
                if not 10 <= len(prompt) <= 12_000:
                    self.send_json(HTTPStatus.BAD_REQUEST, {"error": "PROMPT_INVALID"}, started)
                    return
                try:
                    result = service.ask(authenticated[1], prompt)
                    self.send_json(HTTPStatus.OK, result, started)
                except ProviderError as error:
                    self.send_json(HTTPStatus.BAD_GATEWAY, {"error": error.code}, started)
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"}, started)

    return ApiHandler


UI_DOCUMENT = b"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>iOS Calculator Verification Companion</title><link rel="stylesheet" href="/style.css"></head>
<body><main><h1>Runtime-verification companion</h1><p>This local page verifies authentication, persistence, and governed AI integration for the repository. It does not replace or emulate the native UIKit calculator.</p>
<section><h2>Credential login</h2><button id="fill-demo" type="button">Auto Fill Demo Credentials</button><form id="login-form"><label>Email <input id="email" name="email" type="email" autocomplete="username" required></label><label>Password <input id="password" name="password" type="password" autocomplete="current-password" required minlength="12"></label><button type="submit">Sign In</button></form><p id="identity" role="status">Not signed in.</p></section>
<section id="dashboard" hidden><h2>Authenticated dashboard</h2><button id="logout" type="button">Log out</button><h3>Governed AI safety review</h3><form id="ai-form"><label>Review prompt <textarea id="prompt" name="prompt" required minlength="10">Review arithmetic correctness, privacy, accessibility, evidence, rollback, and human approval controls.</textarea></label><button id="review" type="submit">Request review</button></form><pre id="result" aria-live="polite">Signed in. Request a review when ready.</pre></section></main><script src="/app.js" defer></script></body></html>"""

UI_STYLE = b"""body{font:16px system-ui;max-width:780px;margin:3rem auto;padding:0 1rem;color:#152238;background:#eef3f8}main{border:1px solid #ccd5e0;border-radius:16px;padding:2rem;background:#fff}section{border-top:1px solid #d9e1ea;margin-top:1.5rem;padding-top:1rem}form{display:grid;gap:.8rem;margin-bottom:.8rem}label{display:grid;gap:.3rem;font-weight:600}input,textarea,button{font:inherit;padding:.65rem;border:1px solid #8795a8;border-radius:7px}textarea{min-height:8rem}button{width:max-content;background:#174ea6;color:#fff;font-weight:700}button:disabled{background:#8290a2}pre{white-space:pre-wrap;background:#edf2f7;padding:1rem;border-radius:7px}"""


def ui_script(api_port: int) -> bytes:
    return f"""const API='http://127.0.0.1:{api_port}';let token='';const login=document.querySelector('#login-form');const dashboard=document.querySelector('#dashboard');const fillDemo=document.querySelector('#fill-demo');const ai=document.querySelector('#ai-form');const identity=document.querySelector('#identity');const result=document.querySelector('#result');const review=document.querySelector('#review');const logout=document.querySelector('#logout');
async function api(path,options={{}}){{const headers={{Accept:'application/json',...(options.headers||{{}})}};if(token)headers.Authorization=`Bearer ${{token}}`;const response=await fetch(API+path,{{...options,headers}});let body=null;try{{body=await response.json()}}catch{{}}if(!response.ok)throw new Error(body?.error||`HTTP ${{response.status}}`);return body;}}
fillDemo.addEventListener('click',async()=>{{identity.textContent='Loading demo credentials…';try{{const body=await api('/api/auth/demo-credentials');login.email.value=body.email;login.password.value=body.password;identity.textContent='Demo credentials loaded. Select Sign In.';}}catch(error){{identity.textContent=`Demo credentials unavailable: ${{error.message}}`;}}}});
login.addEventListener('submit',async event=>{{event.preventDefault();identity.textContent='Signing in…';try{{const body=await api('/api/auth/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:login.email.value,password:login.password.value}})}});token=body.accessToken;login.password.value='';const me=await api('/api/auth/me');identity.textContent=`Signed in as ${{me.user.email}} (${{me.user.role}}).`;login.hidden=true;fillDemo.hidden=true;dashboard.hidden=false;}}catch(error){{token='';identity.textContent=`Login failed: ${{error.message}}`;dashboard.hidden=true;}}}});
ai.addEventListener('submit',async event=>{{event.preventDefault();result.textContent='Requesting live review…';try{{const body=await api('/api/ai/calculator-safety-review',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{prompt:ai.prompt.value}})}});result.textContent=`Receipt: ${{body.providerReceipt.requestId}}\nModel: ${{body.model}}\n\n${{body.content}}`;}}catch(error){{result.textContent=`Review failed: ${{error.message}}`;}}}});
logout.addEventListener('click',async()=>{{try{{await api('/api/auth/logout',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});}}finally{{token='';identity.textContent='Not signed in.';result.textContent='Sign in to request a review.';dashboard.hidden=true;login.hidden=false;fillDemo.hidden=false;}}}});""".encode()


def ui_handler(config: Config) -> type[BaseHTTPRequestHandler]:
    class UiHandler(BaseHTTPRequestHandler):
        server_version = "IOSCalculatorCompanionUI/1"
        sys_version = ""

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            resources = {
                "/": ("text/html; charset=utf-8", UI_DOCUMENT),
                "/index.html": ("text/html; charset=utf-8", UI_DOCUMENT),
                "/style.css": ("text/css; charset=utf-8", UI_STYLE),
                "/app.js": ("text/javascript; charset=utf-8", ui_script(config.api_port)),
            }
            if path not in resources:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type, document = resources[path]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(document)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", f"default-src 'self'; connect-src http://127.0.0.1:{config.api_port}; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(document)
    return UiHandler


def create_servers(config: Config, service: RuntimeService | None = None, api_port: int | None = None, ui_port: int | None = None) -> tuple[ThreadingHTTPServer, ThreadingHTTPServer]:
    resolved_service = service or RuntimeService(config)
    api_server = ThreadingHTTPServer(("127.0.0.1", config.api_port if api_port is None else api_port), api_handler(resolved_service))
    try:
        ui_server = ThreadingHTTPServer(("127.0.0.1", config.ui_port if ui_port is None else ui_port), ui_handler(config))
    except OSError:
        api_server.server_close()
        raise
    return api_server, ui_server


def run() -> int:
    try:
        config = Config.from_env()
        service = RuntimeService(config)
        api_server, ui_server = create_servers(config, service)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"event": "startup_failed", "error": type(error).__name__, "message": str(error)}), file=sys.stderr, flush=True)
        return 1
    stop = threading.Event()

    def request_stop(signum: int, _frame: object) -> None:
        print(json.dumps({"event": "server_stopping", "signal": signal.Signals(signum).name}), flush=True)
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    threads = [
        threading.Thread(target=api_server.serve_forever, name="api-server", daemon=True),
        threading.Thread(target=ui_server.serve_forever, name="ui-server", daemon=True),
    ]
    for thread in threads:
        thread.start()
    print(json.dumps({"event": "servers_started", "apiPort": config.api_port, "uiPort": config.ui_port}), flush=True)
    try:
        while not stop.wait(0.25):
            if not all(thread.is_alive() for thread in threads):
                raise RuntimeError("a companion listener exited unexpectedly")
    finally:
        api_server.shutdown()
        ui_server.shutdown()
        api_server.server_close()
        ui_server.server_close()
        for thread in threads:
            thread.join(timeout=5)
    print(json.dumps({"event": "servers_stopped"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
