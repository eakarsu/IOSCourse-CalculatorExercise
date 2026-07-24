from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from companion.runtime import (
    CANONICAL_OPENROUTER_BASE,
    Config,
    ProviderError,
    RuntimeService,
    create_servers,
)


def config_for(directory: str) -> Config:
    return Config(
        api_port=31000,
        ui_port=31001,
        database_path=Path(directory) / "runtime.sqlite",
        admin_email="runtime-admin@example.com",
        admin_password="RuntimeAcceptance123!",
        session_ttl_hours=12,
        openrouter_api_key="test-key",
        openrouter_model="test/model",
        openrouter_base_url=CANONICAL_OPENROUTER_BASE,
    )


def fake_provider(_config: Config, prompt: str) -> dict[str, object]:
    return {
        "receipt": "test-provider-receipt-123",
        "model": "test/model",
        "content": f"Evidence-backed safety review for: {prompt}",
    }


class RuntimeTests(unittest.TestCase):
    def test_environment_requires_distinct_ports_and_canonical_provider(self) -> None:
        environment = {
            "API_PORT": "31000", "UI_PORT": "31000", "DATABASE_PATH": "/tmp/test.sqlite",
            "ADMIN_EMAIL": "runtime-admin@example.com", "ADMIN_PASSWORD": "RuntimeAcceptance123!",
            "SESSION_TTL_HOURS": "12", "OPENROUTER_API_KEY": "key", "OPENROUTER_MODEL": "model",
            "OPENROUTER_BASE_URL": CANONICAL_OPENROUTER_BASE,
        }
        with self.assertRaisesRegex(ValueError, "distinct"):
            Config.from_env(environment)
        environment["UI_PORT"] = "31001"
        environment["OPENROUTER_BASE_URL"] = "https://example.com/v1"
        with self.assertRaisesRegex(ValueError, "must equal"):
            Config.from_env(environment)

    def test_credentials_sessions_and_ai_results_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = config_for(directory)
            service = RuntimeService(config, fake_provider)
            self.assertIsNone(service.store.login(config.admin_email, "wrong-password-value"))
            login = service.store.login(config.admin_email, config.admin_password)
            self.assertIsNotNone(login)
            token, _ = login or ("", {})
            authenticated = service.bearer_identity(f"Bearer {token}")
            self.assertIsNotNone(authenticated)
            result = service.ask(authenticated[1], "Check calculator output approval and rollback controls")  # type: ignore[index]
            restarted = RuntimeService(config, fake_provider)
            persisted_identity = restarted.bearer_identity(f"Bearer {token}")
            self.assertIsNotNone(persisted_identity)
            row = restarted.store.interaction(result["interactionId"], persisted_identity[1]["id"])  # type: ignore[index]
            self.assertEqual(row["status"], "SUCCEEDED")  # type: ignore[index]
            self.assertEqual(row["provider_receipt"], "test-provider-receipt-123")  # type: ignore[index]
            self.assertTrue(restarted.store.revoke(token))
            self.assertIsNone(restarted.bearer_identity(f"Bearer {token}"))

    def test_unexpected_provider_failure_is_controlled_and_persisted(self) -> None:
        def broken_provider(_config: Config, _prompt: str) -> dict[str, object]:
            raise RuntimeError("unexpected provider parser failure")

        with tempfile.TemporaryDirectory() as directory:
            config = config_for(directory)
            service = RuntimeService(config, broken_provider)
            login = service.store.login(config.admin_email, config.admin_password)
            self.assertIsNotNone(login)
            token, _ = login or ("", {})
            authenticated = service.bearer_identity(f"Bearer {token}")
            self.assertIsNotNone(authenticated)
            with self.assertRaisesRegex(ProviderError, "failed safely") as raised:
                service.ask(authenticated[1], "Exercise the safe provider failure boundary")  # type: ignore[index]
            self.assertEqual(raised.exception.code, "AI_INTERNAL_ERROR")
            with closing(service.store.connect()) as database:
                row = database.execute("SELECT status,error_code FROM ai_interactions ORDER BY created_at DESC LIMIT 1").fetchone()
            self.assertEqual(dict(row), {"status": "FAILED", "error_code": "AI_INTERNAL_ERROR"})

    def test_http_login_identity_denial_ai_persistence_and_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = config_for(directory)
            service = RuntimeService(config, fake_provider)
            api, ui = create_servers(config, service, api_port=0, ui_port=0)
            threads = [threading.Thread(target=api.serve_forever), threading.Thread(target=ui.serve_forever)]
            for thread in threads:
                thread.start()
            api_base = f"http://127.0.0.1:{api.server_address[1]}"
            ui_base = f"http://127.0.0.1:{ui.server_address[1]}"

            def request(path: str, method: str = "GET", body: dict | None = None, token: str | None = None):
                headers = {"Accept": "application/json"}
                data = None
                if body is not None:
                    headers["Content-Type"] = "application/json"
                    data = json.dumps(body).encode()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                try:
                    with urllib.request.urlopen(urllib.request.Request(api_base + path, data=data, method=method, headers=headers), timeout=5) as response:
                        return response.status, json.loads(response.read())
                except urllib.error.HTTPError as error:
                    try:
                        return error.code, json.loads(error.read())
                    finally:
                        error.close()

            try:
                denied, _ = request("/api/ai/calculator-safety-review", "POST", {"prompt": "anonymous request must fail"})
                self.assertEqual(denied, 401)
                status, login = request("/api/auth/login", "POST", {"email": config.admin_email, "password": config.admin_password})
                self.assertEqual(status, 200)
                token = login["accessToken"]
                status, identity = request("/api/auth/me", token=token)
                self.assertEqual(status, 200)
                self.assertEqual(identity["user"]["authType"], "SESSION")
                status, result = request("/api/ai/calculator-safety-review", "POST", {"prompt": "Review calculation evidence and rollback controls"}, token)
                self.assertEqual(status, 200)
                self.assertEqual(result["providerReceipt"]["requestId"], "test-provider-receipt-123")
                status, durable = request(f"/api/ai/interactions/{result['interactionId']}", token=token)
                self.assertEqual(status, 200)
                self.assertEqual(durable["interaction"]["status"], "SUCCEEDED")
                with urllib.request.urlopen(ui_base, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    document = response.read()
                    self.assertIn(b"does not replace or emulate", document)
                    self.assertIn(b'id="login-form"', document)
                with urllib.request.urlopen(ui_base + "/app.js", timeout=5) as response:
                    script = response.read()
                    self.assertIn(b"/api/auth/login", script)
                    self.assertIn(b"/api/auth/me", script)
                    self.assertIn(b"/api/ai/calculator-safety-review", script)
            finally:
                api.shutdown()
                ui.shutdown()
                api.server_close()
                ui.server_close()
                for thread in threads:
                    thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
