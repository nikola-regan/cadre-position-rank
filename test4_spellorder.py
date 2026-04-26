"""
(b) Within-person test controlling for spell order.

Concern: Maybe organizations naturally place people in higher-MVR positions over time
        AND naturally promote people who have spent more time at level. If both
        trends exist mechanically, then 'promoted spell tends to be higher MVR'
        could be just a time trend.

Test: Add spell_order_in_副部 (1st, 2nd, 3rd 副部 spell) as a control in the
      within-person comparison. If MVR_z effect SURVIVES controlling for spell
      order, the time-trend confound is ruled out.
"""
import pandas as pd, numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import wilcoxon, ttest_1samp, ttest_rel

panel = pd.read_pickle('panel.pkl').sort_values(['用户编码','经历序号'])
panel['next_level_num'] = panel.groupby('用户编码')['level_num'].shift(-1)
panel['next_promoted']  = (panel['next_level_num'] > panel['level_num']).astype('Int64')
panel['active'] = (~panel['基本大类别'].isin(['人大','政协','行业协会_人民团体'])).astype(int)

# Spell order within person × formal level
panel['spell_idx_at_level'] = panel.groupby(['用户编码','level_num']).cumcount() + 1

df = panel[(panel['level_num']==5) & (panel['mvr_mean_rank'].notna()) &
           (panel['next_level_num'].notna()) & (panel['active']==1) &
           (panel['age'].notna()) & (panel['tenure_at_level'].notna())].copy()
df['tenure_yrs'] = df['tenure_at_level']/12.0
df = df.dropna(subset=['mvr_rank_z','next_promoted']).reset_index(drop=True)

print(f"=== Spell-order distribution among 副部 spells ===")
print(df['spell_idx_at_level'].describe().round(2))
print()
print(df['spell_idx_at_level'].value_counts().sort_index().head(10))
print()

# Mixed-outcome subset (the only group contributing to within-person identification)
mixed = df.groupby('用户编码')['next_promoted'].nunique()
mixed_uids = mixed[mixed>1].index
m = df[df['用户编码'].isin(mixed_uids)].copy()
print(f"Mixed-outcome people: {len(mixed_uids)}, total spells: {len(m)}\n")

# --- Q1: Does spell order alone predict promotion within person? ---
print("=== Q1: Sanity — does spell_idx alone predict next_promoted (within person)? ===")
m['mvr_z_dev']  = m['mvr_rank_z']      - m.groupby('用户编码')['mvr_rank_z'].transform('mean')
m['idx_dev']    = m['spell_idx_at_level']- m.groupby('用户编码')['spell_idx_at_level'].transform('mean')
m['ten_dev']    = m['tenure_yrs']      - m.groupby('用户编码')['tenure_yrs'].transform('mean')
m['age_dev']    = m['age']             - m.groupby('用户编码')['age'].transform('mean')
m['out_dev']    = m['next_promoted']   - m.groupby('用户编码')['next_promoted'].transform('mean')

# Within: out_dev ~ idx_dev only
mod = sm.OLS(m['out_dev'], sm.add_constant(m[['idx_dev']])).fit(
    cov_type='cluster', cov_kwds={'groups': m['用户编码'].values})
b, se = mod.params['idx_dev'], mod.bse['idx_dev']
print(f"  spell_idx alone:    β = {b:+.4f}  SE = {se:.4f}  p = {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")
print(f"  → 1 step later in 副部 career → +{100*b:.2f}pp promotion probability")
print()

# --- Q2: Joint within-person regression: MVR_z + spell_idx ---
print("=== Q2: Joint within-person: out_dev ~ mvr_z_dev + idx_dev + tenure + age ===")
mod = sm.OLS(m['out_dev'], sm.add_constant(m[['mvr_z_dev','idx_dev','ten_dev','age_dev']])).fit(
    cov_type='cluster', cov_kwds={'groups': m['用户编码'].values})
print(mod.summary().tables[1])
print()

# --- Q3: Direct paired test, controlling for spell_idx ---
print("=== Q3: Direct paired test — for mixed-outcome people, ===")
print("===     (mean MVR_z when promoted) − (mean MVR_z when not), and same for spell_idx ===")
person_mvr_diff = m.groupby('用户编码').apply(
    lambda g: g.loc[g['next_promoted']==1,'mvr_rank_z'].mean()
              - g.loc[g['next_promoted']==0,'mvr_rank_z'].mean(),
    include_groups=False).dropna()
person_idx_diff = m.groupby('用户编码').apply(
    lambda g: g.loc[g['next_promoted']==1,'spell_idx_at_level'].mean()
              - g.loc[g['next_promoted']==0,'spell_idx_at_level'].mean(),
    include_groups=False).dropna()

print(f"  Δ MVR_z  (promoted - not): mean = {person_mvr_diff.mean():+.3f}σ, t-test p = {ttest_1samp(person_mvr_diff,0).pvalue:.2e}")
print(f"  Δ spell_idx (promoted - not): mean = {person_idx_diff.mean():+.3f},   t-test p = {ttest_1samp(person_idx_diff,0).pvalue:.2e}")
print()

# Joint: regress per-person MVR_diff on per-person idx_diff to see how much MVR diff is explained by idx diff
joined = pd.DataFrame({'mvr_d':person_mvr_diff,'idx_d':person_idx_diff}).dropna()
mod = sm.OLS(joined['mvr_d'], sm.add_constant(joined[['idx_d']])).fit()
print("  Regress per-person Δ_MVR_z on per-person Δ_spell_idx:")
print(f"     intercept (residual MVR_z effect after netting time trend): {mod.params['const']:+.3f}σ")
print(f"     intercept SE: {mod.bse['const']:.3f},  t = {mod.tvalues['const']:+.2f},  p = {mod.pvalues['const']:.2e}")
print(f"     idx_d coefficient: {mod.params['idx_d']:+.3f}  (NS likely)")
print()
print("  → Even if we 'netted out' the time-trend effect of being a later spell,")
print(f"    the residual MVR_z effect is {mod.params['const']:+.3f}σ (p = {mod.pvalues['const']:.2e}).")

# --- Q4: Conditional on FIRST/LAST spell positions ---
print("\n=== Q4: Sub-analysis — Compare 'promoted spell' position to FIRST 副部 spell only ===")
person_first_last = []
for uid, g in m.groupby('用户编码'):
    g = g.sort_values('spell_idx_at_level')
    if (g['next_promoted']==1).any():
        promoted_row = g[g['next_promoted']==1].iloc[0]
        first_row = g.iloc[0]
        if promoted_row['spell_idx_at_level'] != first_row['spell_idx_at_level']:
            diff = promoted_row['mvr_rank_z'] - first_row['mvr_rank_z']
            person_first_last.append(diff)
person_first_last = pd.Series(person_first_last)
print(f"  N people where promoted spell ≠ first 副部 spell: {len(person_first_last)}")
print(f"  Mean Δ MVR_z (promoted spell − first 副部 spell): {person_first_last.mean():+.3f}σ")
print(f"  t-test p: {ttest_1samp(person_first_last, 0).pvalue:.2e}")
print(f"  % positive: {100*(person_first_last>0).mean():.1f}%")
