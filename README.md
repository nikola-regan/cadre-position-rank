# Position Rank, Career Path, and Promotion in the Chinese Cadre System

A worker-flow approach to estimating the implicit hierarchy of the Chinese state.

This repository contains the code, processed-result tables, and pre-analysis plan for a research project that adapts the worker-flow ranking methodology of Huitfeldt, Kostøl, Nimczik, and Weber (2023) and the corporate-hierarchy framework of Ewens and Giroud (2025) to Chinese cadre career data. The full conceptual framework, hypotheses, and pre-registered confirmatory analyses are documented in [`OSF_PreRegistration_v1.pdf`](OSF_PreRegistration_v1.pdf) (also OSF-DOI: TBD).

## Summary of Findings

Using the Chinese Political Elite Database (CPED) v1.0 (Jiang 2018), we estimate position-level network ranks for 470 senior-government posts (2000–2015) and find:

1. **Algorithm-estimated rank correlates strongly with formal administrative rank** (Spearman ρ = 0.881), while revealing systematic deviations corresponding to known political mechanisms (stepping-stone positions; 退二线 termini).

2. **In active subsystems (党/政), network rank significantly predicts subsequent promotion** (β = +0.34, p < 0.001), robust to time-split out-of-sample tests and to a quasi-IV using predecessors' career outcomes.

3. **Early-career central-government exposure is a powerful, distinct predictor of reaching higher peak rank** (β = +1.47 on log-odds of reaching 正部+, larger than the effect of holding a graduate degree).

4. **Position effects, path effects, and person effects are statistically independent dimensions** of cadre advancement.

## Repository Structure

```
.
├── README.md                       # This file
├── requirements.txt                # Python dependencies
├── .gitignore                      # Excludes raw data and pickled outputs
├── OSF_PreRegistration_v1.pdf      # Pre-analysis plan (canonical)
├── OSF_PreRegistration_v1.md       # Markdown source
│
├── build_network.py                # Stage 1: build position transition network
├── build_panel.py                  # Stage 1: build person × spell panel
├── mvr_huitfeldt.py                # Stage 2: MVR-MCMC algorithm (core)
├── mvr_analyze.py                  # Stage 2: rank uncertainty + outlier identification
├── province_ilm.py                 # Robustness: provincial ILM comparison
│
├── test1_logit.py                  # RQ2 cross-sectional logit
├── test2_within.py                 # RQ2 within-person paired test
├── test3_timesplit.py              # RQ2 time-split out-of-sample
├── test4_spellorder.py             # RQ2 spell-order-controlled within-person
├── test5_predecessor.py            # RQ2 quasi-IV via predecessors' outcomes
├── test6_centrallocal.py           # RQ3 path effect + RQ4 mediation
│
├── *.png                           # Figures referenced in the pre-reg
└── *.csv                           # Aggregated result tables (no individual identifiers)
```

## Pipeline Order

The scripts must be run in roughly this order, as each stage produces pickled intermediate results consumed by later stages.

```
build_network.py  ──►  edges.pkl, pos_rank.pkl, records.pkl
       │
       ▼
mvr_huitfeldt.py  ──►  mvr_ranks.pkl
       │
       ├──►  mvr_analyze.py     (rank uncertainty plots)
       │
       └──►  build_panel.py     ──►  panel.pkl
                  │
                  ├──►  test1_logit.py        (cross-sectional)
                  ├──►  test2_within.py       (within-person)
                  ├──►  test3_timesplit.py    (out-of-sample)
                  ├──►  test4_spellorder.py   (spell-order control)
                  ├──►  test5_predecessor.py  (quasi-IV)
                  └──►  test6_centrallocal.py (path effect + mediation)

province_ilm.py  ──►  province_*.csv  (independent of mvr stage; uses senior_sample.pkl)
```

## Data Access

**The raw CPED v1.0 data is not included in this repository** and must be obtained directly from its maintainer:

- Junyan Jiang, Department of Government and Public Administration, The Chinese University of Hong Kong
- Project page: [www.junyanjiang.com/data.html](https://www.junyanjiang.com/data.html)
- Citation: Jiang, Junyan. 2018. "Making Bureaucracy Work: Patronage Networks, Performance Incentives, and Economic Development in China." *American Journal of Political Science* 62(4): 982–999.

Once granted access, place the two files in a sibling directory `CPED_V1.0/`:
- `Full Data.xlsx`
- `Location_and_Job_Codes.xlsx`

Adjust the data-path constants at the top of `build_network.py` and `build_panel.py` accordingly.

The aggregated CSV files in this repository (`positions_ranked.csv`, `mvr_positions_ranked.csv`, `province_shared_positions.csv`, etc.) contain only position-level summary statistics with no individual identifiers and may be redistributed under this repository's license.

## Replication

After obtaining CPED data and installing dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Stage 1: data preparation (~1 min)
python build_network.py
python build_panel.py

# Stage 2: hierarchy estimation (~1 min with Numba JIT)
python mvr_huitfeldt.py
python mvr_analyze.py

# Stage 3: empirical tests (each ~10–60 sec)
python test1_logit.py
python test2_within.py
python test3_timesplit.py
python test4_spellorder.py
python test5_predecessor.py
python test6_centrallocal.py

# Robustness
python province_ilm.py
```

All scripts print results to stdout and write figures (`.png`) and aggregated tables (`.csv`) into the working directory.

## Computational Requirements

- Python 3.10+
- 4 GB RAM is sufficient
- Total runtime end-to-end: under 5 minutes on a modern laptop (Numba JIT-compiled MCMC dominates; the actual MCMC takes <1 second per chain after compilation).

## Citation

If you build on this code or framework, please cite:

> Gen. 2026. "Position Rank, Career Path, and Promotion in the Chinese Cadre System: A Worker-Flow Approach." OSF Pre-Registration. DOI: TBD.

The methodological backbone:

> Huitfeldt, I., A. R. Kostøl, J. Nimczik, and A. Weber. 2023. "Internal Labor Markets: A Worker Flow Approach." *Journal of Econometrics* 233(2): 661–688.

> Ewens, M., and X. Giroud. 2025. "Corporate Hierarchy." *NBER Working Paper* 34162.

The data:

> Jiang, Junyan. 2018. "Making Bureaucracy Work: Patronage Networks, Performance Incentives, and Economic Development in China." *American Journal of Political Science* 62(4): 982–999.

## License

Code: MIT License (see `LICENSE`).

Pre-registration document: CC BY 4.0.

CPED data: governed by the data-use agreement set by its maintainer; not redistributed in this repository.

## Project Status

This is the **exploratory phase** of the project, time-stamped via OSF pre-registration. The confirmatory phase (extending to CPED v2.0+ and 任前公示 data) is in planning. See the pre-registration document for the analysis plan.

## Contact

Gen — nikolareganli@gmail.com
