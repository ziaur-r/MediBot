"""
Corporate SSL fix for SSL certificate verification in corporate proxy environments.

Strategy:
  1. Patch ssl module's default context creation
  2. Patch urllib3 HTTPSConnectionPool to disable verification
  3. Disable certificate verification in requests globally
  4. Configure huggingface_hub to use insecure sessions
  5. Set environment variables to disable SSL globally

Call `apply()` once at process start, BEFORE any network library is imported.
"""
from __future__ import annotations
import os
import ssl


def apply() -> None:
    # ── 0. Patch ssl module default context ──────────────────────────────────
    try:
        # Force Python's ssl module to use unverified context
        _original_create_default_context = ssl.create_default_context
        
        def _patched_create_default_context(*args, **kwargs):  # type: ignore[no-untyped-def]
            ctx = _original_create_default_context(*args, **kwargs)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        
        ssl.create_default_context = _patched_create_default_context
        ssl._create_default_https_context = _patched_create_default_context  # type: ignore[attr-defined]
    except Exception:
        pass

    # ── 1. Patch urllib3 HTTPSConnectionPool ────────────────────────────────
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Disable SSL verification at connection pool level
        urllib3.poolmanager.PoolManager.connection_pool_kw = {
            "cert_reqs": "CERT_NONE",
            "ca_certs": None,
            "ssl_version": ssl.PROTOCOL_TLS,
            "ssl_context": None,
        }
    except Exception:
        pass

    # ── 2. Patch requests library ────────────────────────────────────────────
    try:
        import requests
        from requests.adapters import HTTPAdapter
        
        # Monkey-patch HTTPAdapter to disable verification
        _original_init = HTTPAdapter.__init__
        
        def _patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _original_init(self, *args, **kwargs)
            self.verify = False
        
        HTTPAdapter.__init__ = _patched_init
    except Exception:
        pass

    # ── 3. huggingface_hub explicit backend session ──────────────────────────
    try:
        import requests as _requests
        from huggingface_hub import configure_http_backend

        def _insecure_backend() -> _requests.Session:
            s = _requests.Session()
            s.verify = False
            return s

        configure_http_backend(backend_factory=_insecure_backend)
    except Exception:
        pass

    # ── 4. Environment variables (catch-all) ─────────────────────────────────
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    os.environ["CURL_CA_BUNDLE"] = ""
    os.environ["PYTHONWARNINGS"] = "ignore:Unverified HTTPS request"


