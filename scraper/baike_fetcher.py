"""
Baidu Baike fetcher: search by name, disambiguate, fetch entry pages.

Search URL pattern:
    https://baike.baidu.com/search?query=<name>

Entry URL pattern:
    https://baike.baidu.com/item/<name>             # canonical (1 entry exists)
    https://baike.baidu.com/item/<name>/<id>        # disambiguated (multiple)

Disambiguation strategy:
  1. Search → list of candidate entry URLs
  2. For each candidate, fetch the first 2000 chars
  3. Score by (a) birth-date match, (b) position keyword match
  4. Pick highest-scoring candidate; require min score to accept

Run on YOUR machine, not in this sandbox (sandbox blocks baidu.com).
"""
from __future__ import annotations
import re
import time
import random
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urljoin

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Baidu's WAF checks for full browser-fingerprint headers, not just User-Agent.
# These headers mimic what Chrome 124 on macOS sends with every navigation.
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8,"
               "application/signed-exchange;v=b3;q=0.7"),
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

BAIKE_BASE       = "https://baike.baidu.com"
SEARCH_URL_FMT   = BAIKE_BASE + "/search?query={query}"
ENTRY_DIRECT_FMT = BAIKE_BASE + "/item/{name}"

# Use baidu.com (web search, not baike subdomain) with site: filter to find
# the specific Baike entry. Web search returns disambiguated /item/X/<id>
# URLs reliably even when baike's own search is JS-rendered.
WEB_SEARCH_FMT   = "https://www.baidu.com/s?wd={query}"

# Location-hint extraction: pull a city/province name from current_position
# text. Common forms: "苏州市X局", "江苏省X厅", "镇江市委X部".
RE_LOCATION_HINT = re.compile(
    r"^([一-龥]{2,5}(?:市|省|区|县|州))"
)


@dataclass
class BaikeCandidate:
    name: str
    url: str
    snippet: str        # short description from search result
    score: float = 0.0
    matched_fields: tuple = ()


