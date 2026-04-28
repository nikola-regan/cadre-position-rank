"""
Polite HTTP fetcher for Chinese provincial 组工网 (cadre management bureau)
任前公示 pages.

Design principles:
  - Rate-limited (1-3 second random delays)
  - Retries with exponential backoff on transient failures
  - Persistent caching (raw HTML is saved; if you re-run, it pulls from cache)
  - User-Agent that identifies a research bot (transparency)
  - Cleanly separates "fetching" from "parsing"

Each provincial source is one subclass of `BaseFetcher` that knows:
  - The URL pattern for index pages (list of recent 任前公示)
  - The URL pattern for detail pages (individual bio)
  - Site-specific HTML structure → list of bio paragraphs

Production usage: YOU run this on YOUR machine, NOT in this sandbox
(the sandbox blocks Chinese government domains via allowlist).
"""
from __future__ import annotations
import time
import random
import hashlib
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, Optional
import logging

logger = logging.getLogger(__name__)

USER_AGENT = (
    "AcademicResearchBot/0.1 "
    "(university-affiliated research; CPED-extension project; "
    "no commercial use; rate-limited at <=1 req/sec; contact: your-email-here)"
)


@dataclass
class FetchResult:
    url: str
    fetched_at: str           # ISO 8601 timestamp
    status_code: int
    content_type: str
    raw_html: str
    cache_hit: bool = False


class BaseFetcher:
    """Abstract base. Subclass for each source."""

    NAME = "base"
    BASE_URL = ""

    def __init__(self, cache_dir: str | Path = "./cache",
                 min_delay: float = 1.0, max_delay: float = 3.0,
                 max_retries: int = 3, timeout: int = 20):
        self.cache_dir = Path(cache_dir) / self.NAME
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.timeout = timeout

    def _cache_path(self, url: str) -> Path:
        h = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{h}.html"

    def fetch(self, url: str, force_refresh: bool = False) -> FetchResult:
        """Fetch a URL with caching and rate-limiting."""
        cache_p = self._cache_path(url)
        if cache_p.exists() and not force_refresh:
            return FetchResult(
                url=url,
                fetched_at=cache_p.with_suffix(".meta").read_text(),
                status_code=200,
                content_type="text/html",
                raw_html=cache_p.read_text(encoding="utf-8"),
                cache_hit=True,
            )

        # Polite delay
        time.sleep(random.uniform(self.min_delay, self.max_delay))

        import requests  # imported here so the parser/test path works without it
        last_err = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"GET {url} (attempt {attempt+1})")
                resp = requests.get(
                    url,
                    headers={"User-Agent": USER_AGENT,
                             "Accept-Language": "zh-CN,zh;q=0.9"},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding   # GB2312/GBK/UTF-8 auto-detect
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                cache_p.write_text(resp.text, encoding="utf-8")
                cache_p.with_suffix(".meta").write_text(ts)
                return FetchResult(url=url, fetched_at=ts,
                                   status_code=resp.status_code,
                                   content_type=resp.headers.get("Content-Type",""),
                                   raw_html=resp.text)
            except Exception as e:
                last_err = e
                logger.warning(f"  attempt {attempt+1} failed: {e}")
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_err}")

    # Subclass interface
    def list_index_urls(self, year: int) -> list[str]:
        """Yield URLs of index pages (lists of 任前公示) for given year."""
        raise NotImplementedError

    def parse_index(self, html: str) -> list[str]:
        """Extract detail-page URLs from an index page."""
        raise NotImplementedError

    def parse_detail(self, html: str) -> list[str]:
        """Extract one or more bio paragraphs from a detail page."""
        raise NotImplementedError

    # Convenience: full crawl for one year
    def crawl_year(self, year: int) -> Iterator[tuple[str, str]]:
        """Yields (detail_url, bio_paragraph_text) tuples."""
        for idx_url in self.list_index_urls(year):
            try:
                idx_res = self.fetch(idx_url)
            except Exception as e:
                logger.error(f"Skipping index {idx_url}: {e}")
                continue
            for detail_url in self.parse_index(idx_res.raw_html):
                try:
                    det_res = self.fetch(detail_url)
                except Exception as e:
                    logger.error(f"Skipping detail {detail_url}: {e}")
                    continue
                for bio_text in self.parse_detail(det_res.raw_html):
                    yield detail_url, bio_text


