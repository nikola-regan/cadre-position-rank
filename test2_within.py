"""
Test 2: Within-person fixed-effects.
Hypothesis: For the same person at 副部, moving to a higher-MVR-rank position
            increases probability that NEXT move is a promotion.
"""
import pandas as pd, numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS

panel = pd.read_pickle('panel.pkl').sort_values(['用户编码','经历序号'])

# Define spell-level outcome: immediate next-spell promotion
panel['next_level_num']  = panel.groupby('用户编码')['level_num'].shift(-1)
panel['next_position']   = panel.groupby('用户编码')['position'].shift(-1)
panel['next_promoted']   = (panel['next_level_num'] > panel['level_num']).astype('Int64')

# Restrict to active subsample (drop 退二线 systems)
panel['active'] = (~panel['基本大类别'].isin(['人大','政协','行业协会_人民团体'])).astype(int)

df = panel[(panel['level_num']==5) &
           (panel['mvr_mean_rank'].notna()) &
           (panel['next_level_num'].notna()) &
           (panel['active']==1) &
           (panel['age'].notna()) &
           (panel['tenure_at_level'].notna())].copy()

df['tenure_yrs'] = df['tenure_at_level']/12.0
df = df.dropna(subset=['mvr_rank_z','age','tenure_yrs','next_promoted']).reset_index(drop=True)

print(f"Total active 副部 spells with known next move: {len(df)}")
print(f"Unique people: {df['用户编码'].nunique()}")
print(f"Spell-level promotion rate: {df['next_promoted'].mean()*100:.1f}%")

# Distribution of spells per person
spell_per = df.groupby('用户编码').size()
print(f"\nSpells per person: mean={spell_per.mean():.1f}, median={spell_per.median():.0f}, max={spell_per.max()}")
print(f"  ≥2 副部 spells: {(spell_per>=2).sum()} people")
print(f"  ≥3 副部 spells: {(spell_per>=3).sum()} people")

# People with WITHIN-PERSON variation in outcome
multi = df[df.groupby('用户编码')['用户编码'].transform('size')>=2].copy()
varies = multi.groupby('用户编码')['next_promoted'].nunique()
people_with_var = varies[varies>1].index
print(f"\nPeople with ≥2 spells AND variation in outcome: {len(people_with_var)}")
print(f"Spells from these people: {multi[multi['用户编码'].isin(people_with_var)].shape[0]}")
print()

# --- Naive cross-sectional comparison (for reference) ---
print("=== A. Pooled (no FE) — for reference ===")
m_pool = smf.logit('next_promoted ~ mvr_rank_z + age + tenure_yrs',
                   data=df).fit(disp=0, cov_type='cluster',
                                cov_kwds={'groups': df['用户编码'].values})
b = m_pool.params['mvr_rank_z']; se = m_pool.bse['mvr_rank_z']
print(f"  β(MVR_z) = {b:+.4f}  SE={se:.4f}  z={b/se:+.2f}  p={2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")

# --- Linear Probability Model with person FE ---
print("\n=== B. Linear Probability Model + person fixed effects ===")
df_fe = df.set_index(['用户编码','经历序号'])
mod = PanelOLS.from_formula('next_promoted ~ mvr_rank_z + age + tenure_yrs + EntityEffects',
                             data=df_fe)
res = mod.fit(cov_type='clustered', cluster_entity=True)
print(f"  N obs: {res.nobs}, N entities: {df['用户编码'].nunique()}")
print(f"  β(MVR_z) = {res.params['mvr_rank_z']:+.4f}  SE = {res.std_errors['mvr_rank_z']:.4f}")
print(f"  t = {res.tstats['mvr_rank_z']:+.2f}  p = {res.pvalues['mvr_rank_z']:.4f}")
print(f"  Within R² = {res.rsquared_within:.4f}")

# --- Demeaned (manual within transformation) ---
print("\n=== C. Hand-rolled within transform — sanity check ===")
df['mvr_z_dev'] = df['mvr_rank_z'] - df.groupby('用户编码')['mvr_rank_z'].transform('mean')
df['age_dev'] = df['age'] - df.groupby('用户编码')['age'].transform('mean')
df['tenure_dev'] = df['tenure_yrs'] - df.groupby('用户编码')['tenure_yrs'].transform('mean')
df['out_dev'] = df['next_promoted'] - df.groupby('用户编码')['next_promoted'].transform('mean')

multi_only = df[df.groupby('用户编码')['用户编码'].transform('size')>=2].copy()
m = sm.OLS(multi_only['out_dev'], 
           sm.add_constant(multi_only[['mvr_z_dev','age_dev','tenure_dev']])
          ).fit(cov_type='cluster', cov_kwds={'groups': multi_only['用户编码'].values})
print(f"  N obs (multi-spell only): {len(multi_only)}, N entities: {multi_only['用户编码'].nunique()}")
print(f"  β(MVR_z within) = {m.params['mvr_z_dev']:+.4f}  SE={m.bse['mvr_z_dev']:.4f}")
print(f"  t = {m.params['mvr_z_dev']/m.bse['mvr_z_dev']:+.2f}  p = {m.pvalues['mvr_z_dev']:.4f}")

# --- Pair-level test: within-person SPELL with promotion vs without ---
print("\n=== D. Direct paired test — for each multi-spell person, ===")
print("=== compare MVR_z of promoted vs non-promoted spells ===")
multi_mixed = multi_only[multi_only['用户编码'].isin(people_with_var)]
person_diff = multi_mixed.groupby('用户编码').apply(
    lambda g: g.loc[g['next_promoted']==1, 'mvr_rank_z'].mean()
              - g.loc[g['next_promoted']==0, 'mvr_rank_z'].mean()
)
person_diff = person_diff.dropna()
print(f"  N people with both promoted & non-promoted 副部 spells: {len(person_diff)}")
print(f"  Mean (MVR_z promoted - MVR_z not promoted) per person: {person_diff.mean():+.4f}")
print(f"  Median: {person_diff.median():+.4f}")
from scipy.stats import wilcoxon, ttest_1samp
t, p = ttest_1samp(person_diff, 0)
print(f"  one-sample t-test against 0: t={t:+.2f}, p={p:.4f}")
w, p2 = wilcoxon(person_diff)
print(f"  Wilcoxon signed-rank: stat={w:.0f}, p={p2:.4f}")
print(f"  % of people where promoted spell had higher MVR_z: {100*(person_diff>0).mean():.1f}%")
