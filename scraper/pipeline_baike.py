"""
Baidu Baike pipeline: take a 任前公示 CSV (with name + birth_date +
current_position), look up each person on Baike, parse their full career
chronology, and write two output CSVs.

Usage:
    # Test mode — no network needed
    python pipeline_baike.py --input mock --out-prefix baike_test

    # Real run — requires running on YOUR machine, NOT the sandbox
    python pipeline_baike.py \\
        --input jiangsu_all_years_v0.3.csv \\
        --out-prefix baike_jiangsu

Outputs:
    {prefix}_persons.csv  — one row per person with match status + basic info
    {prefix}_careers.csv  — one row per career spell (long format)
"""
from __future__ import annotations
import argparse
import csv
import logging
import time
from pathlib import Path
from dataclasses import asdict
from typing import Optional

import pandas as pd

from baike_fetcher import BaikeFetcher, MockBaikeFetcher
from baike_parser  import parse_baike_entry

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


PERSONS_FIELDS = [
    "name", "gender", "ethnicity", "birth_date_baike",
    "native_place", "party_join_date", "work_start_date",
    "highest_degree", "alma_mater",
    # Provenance from input
    "input_birth_date", "input_current_position", "input_proposed_position",
    # Match status
    "match_status", "match_score", "matched_url",
    "n_career_spells", "parse_warnings",
]

CAREERS_FIELDS = [
    "person_name", "person_birth_date", "spell_idx",
    "start_date", "end_date", "organization", "position",
    "raw_line", "matched_url",
]


def process_one_person(fetcher,
                       row: dict) -> tuple[dict, list[dict]]:
    """Look up one person on Baike. Return (person_record, [career_rows])."""
    name      = row.get("name") or ""
    birth     = row.get("birth_date") or ""
    cur_pos   = row.get("current_position") or ""
    prop_pos  = row.get("proposed_position") or ""

    person_rec = {
        "name": name,
        "input_birth_date": birth,
        "input_current_position": cur_pos,
        "input_proposed_position": prop_pos,
        "match_status": "pending",
        "matched_url": "",
        "match_score": 0.0,
        "n_career_spells": 0,
        "parse_warnings": "",
    }

    if not name:
        person_rec["match_status"] = "skip_no_name"
        return person_rec, []

    # 1. Search — pass location hint extracted from current_position
    location_hint = fetcher.extract_location_hint(cur_pos) \
                    if hasattr(fetcher, "extract_location_hint") else None
    try:
        candidates = fetcher.search(name, location_hint=location_hint)
    except Exception as e:
        log.warning(f"  search failed for {name}: {e}")
        person_rec["match_status"] = "search_error"
        return person_rec, []
    if not candidates:
        person_rec["match_status"] = "not_found"
        return person_rec, []

    # 2. Disambiguate using known birth + position
    best = fetcher.disambiguate(candidates,
                                known_birth=birth,
                                known_position=cur_pos,
                                min_score=1.0)
    if not best:
        person_rec["match_status"] = "ambiguous"
        person_rec["match_score"] = candidates[0].score if candidates else 0.0
        return person_rec, []

    person_rec["matched_url"] = best.url
    person_rec["match_score"] = round(best.score, 3)

    # 3. Fetch full entry
    try:
        html = fetcher.fetch(best.url)
    except Exception as e:
        log.warning(f"  fetch entry failed for {name}: {e}")
        person_rec["match_status"] = "fetch_error"
        return person_rec, []

    # 4. Parse
    person = parse_baike_entry(html, source_url=best.url)

    # Verify birth-date consistency between input and Baike entry
    if (person.basic.birth_date and birth
            and person.basic.birth_date != birth):
        person_rec["match_status"] = "birth_mismatch"
        person_rec["parse_warnings"] = (
            f"input_birth={birth};baike_birth={person.basic.birth_date}"
        )
        return person_rec, []

    person_rec.update({
        "gender":           person.basic.gender,
        "ethnicity":        person.basic.ethnicity,
        "birth_date_baike": person.basic.birth_date,
        "native_place":     person.basic.native_place,
        "party_join_date":  person.basic.party_join_date,
        "work_start_date":  person.basic.work_start_date,
        "highest_degree":   person.basic.highest_degree,
        "alma_mater":       person.basic.alma_mater,
        "match_status":     "ok",
        "n_career_spells":  len(person.career),
        "parse_warnings":   ";".join(person.parse_warnings),
    })

    career_rows = []
    for spell in person.career:
        career_rows.append({
            "person_name":       name,
            "person_birth_date": birth,
            "spell_idx":         spell.spell_idx,
            "start_date":        spell.start_date,
            "end_date":          spell.end_date,
            "organization":      spell.organization,
            "position":          spell.position,
            "raw_line":          spell.raw_line,
            "matched_url":       best.url,
        })
    return person_rec, career_rows


def run(input_csv: str, out_prefix: str, fetcher,
        max_persons: Optional[int] = None) -> None:
    if input_csv == "mock":
        df = pd.DataFrame([{
            "name": "张三", "birth_date": "1972-05",
            "current_position": "江苏省委组织部副部长",
            "proposed_position": "江苏省委组织部部长",
        }])
    else:
        df = pd.read_csv(input_csv)
    if max_persons:
        df = df.head(max_persons)
    log.info(f"Processing {len(df)} persons")

    persons_csv = Path(f"{out_prefix}_persons.csv")
    careers_csv = Path(f"{out_prefix}_careers.csv")

    p_writer = c_writer = None
    pf = persons_csv.open("w", encoding="utf-8", newline="")
    cf = careers_csv.open("w", encoding="utf-8", newline="")
    p_writer = csv.DictWriter(pf, fieldnames=PERSONS_FIELDS)
    c_writer = csv.DictWriter(cf, fieldnames=CAREERS_FIELDS)
    p_writer.writeheader()
    c_writer.writeheader()

    counts = {"ok":0, "not_found":0, "ambiguous":0, "birth_mismatch":0,
              "search_error":0, "fetch_error":0, "skip_no_name":0}

    for i, row in df.iterrows():
        person_rec, career_rows = process_one_person(fetcher, row.to_dict())
        # Pad missing fields
        for k in PERSONS_FIELDS:
            person_rec.setdefault(k, "")
        p_writer.writerow(person_rec)
        for cr in career_rows:
            for k in CAREERS_FIELDS:
                cr.setdefault(k, "")
            c_writer.writerow(cr)
        counts[person_rec["match_status"]] = counts.get(person_rec["match_status"],0)+1

        if (i+1) % 25 == 0:
            log.info(f"  ...processed {i+1}/{len(df)} (ok={counts['ok']})")

    pf.close()
    cf.close()
    log.info("Done.")
    log.info(f"  Match outcomes: {counts}")
    log.info(f"  → {persons_csv}, {careers_csv}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="Input CSV (任前公示 with name+birth) or 'mock'")
    ap.add_argument("--out-prefix", default="baike_out",
                    help="Output prefix (will create {prefix}_persons.csv and "
                         "{prefix}_careers.csv)")
    ap.add_argument("--cache",   default="./cache",
                    help="HTML cache directory")
    ap.add_argument("--mock", action="store_true",
                    help="Use offline mock fetcher (no network)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Max # of persons to process (for testing)")
    args = ap.parse_args()

    fetcher = (MockBaikeFetcher if args.mock or args.input == "mock"
               else BaikeFetcher)(cache_dir=args.cache)
    run(args.input, args.out_prefix, fetcher, max_persons=args.limit)


if __name__ == "__main__":
    main()
