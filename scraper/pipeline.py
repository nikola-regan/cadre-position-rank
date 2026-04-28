"""
End-to-end pipeline: fetch → parse → store.

Usage (from your local machine, not this sandbox):

    # Test with mock data — works anywhere
    python pipeline.py --source mock --year 2024 --out test.csv

    # Real run against a province's 组工网 (requires network access)
    python pipeline.py --source jiangsu --year 2024 --out jiangsu_2024.csv
"""
from __future__ import annotations
import argparse
import csv
import logging
from pathlib import Path
from dataclasses import asdict

from taiqian_parser import parse_bio
from fetcher       import JiangsuFetcher, GuangdongFetcher, MockFetcher

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

FETCHERS = {
    "mock":      MockFetcher,
    "jiangsu":   JiangsuFetcher,
    "guangdong": GuangdongFetcher,
}


def run(source: str, year: int, out_path: Path, cache_dir: Path) -> int:
    fetcher = FETCHERS[source](cache_dir=cache_dir)
    n_total = 0
    n_warned = 0

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = None
        for detail_url, bio_text in fetcher.crawl_year(year):
            bio = parse_bio(bio_text, source_url=detail_url,
                            source_date=str(year))
            row = asdict(bio)
            row["parse_warnings"] = ";".join(row["parse_warnings"])
            row["raw_text"] = (row["raw_text"] or "")[:500]
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                writer.writeheader()
            writer.writerow(row)
            n_total += 1
            if bio.parse_warnings:
                n_warned += 1
            if n_total % 100 == 0:
                log.info(f"  ...processed {n_total} bios")
    log.info(f"Done: {n_total} bios written to {out_path} "
             f"({n_warned} flagged with parse_warnings)")
    return n_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=list(FETCHERS),
                    help="Province / source name")
    ap.add_argument("--year",   type=int, required=True, help="Year to crawl")
    ap.add_argument("--out",    default="bios.csv", help="Output CSV path")
    ap.add_argument("--cache",  default="./cache",
                    help="Where to store fetched HTML (for re-runs)")
    args = ap.parse_args()
    run(args.source, args.year, Path(args.out), Path(args.cache))


if __name__ == "__main__":
    main()
