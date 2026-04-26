"""
Mediation: does early central exposure work THROUGH exposing officials to
higher-MVR-rank positions? If so, the 'central effect' on reaching 正部+
should attenuate when we control for average MVR rank exposure post-副厅.
"""
import pandas as pd, numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf

panel    = pd.read_pickle('panel.pkl')
sample   = pd.read_pickle('central_local_sample.pkl')

# For each person, compute their average MVR_z exposure in spells AFTER reaching 副厅
panel = panel.sort_values(['用户编码','经历序号'])
post_fuet = panel[(panel['level_num']>=3) & (panel['mvr_mean_rank'].notna()) &
                  (~panel['基本大类别'].isin(['人大','政协','行业协会_人民团体']))]
mvr_avg = post_fuet.groupby('用户编码').agg(
    mvr_z_avg = ('mvr_rank_z','mean'),
    mvr_z_max = ('mvr_rank_z','max'),
    n_spells_with_mvr = ('mvr_rank_z','count'),
).reset_index()

s = sample.merge(mvr_avg, on='用户编码', how='left')

# Restrict to those with at least 1 measurable post-副厅 spell
s2 = s.dropna(subset=['mvr_z_avg']).copy()
print(f"=== Mediation sample (have ≥1 post-副厅 active-system MVR exposure) ===")
print(f"N = {len(s2)}")
print(f"Reach 正部+: {s2['reach_zhengbu'].sum()} ({s2['reach_zhengbu'].mean()*100:.1f}%)")
print()

# Stage 1: pre_fuet_central_frac → mvr_z_avg
print("=== Stage 1: central exposure → MVR rank exposure ===")
m_s1 = smf.ols('mvr_z_avg ~ pre_fuet_central_frac + edu_grad + edu_phd + age_at_first + first_year',
               data=s2).fit()
print(f"  β(central_frac) = {m_s1.params['pre_fuet_central_frac']:+.4f}  "
      f"SE = {m_s1.bse['pre_fuet_central_frac']:.4f}  "
      f"p = {m_s1.pvalues['pre_fuet_central_frac']:.4g}")
print(f"  → 100pp central exposure shifts later MVR rank z by {m_s1.params['pre_fuet_central_frac']:+.3f}σ")
print()

# Stage 2: full mediation logit
print("=== Stage 2: outcome regression with both central_frac AND MVR exposure ===")
m_full = smf.logit('reach_zhengbu ~ pre_fuet_central_frac + mvr_z_avg + edu_grad + edu_phd + age_at_first + first_year + fuet_cohort_2000s',
                   data=s2).fit(disp=0)
print(m_full.summary().tables[1])
print()

# Without mediator
m_red = smf.logit('reach_zhengbu ~ pre_fuet_central_frac + edu_grad + edu_phd + age_at_first + first_year + fuet_cohort_2000s',
                  data=s2).fit(disp=0)

# Compare
b_total = m_red.params['pre_fuet_central_frac']
b_direct = m_full.params['pre_fuet_central_frac']
b_med   = m_full.params['mvr_z_avg']
b_path1 = m_s1.params['pre_fuet_central_frac']

print(f"=== Mediation summary ===")
print(f"  Total effect of central_frac on 正部+ (sans mediator):    β = {b_total:+.3f}")
print(f"  Direct effect (controlling for MVR exposure):                β = {b_direct:+.3f}")
print(f"  Effect through MVR exposure (a × b):  {b_path1:+.3f} × {b_med:+.3f} = {b_path1*b_med:+.3f}")
print(f"  Mediation share: {100*(b_total-b_direct)/b_total:.1f}% of total effect runs through MVR rank exposure")
print()

# Track-typology
def track(r):
    if r['pre_fuet_central_frac'] >= 0.5: return '中央型'
    elif r['pre_fuet_central_frac'] == 0: return '纯地方'
    else: return '穿梭型'
sample['track'] = sample.apply(track, axis=1)
print("=== Career-track typology and outcomes ===")
trk = sample.groupby('track').agg(
    n=('用户编码','count'),
    reach_fubu_pct=('reach_fubu', lambda x: (x.mean()*100).round(1)),
    reach_zhengbu_pct=('reach_zhengbu', lambda x: (x.mean()*100).round(1)),
    central_frac=('pre_fuet_central_frac','mean')
).reindex(['纯地方','穿梭型','中央型'])
print(trk)
print()

# Persistence: among those reaching 副部, fraction reaching 正部
print("=== Conditional: P(正部+ | already 副部+) by track ===")
sub = sample[sample['reach_fubu']==1]
print(sub.groupby('track')['reach_zhengbu'].agg(['count','mean']).round(3).reindex(['纯地方','穿梭型','中央型']))

# Save full sample with mediator
s2.to_pickle('central_local_with_mediator.pkl')
sample.to_pickle('central_local_sample.pkl')