# -----------------------------------------------------------------------------
# EXAMPLE: Jiangsu Provincial 组工网 fetcher
# (URL patterns are illustrative — verify against current site before using)
# -----------------------------------------------------------------------------
class JiangsuFetcher(BaseFetcher):
    """Fetcher for 中共江苏省委新闻网 任免栏目.

    Verified URL patterns (April 2026):
      Index: https://www.zgjssw.gov.cn/fabuting/renmian/
      Detail: https://www.zgjssw.gov.cn/fabuting/renmian/YYYYMM/tYYYYMMDD_<id>.shtml
    """
    NAME     = "jiangsu"
    BASE_URL = "https://www.zgjssw.gov.cn"
    INDEX    = BASE_URL + "/fabuting/renmian/"

    def list_index_urls(self, year: int) -> list[str]:
        # The site uses descending-time pagination: index.shtml, index_1.shtml,
        # index_2.shtml, ... Real implementation should walk these until it hits
        # entries earlier than `year`.
        urls = [self.INDEX]
        urls += [f"{self.INDEX}index_{p}.shtml" for p in range(1, 20)]
        return urls

    # Match both old and new article URL patterns under YYYYMM/ directory:
    #   Old (2015-2020 era): ./201501/t1956809.shtml  (7-digit ID, no underscore)
    #   New (2021+ era):     /fabuting/renmian/202504/t20250418_8477849.shtml
    DETAIL_RE = re.compile(r"(\d{6})/t\d+(?:_\d+)?\.shtml")

    def parse_index(self, html: str, base_url: str = None) -> list[tuple[str, int]]:
        """Yield (full_url, yyyymm) tuples for detail pages found on this index."""
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        soup = BeautifulSoup(html, "html.parser")
        out = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = self.DETAIL_RE.search(href)
            if not m:
                continue
            full = urljoin(base_url or self.INDEX, href)
            if full in seen:
                continue
            seen.add(full)
            yyyymm = int(m.group(1))
            out.append((full, yyyymm))
        return out

    def crawl_year(self, year: int):
        """Override: filter detail URLs by year (extracted from URL itself)."""
        seen = set()
        n_in_year = 0
        for idx_url in self.list_index_urls(year):
            try:
                idx_res = self.fetch(idx_url)
            except Exception as e:
                logger.error(f"Skipping index {idx_url}: {e}")
                continue
            for detail_url, yyyymm in self.parse_index(idx_res.raw_html, base_url=idx_url):
                if yyyymm // 100 != year:
                    continue   # filter by year
                if detail_url in seen:
                    continue
                seen.add(detail_url)
                n_in_year += 1
                try:
                    det_res = self.fetch(detail_url)
                except Exception as e:
                    logger.error(f"Skipping detail {detail_url}: {e}")
                    continue
                for bio_text in self.parse_detail(det_res.raw_html):
                    yield detail_url, bio_text
        logger.info(f"Visited {n_in_year} detail URLs for year {year}")

    def parse_detail(self, html: str) -> list[str]:
        """Extract bio paragraphs from a detail page.

        The page may contain multiple bios concatenated in one article body
        (一次公示往往涉及几名干部). We split on indicators like 男, / 女,
        followed by a year, and treat each chunk as one bio.
        """
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(html, "html.parser")

        # Try common article-body containers first
        article = (soup.select_one(".article-body")
                   or soup.select_one(".TRS_Editor")
                   or soup.select_one("#zoom")
                   or soup.select_one(".content")
                   or soup.select_one(".article")
                   or soup.body
                   or soup)

        bios = []
        for para in article.find_all(["p", "div"]):
            text = para.get_text(separator="", strip=True)
            text = re.sub(r"\s+", " ", text)
            # Heuristic: a bio paragraph contains 男/女 + 年月生 + 现任/拟任
            if (re.search(r"[男女][,，、]", text)
                and re.search(r"\d{4}[年.]\d{1,2}", text)
                and re.search(r"现任|拟任|拟提名", text)
                and len(text) > 60):
                bios.append(text)

        # Fallback: if the article body is one giant blob, split heuristically.
        if not bios:
            big_text = re.sub(r"\s+", " ", article.get_text())
            chunks = re.split(r"(?=(?:[一-龥]{2,4})[,，、]\s*[男女][,，、])", big_text)
            for chunk in chunks:
                if (re.search(r"[男女][,，、]", chunk)
                    and re.search(r"\d{4}[年.]\d{1,2}", chunk)
                    and re.search(r"现任|拟任|拟提名", chunk)
                    and 60 < len(chunk) < 1500):
                    bios.append(chunk.strip())

        return bios


