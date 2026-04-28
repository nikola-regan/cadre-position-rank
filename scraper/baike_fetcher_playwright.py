"""
Playwright-based Baidu Baike fetcher — uses a real headless Chromium browser.

Use this as fallback when requests-based fetcher gets 403 from Baidu's WAF.
Real browser sends full TLS fingerprint, runs JS, handles cookies — bypasses
nearly all bot-detection heuristics.

Slower (~3-5x) than requests but much more reliable for protected sites.

Setup:
    pip install playwright
    python -m playwright install chromium

Usage as drop-in replacement for BaikeFetcher:
    from baike_fetcher_playwright import PlaywrightBaikeFetcher
    fetcher = PlaywrightBaikeFetcher(cache_dir="./cache")
    # rest of pipeline_baike.py works as-is
"""
from __future__ import annotations
import time
import random
import hashlib
import logging
from pathlib import Path
from urllib.parse import quote
from baike_fetcher import BaikeFetcher, BAIKE_BASE   # reuse search/disambiguate

logger = logging.getLogger(__name__)


class PlaywrightBaikeFetcher(BaikeFetcher):
    """Uses Playwright headless Chromium for fetches."""

    NAME = "baike_pw"

    def __init__(self, cache_dir="./cache", min_delay=2.0, max_delay=4.0,
                 max_retries=2, timeout=30, headless=True):
        super().__init__(cache_dir=cache_dir, min_delay=min_delay,
                         max_delay=max_delay, max_retries=max_retries,
                         timeout=timeout)
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure_browser(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            locale="zh-CN",
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 800},
        )
        self._page = self._context.new_page()
        # Warmup: visit homepage
        logger.info("Playwright: warming up at baike.baidu.com")
        self._page.goto(BAIKE_BASE + "/", wait_until="domcontentloaded",
                        timeout=self.timeout * 1000)
        time.sleep(2.0)

    def fetch(self, url: str, force_refresh: bool = False) -> str:
        cache_p = self._cache_path(url)
        if cache_p.exists() and not force_refresh:
            return cache_p.read_text(encoding="utf-8")

        self._ensure_browser()
        time.sleep(random.uniform(self.min_delay, self.max_delay))

        last_err = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Playwright GET {url} (attempt {attempt+1})")
                self._page.goto(url, wait_until="domcontentloaded",
                                timeout=self.timeout * 1000)
                time.sleep(1.0)
                html = self._page.content()
                if "403" in html[:300] or "Forbidden" in html[:300]:
                    raise RuntimeError("Page returned 403 even via browser")
                cache_p.write_text(html, encoding="utf-8")
                return html
            except Exception as e:
                last_err = e
                logger.warning(f"  attempt {attempt+1} failed: {e}")
                time.sleep(3 + random.uniform(0, 3))
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    def close(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
