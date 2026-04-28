# 任前公示 Scraper

A modular pipeline for collecting Chinese cadre 任前公示 (pre-appointment public
notices) from provincial 组工网, parsing them into structured fields compatible
with CPED v1.0, and producing a CSV ready for analysis.

## Why this exists

CPED v1.0 covers the elite track (副厅 and above by way of having reached
副部+ at some point). The 副厅-正处 layer is observable but heavily selected.
任前公示 is the legally-mandated public-disclosure record for cadre
appointments at all levels above 处级; collecting it produces a representative
middle-cadre layer that complements CPED's elite layer.

See the OSF pre-registration document (parent directory) for the full
research-design rationale.

## Architecture

```
pipeline.py
    │
    ├── fetcher.py            # HTTP I/O: rate-limited, caching, retries
    │     ├── BaseFetcher      (abstract)
    │     ├── JiangsuFetcher   (concrete; example URL patterns)
    │     ├── GuangdongFetcher (stub — fill in selectors)
    │     └── MockFetcher      (offline test harness)
    │
    └── taiqian_parser.py     # Regex-based bio paragraph parser
          └── parse_bio() → CadreBio dataclass
```

The fetcher is one class per source (one province = one fetcher).
The parser is source-agnostic — give it any 任前公示 paragraph and it
returns the same `CadreBio` schema regardless of which province scraped it.

## Setup

```bash
pip install requests beautifulsoup4
# parser-only operation (no network) requires nothing else
```

## Quick demo (no network needed)

```bash
python pipeline.py --source mock --year 2024 --out demo.csv
```

This runs against a built-in 3-bio fixture and writes `demo.csv`.

## Real usage (from your machine, NOT a sandbox)

```bash
python pipeline.py --source jiangsu --year 2024 --out jiangsu_2024.csv
```

Behavior:
- Fetches index pages with 1-3 second random delays
- Caches every fetched page under `./cache/jiangsu/` so re-runs are fast
- Retries with exponential backoff on transient HTTP failures
- Writes one row per bio to `jiangsu_2024.csv`

Expected rough yield (rule of thumb, varies):
- ~200-1500 bios per province per year
- ~10-30 minutes per province per year for first crawl
- ~1 minute for re-runs (everything cached)

## Adding a new province

1. Subclass `BaseFetcher` in `fetcher.py`
2. Set `NAME` and `BASE_URL`
3. Implement three methods:
   - `list_index_urls(year) → list[str]`
   - `parse_index(html) → list[detail_urls]`
   - `parse_detail(html) → list[bio_paragraphs]`
4. Register in `pipeline.py` FETCHERS dict
5. Test by manually fetching one detail page and inspecting HTML to figure
   out the right CSS selectors

## Output schema

Compatible with CPED v1.0 personal-info table, plus provenance fields:

| Field | Type | Description |
|---|---|---|
| name | str | 姓名 |
| gender | str | 男/女 |
| ethnicity | str | 民族 |
| birth_date | str | YYYY-MM |
| native_province / native_city | str | 籍贯 |
| party_join_date | str | YYYY-MM |
| work_start_date | str | YYYY-MM |
| highest_degree | str | 博士/硕士/大学/研究生/etc |
| alma_mater | str | 毕业院校 (best-effort) |
| current_position | str | 现任职务 |
| proposed_position | str | 拟任职务 |
| source_url | str | 公示来源 URL |
| source_date | str | 公示年份 |
| raw_text | str | 原始简历段落 (for retroactive re-parsing) |
| parser_version | str | 用于兼容性追踪 |
| parse_warnings | str | 分号分隔的警告信号 |

## Quality control

After a crawl, inspect:
- `parse_warnings` column — flagged rows need manual review
- Birth-year distribution — implausible years suggest bad parsing
- `current_position` for very short or very long strings
- Sample 50 random rows and check against `raw_text`

Production rule: if >10% of rows have warnings, debug the parser before
trusting the data.

## Legal & ethical notes

- 任前公示 is **legally mandated public information** under 《党政领导干部
  选拔任用工作条例》. There is no reasonable expectation of privacy.
- Do not attempt to circumvent rate limits or anti-scraping measures.
- Identify your bot via a descriptive User-Agent (already configured).
- If a site has a `robots.txt`, respect it.
- For institutional research, retain raw HTML for at least the duration of
  the project for reproducibility.
- Do not redistribute identifiable bio data without consideration of the
  underlying officials' positions (mostly currently-serving or former
  officials, so privacy concerns are limited but non-zero).

## Linking back to CPED

Once you have a CSV from this pipeline:

1. Match `name + birth_date + native_province` against CPED basic-info table.
   Officials who appear in BOTH datasets validate that the parser produces
   consistent fields with CPED's coding.
2. For officials in CPED only: use as elite-track sample (existing analysis).
3. For officials in 任前公示 only: representative middle-cadre sample
   (the bias-correction angle for CPED v1.0).

## Roadmap

- [ ] v0.2 parser: handle compound titles, joint appointments, military background
- [ ] Add fetchers for 北京/上海/浙江/广东/山东/湖北/四川/河南
- [ ] LLM-based fallback parser for paragraphs that fail regex extraction
- [ ] Entity-resolution module for matching to CPED
- [ ] Tracking longitudinal changes (when same person appears in multiple
      公示 across years, reconstruct career path)