class GuangdongFetcher(BaseFetcher):
    """Stub for Guangdong 组工网. Fill in real URL patterns as you discover them."""
    NAME     = "guangdong"
    BASE_URL = "http://www.gdzz.gov.cn"

    def list_index_urls(self, year: int) -> list[str]:
        return [f"{self.BASE_URL}/gbgs/{year}/p{p}.html" for p in range(1, 6)]

    def parse_index(self, html: str) -> list[str]:
        # similar pattern to Jiangsu — adapt selectors per site
        raise NotImplementedError("Inspect actual HTML and fill in selectors")

    def parse_detail(self, html: str) -> list[str]:
        raise NotImplementedError


# -----------------------------------------------------------------------------
# Mock fetcher for testing without network access
# -----------------------------------------------------------------------------
class MockFetcher(BaseFetcher):
    """Returns hard-coded HTML for testing the pipeline end-to-end."""
    NAME = "mock"
    BASE_URL = "mock://example/"

    MOCK_INDEX_HTML = """
    <html><body><ul class="list">
      <li><a href="mock://example/detail/001.html">某地干部任前公示(一)</a></li>
      <li><a href="mock://example/detail/002.html">某地干部任前公示(二)</a></li>
    </ul></body></html>
    """

    MOCK_DETAIL_HTML = {
        "mock://example/detail/001.html": """
        <html><body><div class="article-body">
        <p>张三,男,汉族,1972年5月生,江苏宿迁人,1995年7月加入中国共产党,
        1994年7月参加工作,中央党校研究生学历。
        现任江苏省委组织部副部长,拟任江苏省委组织部部长。</p>
        <p>李四,男,汉族,1975年8月生,江苏南京人,1998年6月入党,
        1997年7月参加工作,南京大学硕士研究生学历。
        现任南京市委办公室主任,拟任南京市某区委书记。</p>
        </div></body></html>
        """,
        "mock://example/detail/002.html": """
        <html><body><div class="article-body">
        <p>王芳,女,汉族,1980年8月生,江苏苏州人,2003年5月入党,2002年7月参加工作,
        东南大学博士。现任苏州市经信委副主任,拟任苏州市某局局长。</p>
        </div></body></html>
        """,
    }

    def fetch(self, url: str, force_refresh: bool = False) -> FetchResult:
        if "detail" in url:
            html = self.MOCK_DETAIL_HTML.get(url, "")
        else:
            html = self.MOCK_INDEX_HTML
        return FetchResult(url=url, fetched_at="2026-04-15T10:00:00Z",
                           status_code=200, content_type="text/html",
                           raw_html=html, cache_hit=False)

    def list_index_urls(self, year: int) -> list[str]:
        return ["mock://example/index.html"]

    def parse_index(self, html: str) -> list[str]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return [a.get("href") for a in soup.select("ul.list a")]

    def parse_detail(self, html: str) -> list[str]:
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(html, "html.parser")
        bios = []
        for p in soup.select(".article-body p"):
            text = re.sub(r"\s+", " ", p.get_text(strip=True))
            if "现任" in text or "拟任" in text or "拟提名" in text:
                bios.append(text)
        return bios
