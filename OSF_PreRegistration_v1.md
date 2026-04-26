# Pre-Analysis Plan: Position Rank, Career Path, and Promotion in the Chinese Cadre System — A Worker-Flow Approach

**Status**: Draft v1.0 — to be posted on OSF for time-stamping.
**Date**: April 2026
**Author**: Gen (nikolareganli@gmail.com)
**Coauthors**: TBD

---

## Note on the Nature of This Document

This pre-analysis plan describes a research project at two stages:
- **Exploratory phase (completed on CPED v1.0, April 2026)**: hypothesis-generating analyses on existing data, documented here for transparency.
- **Confirmatory phase (planned)**: pre-registered analyses to be conducted on extended data (CPED-equivalent updated to 2024+, supplemented by 任前公示 / 地方年鉴 data) to test the hypotheses generated in the exploratory phase.

The primary purpose of this document is to time-stamp the conceptual framework, methodology, and preliminary findings, and to specify in advance the confirmatory tests so that they cannot be subject to specification search.

---

## Abstract

Chinese cadre promotion has been studied extensively along two dimensions: individual-level characteristics (education, age, faction, performance) and formal administrative rank. We propose a third, hitherto-unmeasured dimension: **the implicit "real" rank of a position within the bureaucracy's flow network, independent of its formal classification**. Adapting the worker-flow ranking method of Huitfeldt, Kostøl, Nimczik, and Weber (2023) and the corporate-hierarchy framework of Ewens and Giroud (2025), we estimate position-level network ranks for Chinese government posts using cadre career-transition data from CPED v1.0 (Jiang 2018). We document four findings: (1) the algorithm-estimated rank correlates strongly with formal administrative rank but reveals systematic deviations corresponding to known political mechanisms (stepping-stone positions, 退二线 mechanism); (2) within active subsystems, network rank significantly predicts subsequent formal promotion; (3) early-career central-government exposure is a powerful, distinct predictor of reaching higher peak rank; (4) position effects, path effects, and person effects are statistically independent dimensions of promotion determinants.

---

## 1. Background and Motivation

### 1.1 Theoretical motivation

Models of corporate hierarchy (Garicano 2000; Caliendo, Monte, and Rossi-Hansberg 2015; Bolton and Dewatripont 1994) treat firms as networks of differentiated positions linked by flows of workers, information, and authority. The Chinese cadre system — comprising over 7 million civil servants spread across multiple administrative levels and functional systems — represents perhaps the world's largest single bureaucratic hierarchy. Yet its hierarchical structure has typically been studied through the lens of formal administrative rank (副国/正部/副部/正厅/...), not through its implicit network structure.

The formal administrative rank classification is a **legal / institutional** label. Within any given formal rank, however, positions vary substantially in:
- their actual political authority (e.g., 中办副秘书长 vs 某部副部长);
- their function in promotion pathways (stepping stone vs terminus);
- their selection of incumbents (fast-track vs ordinary).

Existing literature has noted these distinctions qualitatively but has not provided a systematic, replicable, data-driven measure that distinguishes "real" position rank from "formal" position rank.

### 1.2 Methodological gap

Recent advances in econometrics (Huitfeldt et al. 2023; De Bacco, Larremore, Moore 2018; Ewens and Giroud 2025) provide tools for estimating implicit hierarchy from observed worker flows. The core idea: if many workers move from position A to position B but few move from B to A, then B is "above" A in the implicit hierarchy. Statistical estimation provides not only point estimates of rank but also uncertainty.

These methods have been applied to Norwegian private-sector firms (Huitfeldt et al.) and U.S. public companies (Ewens-Giroud). **They have not been applied to any government, despite the fact that the data structure (cadre career histories) is well-suited and the substantive importance of the resulting hierarchy estimates is high.**

### 1.3 Substantive motivation

Three practical implications motivate measuring implicit position rank in the Chinese state:

1. **Selection vs. treatment**: When organizations promote a cadre, are they responding to the cadre's individual ability, the cadre's network connections, or the cadre's *current position*? Existing literature has examined the first two; quantifying the third has been impossible without a valid measure of position quality.

