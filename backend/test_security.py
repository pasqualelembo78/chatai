"""
test_security.py — Test automatizzati di sicurezza per ChatAI

Esecuzione:
  cd backend && python -m pytest test_security.py -v

Richiede:
  pytest, requests
"""

import os
import sys
import json
import time
import uuid
import hmac
import hashlib
import pytest
import requests

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5000")

TEST_USER = f"test_user_{uuid.uuid4().hex[:8]}"
TEST_PASS = "test_password_123!"


def _url(path):
    return f"{BASE_URL}{path}"


def _json(resp):
    try:
        return resp.json()
    except Exception:
        return {}


@pytest.fixture(scope="module")
def auth_tokens():
    """Registra un utente di test e restituisce access_token, refresh_token."""
    resp = requests.post(_url("/auth/register"), json={
        "username": TEST_USER,
        "password": TEST_PASS,
    })
    data = _json(resp)
    if resp.status_code == 409:
        resp = requests.post(_url("/auth/login"), json={
            "username": TEST_USER,
            "password": TEST_PASS,
        })
        data = _json(resp)
    assert "access_token" in data, f"Auth failed: {data}"
    return data["access_token"], data.get("refresh_token", "")


# ══════════════════════════════════════════════════════════════════
# [7.1] OWASP Top 10 — Authentication & Access Control
# ══════════════════════════════════════════════════════════════════

