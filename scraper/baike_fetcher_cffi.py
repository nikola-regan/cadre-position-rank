"""
Baidu Baike fetcher using curl_cffi — mimics Chrome's TLS fingerprint
to bypass WAF detection that catches Python's requests/urllib3.

Why this exists:
   The standard `requests` library uses urllib3, which has a Python-specific
   TLS handshake (cipher order, ALPN, JA3 fingerprint). Modern WAFs like
   Baidu's recognize this signature and reject. Real browsers and curl have
   different signatures. `curl_cffi` uses libcurl underneath but lets you
   pick a browser to impersonate — same TLS fingerprint as real Chrome.

Setup:
    pip install curl_cffi

Drop-in replacement for BaikeFetcher in pipeline_baike.py.
"""
from __future__ import annotations
import time
import random
import logging
from pathlib import Path
from baike_fetcher import BaikeFetcher, BAIKE_BASE, BROWSER_HEADERS

logger = logging.getLogger(__name__)


class CffiBaikeFetcher(BaikeFetcher):
    """Uses curl_cffi to impersonate a real Chrome browser TLS fingerprint."""

    NAME = "baike_cffi"

    # Chrome version to impersonate. Options: chrome116, chrome119, chrome120,
    # chrome123, chrome124, edge99, safari17_2_ios, etc.
    IMPERSONATE = "chrome124"

    def __init__(self, cache_dir: str | Path = "./cache",
                 min_delay: float = 1.5, max_delay: float = 3.5,
                 max_retries: int = 3, timeout: int = 25):
        super().__init__(cache_dir=cache_dir, min_delay=min_delay,
                         max_delay=max_delay, max_retries=max_retries,
                         timeout=timeout)

    def _get_session(self):
        """Override base — use curl_cffi Session with TLS impersonation."""
        if self._session is None:
            from curl_cffi import requests as cffi_requests
            self._session = cffi_requests.Session(impersonate=self.IMPERSONATE)
            self._session.headers.update(BROWSER_HEADERS)
            logger.info(f"curl_cffi session impersonating: {self.IMPERSONATE}")
        return self._session

    def _warmup(self):
        if self._warmed:
            return
        try:
            sess = self._get_session()
            logger.info("Warming up: GET baike.baidu.com (homepage)")
            r = sess.get(BAIKE_BASE + "/", timeout=self.timeout)
            # curl_cffi cookies behave differently — iterate to get names
            try:
                cookie_names = [c.name for c in sess.cookies]
            except Exception:
                cookie_names = []
            logger.info(f"  homepage status={r.status_code}, cookies: {cookie_names}")
            time.sleep(random.uniform(1.5, 3.0))
            self._warmed = True
        except Exception as e:
            logger.warning(f"  warmup failed: {e}")
            self._warmed = True

    def fetch(self, url: str, force_refresh: bool = False) -> str:
        """Override base fetch — curl_cffi Response has no apparent_encoding;
        but its .text already does the right encoding detection."""
        cache_p = self._cache_path(url)
        if cache_p.exists() and not force_refresh:
            return cache_p.read_text(encoding="utf-8")

        self._warmup()
        time.sleep(random.uniform(self.min_delay, self.max_delay))
        sess = self._get_session()
        last_err = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"GET {url} (attempt {attempt+1})")
                resp = sess.get(
                    url,
                    headers={"Referer": BAIKE_BASE + "/"},
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                if resp.status_code == 403:
                    last_err = Exception("403 Forbidden")
                    logger.warning(f"  403 Forbidden — backing off")
                    time.sleep(5 + random.uniform(0, 5))
                    continue
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                # curl_cffi auto-decodes; resp.text returns str
                html = resp.text
                cache_p.write_text(html, encoding="utf-8")
                return html
            except Exception as e:
                last_err = e
                logger.warning(f"  attempt {attempt+1} failed: {e}")
                time.sleep(2 ** attempt + random.uniform(0, 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")
