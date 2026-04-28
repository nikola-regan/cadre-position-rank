"""
Sanity-test the Jiangsu fetcher and parser against ONE real public 任前公示 page.

Run this on your local machine (NOT in this sandbox — sandbox blocks gov.cn).

    python test_jiangsu_real.py

What it does:
    1. Fetches one specific Jiangsu 公示 detail page
    2. Saves the raw HTML to ./jiangsu_test_raw.html (for manual inspection)
    3. Runs JiangsuFetcher.parse_detail to extract bio paragraphs
    4. Runs taiqian_parser on each bio
    5. Prints structured fields for each
    6. Reports failures (empty parse, wrong field, etc.)

If extraction fails, open jiangsu_test_raw.html in a browser and look for
the actual HTML structure, then update JiangsuFetcher.parse_detail's
selectors or fallback heuristic in fetcher.py.
"""
from fetcher       import JiangsuFetcher
from taiqian_parser import parse_bio
from dataclasses    import asdict
from pathlib        import Path

# A specific 任前公示 detail page on 中共江苏省委新闻网.
# (Found via web search; verify the URL still exists before running.)
TEST_URL  = "https://www.zgjssw.gov.cn/fabuting/renmian/202504/t20250418_8477849.shtml"

# Alternative URLs to try if the above is broken — pick the first that works.
ALT_URLS = [
    # Format: provincial-level appointments. URL date in the path.
    "https://www.zgjssw.gov.cn/fabuting/renmian/202503/t20250328_8470000.shtml",
    "https://www.zgjssw.gov.cn/fabuting/renmian/",   # the index itself
]


def main():
    f = JiangsuFetcher(cache_dir="./cache_test", min_delay=0.5, max_delay=1.5)
    print(f"Fetching {TEST_URL} ...")
    try:
        result = f.fetch(TEST_URL)
    except Exception as e:
        print(f"!! Fetch failed: {e}")
        for url in ALT_URLS:
            print(f"   Trying alt: {url}")
            try:
                result = f.fetch(url)
                break
            except Exception as e2:
                print(f"   !! also failed: {e2}")
        else:
            print("All fetch attempts failed. Aborting.")
            return

    raw_path = Path("jiangsu_test_raw.html")
    raw_path.write_text(result.raw_html, encoding="utf-8")
    print(f"Raw HTML saved to {raw_path} ({len(result.raw_html)} chars)")

    # Try the parser
    bios = f.parse_detail(result.raw_html)
    print(f"\nExtracted {len(bios)} bio paragraph(s) from page")

    if not bios:
        print("\n!! No bios extracted. Likely causes:")
        print("   1. HTML structure differs from JiangsuFetcher.parse_detail's selectors")
        print("   2. Bio text is wrapped in a container we didn't anticipate")
        print("   3. Page is truly an index/list rather than detail")
        print("\nNext step: open jiangsu_test_raw.html in a browser, find a bio paragraph,")
        print("then update JiangsuFetcher.parse_detail() in fetcher.py with the right selector.")
        return

    for i, raw in enumerate(bios, 1):
        print(f"\n{'='*70}\nBio {i}/{len(bios)}\n{'='*70}")
        print(f"Raw text ({len(raw)} chars):")
        print(f"  {raw[:200]}{'...' if len(raw)>200 else ''}")

        parsed = parse_bio(raw, source_url=TEST_URL, source_date="2025-04")
        print("\nParsed fields:")
        for k, v in asdict(parsed).items():
            if k == "raw_text":
                continue
            if v not in (None, [], ""):
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