class BaikeFetcher:
    """Polite Baidu Baike fetcher with cache and retries."""

    NAME = "baike"

    def __init__(self, cache_dir: str | Path = "./cache",
                 min_delay: float = 2.0, max_delay: float = 5.0,
                 max_retries: int = 3, timeout: int = 25):
        self.cache_dir = Path(cache_dir) / self.NAME
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self._session = None     # lazily initialized
        self._warmed = False     # has homepage been visited?

    def _get_session(self):
        """Lazily create a persistent requests.Session for cookie continuity."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update(BROWSER_HEADERS)
        return self._session

    def _warmup(self):
        """Hit baike.baidu.com homepage to get the BAIDUID cookie that the
        WAF expects on subsequent requests."""
        if self._warmed:
            return
        try:
            sess = self._get_session()
            logger.info("Warming up: GET baike.baidu.com (homepage)")
            r = sess.get(BAIKE_BASE + "/", timeout=self.timeout)
            logger.info(f"  homepage status={r.status_code}, "
                        f"got cookies: {list(sess.cookies.keys())}")
            time.sleep(random.uniform(1.5, 3.0))
            self._warmed = True
        except Exception as e:
            logger.warning(f"  warmup failed (continuing anyway): {e}")
            self._warmed = True   # don't keep retrying

    def _cache_path(self, url: str) -> Path:
        h = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{h}.html"

    def fetch(self, url: str, force_refresh: bool = False) -> str:
        cache_p = self._cache_path(url)
        if cache_p.exists() and not force_refresh:
            return cache_p.read_text(encoding="utf-8")

        # Make sure we've established a session with cookies first
        self._warmup()

        time.sleep(random.uniform(self.min_delay, self.max_delay))
        sess = self._get_session()
        # Per-request: set Referer to look like normal browsing
        per_req_headers = {"Referer": BAIKE_BASE + "/"}
        last_err = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"GET {url} (attempt {attempt+1})")
                resp = sess.get(
                    url,
                    headers=per_req_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                if resp.status_code == 403:
                    # Often retryable after a longer pause
                    last_err = Exception(f"403 Forbidden")
                    logger.warning(f"  403 Forbidden — backing off")
                    time.sleep(5 + random.uniform(0, 5))
                    continue
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                cache_p.write_text(resp.text, encoding="utf-8")
                return resp.text
            except Exception as e:
                last_err = e
                logger.warning(f"  attempt {attempt+1} failed: {e}")
                time.sleep(2 ** attempt + random.uniform(0, 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    # -------------------------------------------------------------------
    @staticmethod
    def extract_location_hint(position: Optional[str]) -> Optional[str]:
        """Pull the city/province from a 现任职务 string."""
        if not position:
            return None
        m = RE_LOCATION_HINT.search(position)
        return m.group(1) if m else None

    def search_via_web(self, name: str,
                        location_hint: Optional[str] = None) -> list[BaikeCandidate]:
        """Use baidu.com web search with site: filter to locate the specific
        Baike entry for a person. More reliable than baike's own search,
        which is JS-rendered."""
        from bs4 import BeautifulSoup
        from urllib.parse import quote_plus

        terms = [name]
        if location_hint:
            terms.append(location_hint)
        terms.append("site:baike.baidu.com")
        query = " ".join(terms)
        url = WEB_SEARCH_FMT.format(query=quote_plus(query))
        try:
            html = self.fetch(url)
        except Exception as e:
            logger.warning(f"  web-search failed for {name}: {e}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        seen = set()

        # Web search results — links to baike.baidu.com/item/<name>/<id>
        # appear in result anchor tags (and as "real URL" fields)
        item_re = re.compile(r"baike\.baidu\.com/item/[^\"']+")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            # Direct match on Baike URL anywhere
            for m in item_re.finditer(href + " " + text):
                url_raw = m.group(0)
                if "?" in url_raw:
                    url_raw = url_raw.split("?", 1)[0]
                full = "https://" + url_raw
                if full in seen:
                    continue
                seen.add(full)
                candidates.append(BaikeCandidate(
                    name=text[:100], url=full, snippet=text[:300]
                ))
                break

        # Also scan plaintext for baike URLs (sometimes shown as breadcrumb)
        for m in item_re.finditer(html):
            url_raw = m.group(0).split("?", 1)[0]
            full = "https://" + url_raw
            if full in seen:
                continue
            seen.add(full)
            candidates.append(BaikeCandidate(
                name=name, url=full, snippet=""
            ))

        if candidates:
            logger.info(f"  web-search for '{query}': {len(candidates)} Baike URLs found")
        return candidates

    def search(self, name: str,
               location_hint: Optional[str] = None) -> list[BaikeCandidate]:
        """Return candidate entry URLs for a name query.
        First try Baidu web search with site:baike.baidu.com filter
        (returns specific /item/<name>/<id> URLs).  Fallback to Baike's
        own search and direct /item/<name> with polysemy extraction."""
        from bs4 import BeautifulSoup

        # PRIMARY: web search with disambiguator
        if location_hint or True:  # always try web search first
            web_results = self.search_via_web(name, location_hint)
            if web_results:
                return web_results

        # FALLBACK 1: Baike's own search page (often JS-rendered, often 0 results)
        url = SEARCH_URL_FMT.format(query=quote(name))
        html = self.fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        candidates = []
        # Baike's search results page uses .result-title / .search-result-list
        # selectors. Different versions of Baike have used several layouts;
        # we try a few patterns.
        selectors = [
            "a.result-title",
            ".search-result-list a",
            "dl.search-list dd a",
            ".result-list a.title",
        ]
        for sel in selectors:
            for a in soup.select(sel):
                href = a.get("href", "")
                if not href:
                    continue
                if "/item/" not in href and not href.startswith("/item/"):
                    continue
                full = urljoin(BAIKE_BASE, href)
                title = a.get_text(strip=True)
                # snippet: try the parent or sibling description
                snippet = ""
                par = a.find_parent("dd") or a.find_parent("div") or a
                desc = par.find_next(class_=re.compile(r"abstract|desc|summary"))
                if desc:
                    snippet = desc.get_text(strip=True)[:300]
                candidates.append(BaikeCandidate(
                    name=title, url=full, snippet=snippet
                ))
            if candidates:
                break

        # Dedupe by URL
        seen = set()
        uniq = []
        for c in candidates:
            if c.url in seen:
                continue
            seen.add(c.url)
            uniq.append(c)

        # Fallback: if search-results page didn't yield candidates (commonly
        # because Baike's search page is JS-rendered), hit /item/<name>
        # directly. Baike redirects this URL to the "default" entry for
        # that name, which itself contains links to all polysemy variants
        # (other people with the same name) via /item/<name>/<digits>.
        if not uniq:
            direct_url = ENTRY_DIRECT_FMT.format(name=quote(name))
            try:
                direct_html = self.fetch(direct_url)
            except Exception as e:
                logger.warning(f"  fallback /item fetch failed for {name}: {e}")
                # Last resort: just return the direct URL itself
                uniq.append(BaikeCandidate(name=name, url=direct_url, snippet=""))
                return uniq

            # Always include the default entry as candidate #1
            uniq.append(BaikeCandidate(name=name, url=direct_url, snippet=""))

            # Extract polysemy candidates: /item/<name>/<digits>
            poly_re = re.compile(
                r'/item/' + re.escape(quote(name)) + r'/\d+'
            )
            soup_d = BeautifulSoup(direct_html, "html.parser")
            for a in soup_d.find_all("a", href=True):
                href = a["href"]
                if not poly_re.search(href):
                    continue
                full = urljoin(BAIKE_BASE, href.split("?")[0])
                if full in seen:
                    continue
                seen.add(full)
                # Disambig title: usually "吴剑（民建...）" — extract from title attr
                title_text = (a.get("title") or "").strip()
                if not title_text:
                    title_text = a.get_text(strip=True)
                uniq.append(BaikeCandidate(
                    name=title_text or name, url=full, snippet=""
                ))
            logger.info(f"  /item fallback for {name}: {len(uniq)} candidates "
                        f"(default + {len(uniq)-1} polysemy)")

        return uniq

    # -------------------------------------------------------------------
    def disambiguate(self,
                     candidates: list[BaikeCandidate],
                     known_birth: Optional[str] = None,
                     known_position: Optional[str] = None,
                     min_score: float = 1.0) -> Optional[BaikeCandidate]:
        """Score candidates by how well they match known facts.

        known_birth:    "YYYY-MM" string from 任前公示
        known_position: a position keyword (e.g., "副市长", "组织部部长")
        """
        if not candidates:
            return None

        for cand in candidates:
            score = 0.0
            matched = []

            # Fetch the candidate page snippet (first 3000 chars are enough)
            try:
                html = self.fetch(cand.url)
            except Exception as e:
                logger.warning(f"  skip {cand.url}: {e}")
                continue
            blob = (cand.snippet + " " + html[:5000]).lower()

            # Birth-date match: convert known_birth to "YYYY年M月" then look
            if known_birth and re.match(r"^\d{4}-\d{2}$", known_birth):
                yr, mo = known_birth.split("-")
                pat = f"{yr}年{int(mo)}月"
                if pat in blob:
                    score += 2.0
                    matched.append("birth")
                elif yr in blob:
                    score += 0.5

            # Position keyword: split into 2-char tokens and count overlaps
            if known_position:
                tokens = re.findall(r"[一-鿿]{2,}", known_position)
                hit = sum(1 for t in tokens if t in blob)
                if hit:
                    score += min(hit, 5) * 0.3
                    matched.append(f"pos:{hit}")

            cand.score = score
            cand.matched_fields = tuple(matched)

        candidates.sort(key=lambda c: c.score, reverse=True)
        best = candidates[0]
        if best.score >= min_score:
            logger.info(f"  → best match score {best.score:.2f}: {best.url}")
            return best
        # Show top scores for debugging
        logger.info(f"  no confident match (top scores: "
                    f"{[(c.score, c.url[-60:]) for c in candidates[:3]]})")
        return None

    # -------------------------------------------------------------------
    def fetch_entry(self, name: str,
                    known_birth: Optional[str] = None,
                    known_position: Optional[str] = None) -> Optional[tuple[str, str]]:
        """Find and fetch the best Baidu Baike entry for `name`.
        Returns (entry_url, raw_html) or None if no confident match."""
        cands = self.search(name)
        if not cands:
            return None
        best = self.disambiguate(cands, known_birth, known_position)
        if not best:
            logger.info(f"  no confident match for {name} (top score={cands[0].score:.2f})")
            return None
        html = self.fetch(best.url)
        return best.url, html


# -----------------------------------------------------------------------
# Mock fetcher for offline testing
# -----------------------------------------------------------------------
class MockBaikeFetcher(BaikeFetcher):
    """Offline test harness with hard-coded HTML."""

    NAME = "baike_mock"

    MOCK_SEARCH = """
    <html><body>
    <a class="result-title" href="/item/张三/12345">张三</a>
    <p>简介:中国共产党党员,1972年5月生</p>
    </body></html>
    """

    MOCK_ENTRY = """
    <html><body>
    <div class="lemma-summary">张三,男,汉族,1972年5月生,江苏宿迁人,1995年7月加入中国共产党,
    1994年7月参加工作,中央党校研究生学历。</div>

    <h2>人物经历</h2>
    <div class="para-content">
    <p>1994.07—1996.10  江苏省宿迁市XX乡 团委干事</p>
    <p>1996.10—1999.03  江苏省宿迁市XX乡 团委副书记</p>
    <p>1999.03—2002.05  江苏省宿迁市XX乡 党委副书记</p>
    <p>2002.05—2005.11  江苏省宿迁市XX区 区委办公室副主任</p>
    <p>2005.11—2009.02  江苏省宿迁市政府 办公室主任</p>
    <p>2009.02—2014.06  江苏省宿迁市委 副秘书长</p>
    <p>2014.06—2018.09  江苏省宿迁市某局 局长</p>
    <p>2018.09—2022.03  江苏省宿迁市某区 区长</p>
    <p>2022.03—至今    江苏省委组织部 副部长</p>
    </div>
    </body></html>
    """

    def fetch(self, url: str, force_refresh: bool = False) -> str:
        if "search" in url:
            return self.MOCK_SEARCH
        return self.MOCK_ENTRY