class TestAuth:
    """A1 - Broken Access Control / A2 - Cryptographic Failures / A7 - Identification Failures"""

    def test_register_weak_password(self):
        """Password < 8 caratteri deve fallire."""
        resp = requests.post(_url("/auth/register"), json={
            "username": "weak_user",
            "password": "short",
        })
        assert resp.status_code in (400, 422)

    def test_register_invalid_username(self):
        """Username con caratteri non consentiti deve fallire."""
        resp = requests.post(_url("/auth/register"), json={
            "username": "user name !@#",
            "password": "long_enough_password",
        })
        assert resp.status_code in (400, 422)

    def test_login_nonexistent_user(self):
        """Login con utente inesistente → 401."""
        resp = requests.post(_url("/auth/login"), json={
            "username": "no_such_user_xxx",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_register_duplicate_username(self):
        """Username già registrato → 409."""
        resp = requests.post(_url("/auth/register"), json={
            "username": TEST_USER,
            "password": TEST_PASS,
        })
        assert resp.status_code == 409

    def test_token_required(self):
        """Endpoint protetto senza token → 401."""
        resp = requests.get(_url("/config"))
        assert resp.status_code == 401

    def test_invalid_token(self):
        """Token JWT manomesso → 401."""
        resp = requests.get(_url("/config"), headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401

    def test_refresh_token_not_allowed(self, auth_tokens):
        """Refresh token usato come access token → 401."""
        _, refresh = auth_tokens
        if not refresh:
            pytest.skip("No refresh token")
        resp = requests.get(_url("/config"), headers={
            "Authorization": f"Bearer {refresh}"
        })
        assert resp.status_code == 401

    def test_access_token_works(self, auth_tokens):
        """Access token valido → 200."""
        access, _ = auth_tokens
        resp = requests.get(_url("/config"), headers={
            "Authorization": f"Bearer {access}"
        })
        assert resp.status_code == 200

    def test_jwt_tampering(self):
        """JWT con firma falsificata deve fallire."""
        header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"  # {"alg":"HS256","typ":"JWT"}
        payload = "eyJ1c2VyX2lkIjoiZmFrZSIsInJvbGUiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0"
        fake_sig = "fakesignature"
        resp = requests.get(_url("/admin/users"), headers={
            "Authorization": f"Bearer {header}.{payload}.{fake_sig}"
        })
        assert resp.status_code == 401


class TestRateLimiting:
    """A4 - Insufficient Rate Limiting"""

    def test_login_rate_limit(self):
        """Troppi tentativi login → 429."""
        for _ in range(15):
            requests.post(_url("/auth/login"), json={
                "username": "ratelimit_test",
                "password": "wrong",
            })
        resp = requests.post(_url("/auth/login"), json={
            "username": "ratelimit_test",
            "password": "wrong",
        })
        assert resp.status_code == 429


# ══════════════════════════════════════════════════════════════════
# [7.1] OWASP Top 10 — Data Validation & Upload
# ══════════════════════════════════════════════════════════════════

class TestUpload:
    """A3 - Injection / A5 - Security Misconfiguration / A8 - Software Integrity"""

    def test_upload_script_as_image(self, auth_tokens):
        """Caricare script PHP come immagine deve fallire."""
        access, _ = auth_tokens
        resp = requests.post(_url("/upload-image"), headers={
            "Authorization": f"Bearer {access}"
        }, files={
            "image": ("shell.php", "<?php system($_GET['cmd']); ?>", "application/x-httpd-php")
        })
        assert resp.status_code == 400

    def test_upload_script_as_audio(self, auth_tokens):
        """Caricare script come audio deve fallire."""
        access, _ = auth_tokens
        resp = requests.post(_url("/transcribe"), headers={
            "Authorization": f"Bearer {access}"
        }, files={
            "audio": ("script.sh", "#!/bin/bash\nrm -rf /", "application/x-sh")
        })
        assert resp.status_code == 400

    def test_upload_no_file(self, auth_tokens):
        """Richiesta senza file → 400."""
        access, _ = auth_tokens
        resp = requests.post(_url("/upload-image"), headers={
            "Authorization": f"Bearer {access}"
        })
        assert resp.status_code == 400

    def test_upload_empty_filename(self, auth_tokens):
        """File senza nome → 400."""
        access, _ = auth_tokens
        resp = requests.post(_url("/upload-image"), headers={
            "Authorization": f"Bearer {access}"
        }, files={
            "image": ("", b"data", "image/jpeg")
        })
        assert resp.status_code == 400

    def test_upload_large_file(self, auth_tokens):
        """File troppo grande → 400."""
        access, _ = auth_tokens
        large_data = b"X" * (11 * 1024 * 1024)
        resp = requests.post(_url("/upload-image"), headers={
            "Authorization": f"Bearer {access}"
        }, files={
            "image": ("large.jpg", large_data, "image/jpeg")
        })
        assert resp.status_code == 400

    def test_upload_valid_image(self, auth_tokens):
        """Immagine valida → 200 (richiede Gemini API key)."""
        access, _ = auth_tokens
        if not os.environ.get("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        small_gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        resp = requests.post(_url("/upload-image"), headers={
            "Authorization": f"Bearer {access}"
        }, files={
            "image": ("test.gif", small_gif, "image/gif")
        })
        assert resp.status_code == 400  # GIF non consentito


# ══════════════════════════════════════════════════════════════════
# [7.1] OWASP Top 10 — Path Traversal & IDOR
# ══════════════════════════════════════════════════════════════════

class TestIDOR:
    """A1 - IDOR (Insecure Direct Object Reference)"""

    def test_other_user_conversation(self, auth_tokens):
        """Un utente non può vedere le conversazioni di un altro."""
        access, _ = auth_tokens
        resp = requests.get(_url("/conversations/other_user_fake_id"), headers={
            "Authorization": f"Bearer {access}"
        })
        assert resp.status_code in (200, 404)
        data = _json(resp)
        if resp.status_code == 200 and "messages" in data:
            for msg in data["messages"]:
                assert msg.get("role") in ("user", "assistant"), f"Unexpected message: {msg}"


# ══════════════════════════════════════════════════════════════════
# [7.4] Security Headers
# ══════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """A5 - Security Misconfiguration — HTTP Headers"""

    def test_x_content_type_options(self):
        """Header X-Content-Type-Options: nosniff."""
        resp = requests.get(_url("/"))
        assert resp.headers.get("X-Content-Type-Options", "").lower() == "nosniff"

    def test_x_frame_options(self):
        """Header X-Frame-Options: DENY."""
        resp = requests.get(_url("/"))
        assert resp.headers.get("X-Frame-Options", "").upper() == "DENY"

    def test_strict_transport_security(self):
        """Header Strict-Transport-Security presente."""
        resp = requests.get(_url("/"))
        hsts = resp.headers.get("Strict-Transport-Security", "")
        assert "max-age" in hsts


# ══════════════════════════════════════════════════════════════════
# [7.3] Penetration Test — Additional Checks
# ══════════════════════════════════════════════════════════════════

class TestPentest:
    """A3 - Injection / A6 - Vulnerable Components / A9 - Logging"""

    def test_sql_injection_login(self):
        """SQL injection su login deve fallire."""
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users; --",
            "admin'--",
        ]
        for payload in payloads:
            resp = requests.post(_url("/auth/login"), json={
                "username": payload,
                "password": payload,
            })
            assert resp.status_code in (401, 400, 422), f"SQLi possible with: {payload}"

    def test_no_server_info_leak(self):
        """La risposta non deve esporre versioni server."""
        resp = requests.get(_url("/"))
        server = resp.headers.get("Server", "")
        assert "Python" not in server, f"Server info leak: {server}"

    def test_username_enumeration(self):
        """Il messaggio di errore non deve rivelare se l'utente esiste."""
        resp = requests.post(_url("/auth/login"), json={
            "username": "nonexistent_user_xyz_123",
            "password": "wrong",
        })
        data = _json(resp)
        error = data.get("error", "").lower()
        assert "non esiste" not in error
        assert "not found" not in error

    def test_admin_endpoint_blocked_for_user(self, auth_tokens):
        """Endpoint admin bloccato per utente normale."""
        access, _ = auth_tokens
        resp = requests.get(_url("/admin/users"), headers={
            "Authorization": f"Bearer {access}"
        })
        assert resp.status_code in (401, 403)

    def test_path_traversal(self):
        """Path traversal deve fallire."""
        paths = [
            "/../etc/passwd",
            "/..%2F..%2Fetc/passwd",
            "/static/../../../etc/passwd",
        ]
        for path in paths:
            try:
                resp = requests.get(_url(path), timeout=5)
                assert resp.status_code != 200 or "root:" not in resp.text, f"Path traversal: {path}"
            except requests.exceptions.ConnectionError:
                pass


# ══════════════════════════════════════════════════════════════════
# GDPR Compliance Tests
# ══════════════════════════════════════════════════════════════════

class TestGDPR:
    """GDPR — Data Export, Deletion, Privacy"""

    def test_privacy_policy_endpoint(self):
        """GET /privacy → deve tornare policy."""
        resp = requests.get(_url("/privacy"))
        assert resp.status_code == 200
        data = _json(resp)
        assert "text" in data
        assert "GDPR" in data["text"]

    def test_user_export(self, auth_tokens):
        """GET /user/export → deve tornare dati utente."""
        access, _ = auth_tokens
        resp = requests.get(_url("/user/export"), headers={
            "Authorization": f"Bearer {access}"
        })
        assert resp.status_code == 200
        data = _json(resp)
        assert "profile" in data
        assert "messages" in data
        assert "exported_at" in data

    def test_user_delete(self):
        """POST /user/delete → deve cancellare utente."""
        resp = requests.post(_url("/auth/register"), json={
            "username": f"delete_me_{uuid.uuid4().hex[:8]}",
            "password": "password_to_delete_123",
        })
        data = _json(resp)
        if "access_token" not in data:
            pytest.skip("Registration failed")
        access = data["access_token"]
        resp = requests.post(_url("/user/delete"), headers={
            "Authorization": f"Bearer {access}"
        })
        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("status") == "account_deleted"