2. **Diagnostics for institutional reform**: If the implicit rank of certain positions diverges sharply from their formal rank, this signals either an outdated formal classification or an emergent informal hierarchy. Either has implications for organizational design and anti-corruption supervision.

3. **Career-path strategy**: For the cadre system to function as a meritocratic tournament, the *route* through positions must matter, not just the *speed*. Measuring the network rank of intermediate positions allows direct quantification of which routes lead where.

---

## 2. Existing Literature

The closest relatives of this project, against which we position our novelty:

**Career-path empirics on Chinese officials.**
- Li, Liu, and Yao (2025, JEBO) document negative correlation in job durations across formal levels, interpreted as a merit-vs-seniority tradeoff. They use career sequences but not network estimation; their unit of analysis is duration at level, not position rank within level. **Distinct from this project.**
- Landry, Lü, and Duan (2018, CPS) examine performance-based selection along the administrative ladder. Use individual-level regressions, not network methods.
- The 2025 meta-analysis by Yu et al. synthesizes 67 empirical studies on performance-promotion linkages. None apply worker-flow ranking.

**Network analyses of Chinese officials.**
- Shih, Adolph, and Liu (2012, APSR): factional connection networks among Central Committee members.
- Jiang (2018, AJPS): patronage networks in provincial leadership.
- Keller (2016): CCP elite networks.
- *All of these analyze person-to-person tie networks. None analyze position-to-position flow networks. Distinct from this project.*

**Worker-flow ranking methodology.**
- Huitfeldt, Kostøl, Nimczik, and Weber (2023, JoE): minimum-violation-ranking with bootstrap uncertainty for Norwegian private firms.
- Ewens and Giroud (2025, NBER w34162): hierarchy estimation in U.S. public companies. Documents that organizational layers respond to demand and knowledge shocks.
- *Neither has been applied to any government sector. This project is the first such application.*

**Central-local mobility / "central exposure" effects.**
- Cheng Li (various) and Bo Zhiyue: qualitative discussion of the importance of central-government tenure in elite advancement.
- Joo (2010, Asian Survey) and others: descriptive central-local circulation patterns.
- *No prior study has provided a continuous, dose-response estimate of central-exposure effect on peak career rank, controlling for education and cohort. This project provides one.*

In summary: the substantive question (career advancement in the Chinese state) is well studied; the methodological approach (network-based position-rank estimation) is well established in private-sector applications; but the intersection — applying worker-flow methods to Chinese cadre data and using the resulting position-rank measure to decompose promotion effects — is novel.

---

## 3. Research Questions and Hypotheses

The project addresses four research questions, organized into a sequential framework:

**RQ1 (Measurement)**: Can worker-flow ranking applied to Chinese cadre transition data produce a position-rank measure that (a) correlates with formal administrative rank and (b) reveals theoretically meaningful within-rank heterogeneity?

> H1: The estimated network rank (MVR mean) and the formal administrative rank exhibit Spearman ρ ≥ 0.7 across positions.
> H2: Positions identified by political-science literature as "stepping stones" (e.g., 共青团委书记, 国办副秘书长) and "退二线" termini (e.g., 政协副主席, 总工会主席) systematically deviate from their formal-rank-implied position in the predicted directions.

**RQ2 (Position effect on promotion)**: Does the network rank of a cadre's current position predict their probability of subsequent formal promotion, controlling for individual characteristics?

> H3: For 副部 cadres in active subsystems (党/政), a one-standard-deviation increase in the network rank z-score (within 副部) is associated with a positive log-odds shift in the probability of subsequent promotion to 正部+, with effect size β ≥ +0.15 and p < 0.01.
> H4: This effect is null or reversed in 退二线 subsystems (人大/政协).
> H5: The effect persists in time-split out-of-sample tests (training MVR on data through year T, testing on cohorts beginning after year T).
> H6: The position-quality effect is independently identifiable through a quasi-IV using predecessors' career outcomes; both predecessor-outcome dummies and MVR rank z-score retain significance in horse-race regressions.

