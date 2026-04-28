"""
Re-parse existing CSV files using the latest taiqian_parser version.

Reads `raw_text` from each row, runs parse_bio on it, writes a new CSV with
updated structured fields (overwriting the old ones).

Use this whenever you upgrade the parser — no need to refetch from network.

    python reparse.py jiangsu_all_years_combined.csv \\
        --out jiangsu_all_years_combined_v0.3.csv
"""
from __future__ import annotations
import argparse
import pandas as pd
from dataclasses import asdict
from pathlib import Path
from taiqian_parser import parse_bio

PARSED_FIELDS = [
    "name", "gender", "ethnicity", "birth_date",
    "native_province", "native_city",
    "party_join_date", "work_start_date",
    "highest_degree", "alma_mater",
    "current_position", "proposed_position",
    "current_city", "party_affiliation",   # v0.4 additions
    "parser_version", "parse_warnings",
]


def reparse_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Re-run parse_bio on the raw_text of every row."""
    out_rows = []
    for _, r in df.iterrows():
        raw = r.get("raw_text")
        if pd.isna(raw) or not str(raw).strip():
            # No raw text — keep original row, mark as not reparsed
            row = r.to_dict()
            row.setdefault("parse_warnings", "")
            wstr = str(row.get("parse_warnings") or "")
            row["parse_warnings"] = (wstr + ";reparse_skipped_no_raw").strip(";")
            out_rows.append(row)
            continue

        bio = parse_bio(
            str(raw),
            source_url=r.get("source_url"),
            source_date=r.get("source_date"),
        )
        bio_dict = asdict(bio)
        bio_dict["parse_warnings"] = ";".join(bio_dict["parse_warnings"])
        bio_dict["raw_text"] = (bio_dict["raw_text"] or "")[:500]

        # Preserve provenance columns from input that aren't in parser output
        merged = r.to_dict()
        for k in PARSED_FIELDS + ["raw_text"]:
            merged[k] = bio_dict.get(k)
        out_rows.append(merged)

    return pd.DataFrame(out_rows)


def coverage_report(df: pd.DataFrame, label: str = "") -> None:
    print(f"\n=== Field coverage{' — ' + label if label else ''} ===")
    n = len(df)
    for col in ["name", "gender", "ethnicity", "birth_date",
                "native_province", "highest_degree",
                "current_position", "proposed_position",
                "current_city", "party_affiliation"]:
        if col in df.columns:
            filled = df[col].notna().sum()
            print(f"  {col:20s}  {filled:4d}/{n}  ({100*filled/n:5.1f}%)")
    if "parse_warnings" in df.columns:
        n_warn = (df["parse_warnings"].fillna("").astype(str) != "").sum()
        print(f"  rows w/ any warning  {n_warn:4d}/{n}  ({100*n_warn/n:5.1f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv", help="Input CSV (with raw_text column)")
    ap.add_argument("--out", help="Output CSV (default: <input>_reparsed.csv)")
    args = ap.parse_args()

    in_path = Path(args.input_csv)
    out_path = Path(args.out) if args.out else in_path.with_name(
        in_path.stem + "_reparsed.csv"
    )

    df_in = pd.read_csv(in_path)
    print(f"Loaded {len(df_in)} rows from {in_path}")
    coverage_report(df_in, "BEFORE reparse")

    df_out = reparse_dataframe(df_in)
    coverage_report(df_out, "AFTER reparse")

    # Show what changed
    if "name" in df_in.columns and "name" in df_out.columns:
        gained_name = df_out["name"].notna().sum() - df_in["name"].notna().sum()
        print(f"\nNet change in 'name' coverage: {gained_name:+d} bios")

    df_out.to_csv(out_path, index=False)
    print(f"\nWrote {len(df_out)} rows to {out_path}")


if __name__ == "__main__":
    main()