**RQ3 (Path effect on peak rank)**: Conditional on reaching at least 副厅 (the threshold for entering CPED's elite track), does the cadre's *path* into senior ranks — specifically, the fraction of pre-副厅 years spent at central government organizations — predict reaching peak ranks?

> H7: Among cadres reaching 副厅+, a higher fraction of pre-副厅 years at central organizations predicts a positive log-odds shift in the probability of reaching 正部+, with effect size β ≥ +0.5 and p < 0.001.
> H8: The path effect is independent of the position effect (Stage-1 mediation: path → MVR exposure is null or weak; Stage-2: both path and MVR exposure remain significant in joint regression).

**RQ4 (Three-dimensional decomposition)**: How do position rank, career path, and individual characteristics jointly determine promotion, and which dimensions are independent?

> H9: Position rank, central-exposure, and education each retain significant predictive power on reaching 正部+ in a joint regression; no single variable subsumes the others.

---

## 4. Data

### 4.1 Primary data source

**Chinese Political Elite Database (CPED)** version 1.0, maintained by Junyan Jiang (Jiang 2018). The database contains structured biographical and career-history data for 4,057 Chinese political elites covering:
- All standing committee members (政治局常委) 2000-2012;
- All provincial party secretaries and governors 1995-2015;
- All city-level party secretaries and mayors 2000-2015;
- All Central Committee members (full and alternate) 1997-2012.

Each individual is associated with a long-format career table containing 62,742 spell records, each marked with start/end dates, institutional affiliation, position title, region, and standardized formal administrative rank.

### 4.2 Sample

- **Time window**: career spells starting in or after January 2000.
- **Population for hierarchy estimation**: officials who, during the observation period, reached at least 副部级 (level ≥ 5). Their full pre-2000-onwards career data within this period contributes to the network. Sample size (exploratory phase): 1,833 individuals, 10,332 spells.
- **Population for path analysis (RQ3)**: officials who reached at least 副厅 (level ≥ 3) and have ≥ 3 years of observable pre-副厅 career history. Sample size: 3,035 individuals.
- **Active subsample**: spells in 党委 / 政府_国务院 / 共青团 / 学校 / 中央企业 systems. Excluded: 人大 / 政协 / 行业协会_人民团体 (退二线 endpoints).

### 4.3 Position node construction

Each unique combination of `(admin level, basic system category, first-level position keyword, normalized specific title)` is treated as one node in the position network. Admin level is one of {中央, 省级, 副省级市, 地级市, 其他}, derived from `是否全国性组织` and `地区级别`. Title normalization removes trailing concurrent-position indicators (e.g., "副省长、党组成员" → "副省长") and merges acting/full equivalents (e.g., "代市长" → "市长").

In the exploratory phase: 470 position nodes after filtering for ≥ 3 occurrences each. This filter is documented as a hyperparameter; in the confirmatory phase the filter level will be pre-set or varied as a robustness exercise.

### 4.4 Confirmatory phase data extensions

For pre-registered confirmatory tests, the following extensions are planned:
- CPED v2.0 (or equivalent extension) updating the temporal window through 2023+.
- 任前公示 scraped data adding a representative middle-cadre layer (2018+ availability).
- 地方年鉴 for ground-truth on positions held in years not currently covered.

---

## 5. Methods

### 5.1 Position-rank estimation algorithm

We implement the minimum-violation-ranking (MVR) estimator of Huitfeldt, Kostøl, Nimczik, and Weber (2023):

**Step 1**: Construct a directed, weighted adjacency matrix W where W[i,j] = number of observed transitions from position i to position j.

**Step 2**: Define the violation count for permutation σ as
V(σ) = Σ_{i,j} W[i,j] · I[σ(i) > σ(j)]
which counts the total weight of edges going "down" against the rank ordering.

**Step 3**: Sample low-violation rankings via a zero-temperature Markov chain Monte Carlo of adjacent-position swaps. For an adjacent swap of nodes (a, b) at positions (p, p+1):
ΔV = W[a,b] − W[b,a]
Swap if ΔV < 0; if ΔV = 0, swap with probability 0.5; otherwise reject.

**Step 4**: Run K independent chains (K=4 in exploratory phase) of 10⁶ iterations each, with 2×10⁵ burn-in. Pool the final 200 samples per chain. For each position, compute mean rank (MVR_mean) and standard deviation (MVR_std) across pooled samples.

**Step 5**: Cluster MVR_mean into K layers via k-means, where K is determined by the rank-uncertainty heuristic K = ceil(rank_range / (2 × median MVR_std)).

**Robustness**: The algorithm warm-starts from a SpringRank ordering (De Bacco et al. 2018). All results to be reported with both warm and random initializations.

### 5.2 Specification for promotion regression (RQ2)

For each spell s with `level_num = 5` (副部) starting before December 31 of year T (typically T=2010, allowing ≥ 5-year follow-up):

logit P(reach_zhengbu_within_5yrs = 1) = β · MVR_z(spell_position) + γ · X_individual + δ · X_spell + ε

where:
- MVR_z is the position's network rank z-score within formal level
- X_individual: age at spell start, prior tenure at level 5, education indicators
- X_spell: system fixed effects (党 / 政 / 学校 / etc.), administrative-level fixed effects, year-of-spell-start fixed effects
- Standard errors clustered at the individual level

Heterogeneity: the same regression run separately for active subsample (excluding 人大/政协) vs full sample. H3 is tested on the active subsample.

### 5.3 Within-person identification (RQ2)

Three within-person specifications:
- **Linear probability with person FE**: identifies pure within-person effect.
- **Direct paired comparison**: among officials with ≥ 1 promoted spell and ≥ 1 non-promoted spell at 副部, compare MVR_z of "promoted spell" vs "non-promoted spell" via paired t-test and Wilcoxon signed-rank test.
- **Spell-order-controlled paired test**: regress per-person Δ_MVR_z (promoted minus non-promoted) on per-person Δ_spell_index. The intercept of this regression measures the residual MVR effect after netting out mechanical time trend in spell-index progression.

### 5.4 Quasi-IV using predecessors' outcomes (RQ2)

For each spell s = (incumbent, position P, start_dt):
- Identify the most recent prior holder of P whose end_dt < s.start_dt and ID ≠ incumbent's ID.
- Classify predecessor's next-spell outcome:
  - `up`: next spell at higher formal level
  - `lateral`: next spell at same formal level (but not 退二线)
  - `tuierxian`: next spell in 人大/政协/工会
  - `down`: next spell at lower formal level
  - `retired`: no next spell, age at spell-end ≥ 60
  - `unknown`: insufficient data

- Reduced-form: regress incumbent's promotion outcome on predecessor-outcome dummies (baseline = lateral) plus controls.
- Horse-race: include both MVR_z and predecessor-outcome dummies; both should retain significance if they capture distinct dimensions of position quality.

### 5.5 Time-split robustness (RQ2)

To rule out look-ahead bias:
- Re-estimate MVR using only spells starting in year ≤ T_split (T_split=2008 in exploratory phase).
- Use this "frozen" MVR rank to predict outcomes in spells starting > T_split, restricting to those with ≥ 5 years of follow-up (start year ≤ 2010).

### 5.6 Path-effect specification (RQ3)

For each official i in the path-analysis sample:
- Compute pre_fuet_central_frac_i = Σ(spell durations × is_central) / Σ(spell durations) over spells with formal level < 3 (i.e., before reaching 副厅).
- Let `is_central` be 1 if `是否全国性组织 == 是`.

logit P(reach_zhengbu = 1) = β · pre_fuet_central_frac + γ · X_individual + δ · cohort + ε

where cohort fixed effects absorb year-specific right-censoring, and X_individual includes education and age.

### 5.7 Mediation through position-rank exposure

Stage-1 (linear): MVR_z_avg_post_fuet = α_1 · pre_fuet_central_frac + γ_1 · controls + u_1
Stage-2 (logit): logit P(reach_zhengbu) = β_d · pre_fuet_central_frac + β_m · MVR_z_avg_post_fuet + γ_2 · controls + u_2

Mediation share = (β_total − β_direct) / β_total, where β_total is the central-exposure coefficient without the mediator and β_direct is its coefficient when MVR_z_avg is included.

---

## 6. Pre-Specified Inference Criteria

Significance threshold: **p < 0.05** for primary tests, **p < 0.01** for confirmatory tests where multiple comparisons exist (Bonferroni correction across the four RQs).

Effect-size criteria:
- H1 succeeds if Spearman ρ ≥ 0.7.
- H3 succeeds if β ≥ +0.15 and p < 0.01.
- H7 succeeds if β ≥ +0.5 and p < 0.001.

Negative results are also reportable: if H4 (no effect in 退二线 subsample) is contradicted, this would suggest the algorithm has not properly disentangled active vs inactive subsystems.

---

## 7. Exploratory-Phase Findings (CPED v1.0, completed April 2026)

The following analyses have been completed on CPED v1.0 and are documented for transparency. They are **not** confirmatory; they generated the pre-registered hypotheses above.

| RQ | Test | Estimate | Inference |
|---|---|---|---|
| RQ1 | MVR mean rank vs formal level (Spearman ρ) | 0.881 | Strong validation |
| RQ1 | MVR rank deviation identifies 团派 stepping stones | qualitative | Confirmed |
| RQ1 | MVR rank deviation identifies 退二线 termini | qualitative | Confirmed |
| RQ2 | β(MVR_z) on reach_zhengbu (active sample, full controls) | +0.335 (p < 0.001) | H3 directionally supported |
| RQ2 | β(MVR_z) on reach_zhengbu (退二线 sample) | reversed/null | H4 supported |
| RQ2 | β(MVR_z), time-split out-of-sample (T_split=2008) | +0.95 (p ≈ 0.06) | H5 directionally supported |
| RQ2 | Reduced-form: predecessor `up` predicts incumbent promotion (active sample) | β = +0.42 (p = 0.003) | H6 supported |
| RQ2 | Horse race: MVR_z and pred_up both significant | yes | H6 supported |
| RQ2 | Within-person paired test (副部) | +0.34σ shift, p < 1e-7 | H3 (within-person) supported |
| RQ2 | Within-person, controlling spell order | +0.27σ residual, p = 0.065 | Marginally supported |
| RQ3 | β(pre_fuet_central_frac) on reach_zhengbu | +1.47 (p < 0.001) | H7 strongly supported |
| RQ3 | Heterogeneity by 学历: similar β across 本科/硕士/博士 | yes | Robust |
| RQ3 | Mediation via MVR exposure | < 1% of total effect | H8 supported (path is direct) |
| RQ4 | Path, position, person all retain significance jointly | yes | H9 supported |

---

## 8. Confirmatory-Phase Plan

Confirmatory replication of the above findings on extended data:

**C1 (priority)**: Replicate the position-rank estimation on CPED v2.0+ (when available) or equivalent extended dataset. Confirm the same set of stepping-stone and 退二线 positions emerge.

**C2**: Test H3-H6 on cohorts not in CPED v1.0 (officials reaching 副部 in 2016-2023). Use full follow-up (≥ 5 years) for outcome.

**C3**: Test H7-H8 on the CPED v2.0+ sample with ≥ 5 years follow-up.

**C4**: Robustness across alternative position-node aggregations: test sensitivity to (a) including/excluding admin-level dimension, (b) merging title categories, (c) different filter thresholds for minimum spell count.

**C5**: External validation: select 5-10 positions identified by the algorithm as having unusual MVR rank (vs formal); cross-check with qualitative political science literature whether these are recognized as anomalous.

---

## 9. Limitations and Caveats

The exploratory-phase findings are subject to the following caveats, which the confirmatory phase aims to address where possible:

1. **Selection on outcomes**: CPED v1.0 sample is conditional on reaching 副部 (or city party secretary) at some point. Therefore "选 ↑ ratings" of 副厅- positions reflect early careers of future seniors, not representative middle-cadre experience.

2. **Right-censoring**: CPED v1.0 ends in 2015. Cohorts starting their 副部 spells in 2010+ have insufficient follow-up time. This biases promotion rates downward for late cohorts.

3. **Within-person identification confound**: The strong correlation between spell-order-within-级别 and promotion makes within-person fixed-effect identification difficult. The pure position effect, after netting time trend, is +0.27σ with p = 0.065 — marginally significant but not definitive.

4. **Mediation mechanism**: The central-exposure effect on reaching 正部+ does not work through MVR-rank exposure. The mechanism (political capital, network ties, decision experience, etc.) remains unidentified.

5. **Predecessor-IV exclusion concern**: If predecessors and incumbents share factional ties or there is mentorship spillover, the predecessor-outcome variable is not strictly exogenous. The horse-race specification suggests the effect is not entirely absorbed by MVR rank, but stronger identification (e.g., far-gap subsamples) is reserved for the confirmatory phase.

6. **External validity**: Findings are conditional on the CPED-defined elite track. Generalization to the full Chinese cadre population requires representative middle-cadre data (planned via 任前公示 scraping in extension).

---

## 10. Timeline

- **April 2026**: this document posted to OSF, time-stamped.
- **April-June 2026**: Working paper draft prepared, posted to SSRN.
- **2026 Q3**: 任前公示 data collection begins. CPED v2.0 / equivalent investigated.
- **2026 Q4 - 2027**: Confirmatory analyses on extended data.
- **2027**: Manuscript submission.

---

## 11. Data and Code Availability

All exploratory-phase code (Python, ~1500 LOC) and processed data outputs are committed to a private GitHub repository (URL TBD when made public) and time-stamped via this OSF post. Raw CPED data is governed by Junyan Jiang's data-use agreement and is not redistributed.

---

## 12. References

(Selected; full list to follow in working paper)

- Bolton, P., and M. Dewatripont. 1994. "The Firm as a Communication Network." *QJE* 109(4): 809-839.
- Caliendo, L., F. Monte, and E. Rossi-Hansberg. 2015. "The Anatomy of French Production Hierarchies." *JPE* 123(4): 809-852.
- De Bacco, C., D. B. Larremore, and C. Moore. 2018. "A Physical Model for Efficient Ranking in Networks." *Science Advances* 4(7).
- Ewens, M., and X. Giroud. 2025. "Corporate Hierarchy." *NBER Working Paper* 34162.
- Garicano, L. 2000. "Hierarchies and the Organization of Knowledge in Production." *JPE* 108(5): 874-904.
- Huitfeldt, I., A. R. Kostøl, J. Nimczik, and A. Weber. 2023. "Internal Labor Markets: A Worker Flow Approach." *Journal of Econometrics* 233(2): 661-688.
- Jiang, J. 2018. "Making Bureaucracy Work: Patronage Networks, Performance Incentives, and Economic Development in China." *AJPS* 62(4): 982-999.
- Landry, P. F., X. Lü, and H. Duan. 2018. "Does Performance Matter? Evaluating Political Selection Along the Chinese Administrative Ladder." *Comparative Political Studies* 51(8): 1074-1105.
- Li, J., Z. Liu, and Y. Yao. 2025. "Career Paths in Hierarchies: Theory and Evidence from Chinese Officials." *Journal of Economic Behavior & Organization* 233.
- Pedings, K., and A. Langville. 2012. "A Minimum Violations Ranking Method." *Optimization and Engineering* 13(2): 349-370.
- Shih, V., C. Adolph, and M. Liu. 2012. "Getting Ahead in the Communist Party." *APSR* 106(1): 166-187.
- 周黎安. 2007. "中国地方官员的晋升锦标赛模式研究." *经济研究* 7: 36-50.

---

*This document is the foundational time-stamp for the project. Subsequent revisions and the full working paper will reference back to this version.*
