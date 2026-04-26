"""B3: Predecessor's career outcome as exogenous signal of position quality."""
import pandas as pd, numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf

panel = pd.read_pickle('panel.pkl').sort_values(['用户编码','经历序号']).reset_index(drop=True)

# spells list with dates
all_spells = panel[['用户编码','姓名','经历序号','position','级别','level_num',
                    'start_dt','end_dt','start_year','基本大类别','admin','出生']].copy()
all_spells = all_spells.dropna(subset=['start_dt']).reset_index(drop=True)

# For each spell, find the LAST distinct holder of same position whose end_dt < current start_dt
print("Finding predecessors...")
pred_records = []
for pos, g in all_spells.groupby('position'):
    g = g.sort_values(['start_dt','用户编码'])
    rows = g.to_dict('records')
    for i in range(len(rows)):
        cur = rows[i]
        for j in range(i-1, -1, -1):
            if pd.notna(rows[j]['end_dt']) and rows[j]['end_dt'] < cur['start_dt'] and rows[j]['用户编码'] != cur['用户编码']:
                pred_records.append({
                    'cur_uid': cur['用户编码'],
                    'cur_xh':  cur['经历序号'],
                    'pred_uid': rows[j]['用户编码'],
                    'pred_xh':  rows[j]['经历序号'],
                    'pred_end': rows[j]['end_dt'],
                    'gap_yrs': (cur['start_dt'] - rows[j]['end_dt']).days/365.25,
                })
                break
pred_df = pd.DataFrame(pred_records)
print(f"  spells with identified predecessor: {len(pred_df)} (out of {len(all_spells)} spells)")
print(f"  median gap (years): {pred_df['gap_yrs'].median():.2f}\n")

# For each predecessor, look up their next-spell outcome
panel_mini = panel[['用户编码','经历序号','level_num','基本大类别','出生']].copy()
panel_mini['next_level_num'] = panel.groupby('用户编码')['level_num'].shift(-1)
panel_mini['next_系统']      = panel.groupby('用户编码')['基本大类别'].shift(-1)

pred_outcomes = pred_df.merge(
    panel_mini.rename(columns={'用户编码':'pred_uid','经历序号':'pred_xh',
                               'level_num':'pred_level',
                               'next_level_num':'pred_next_level',
                               'next_系统':'pred_next_sys',
                               '出生':'pred_dob',
                               '基本大类别':'pred_sys'}),
    on=['pred_uid','pred_xh'], how='left')
pred_outcomes['pred_age_at_end'] = (pred_outcomes['pred_end'] - pred_outcomes['pred_dob']).dt.days/365.25

def classify_pred(r):
    if pd.isna(r['pred_next_level']):
        if pd.notna(r['pred_age_at_end']) and r['pred_age_at_end']>=60:
            return 'retired'
        return 'unknown'
    if r['pred_next_level'] > r['pred_level']:
        return 'up'
    if r['pred_next_level'] < r['pred_level']:
        return 'down'
    if r['pred_next_sys'] in ('人大','政协','行业协会_人民团体'):
        return 'tuierxian'
    return 'lateral'

pred_outcomes['pred_outcome'] = pred_outcomes.apply(classify_pred, axis=1)
print("=== Predecessor outcome distribution (all 副部+ spells) ===")
print(pred_outcomes['pred_outcome'].value_counts())
print()

# Merge back
panel_pred = panel.merge(
    pred_outcomes[['cur_uid','cur_xh','pred_outcome','gap_yrs']].rename(
        columns={'cur_uid':'用户编码','cur_xh':'经历序号'}),
    on=['用户编码','经历序号'], how='left')
panel_pred.to_pickle('panel_pred.pkl')

# === Validity: pred outcome × MVR rank (subsample 副部 with valid MVR) ===
print("=== Validity check 1: predecessor outcome → current position MVR rank z ===")
df_v = panel_pred[(panel_pred['level_num']==5) & (panel_pred['mvr_mean_rank'].notna()) &
                  (panel_pred['pred_outcome'].notna()) &
                  (panel_pred['pred_outcome']!='unknown')].copy()
print(f"  N: {len(df_v)}")
print(df_v.groupby('pred_outcome')['mvr_rank_z'].agg(['mean','std','count']).round(3))
print()

# === Test: incumbent's promotion by predecessor outcome ===
df_t = panel_pred[(panel_pred['level_num']==5) & (panel_pred['ever_promoted'].notna()) &
                  (panel_pred['pred_outcome'].notna()) &
                  (panel_pred['pred_outcome']!='unknown') &
                  (panel_pred['start_year']<=2010)].copy()

print("=== Validity check 2: incumbent promote rate by predecessor outcome ===")
print(f"  All systems n = {len(df_t)}")
prom = df_t.groupby('pred_outcome')['ever_promoted'].agg(['mean','count'])
prom['mean_pct'] = (prom['mean']*100).round(1)
print(prom[['mean_pct','count']])
print()

df_a = df_t[~df_t['基本大类别'].isin(['人大','政协','行业协会_人民团体'])].copy()
print(f"  Active subsample n = {len(df_a)}")
prom_a = df_a.groupby('pred_outcome')['ever_promoted'].agg(['mean','count'])
prom_a['mean_pct'] = (prom_a['mean']*100).round(1)
print(prom_a[['mean_pct','count']])
print()

# === Reduced-form regression ===
df_a['pred_up']        = (df_a['pred_outcome']=='up').astype(int)
df_a['pred_tuierxian'] = (df_a['pred_outcome']=='tuierxian').astype(int)
df_a['pred_down']      = (df_a['pred_outcome']=='down').astype(int)
df_a['pred_ret']       = (df_a['pred_outcome']=='retired').astype(int)
df_a = df_a.dropna(subset=['age','tenure_at_level']).copy()
df_a['tenure_yrs'] = df_a['tenure_at_level']/12.0
df_a['edu_grad']  = (df_a['最高学历'].isin(['硕士','博士'])).astype(int)
df_a['edu_phd']   = (df_a['最高学历']=='博士').astype(int)
df_a['sys_party'] = (df_a['基本大类别']=='党委').astype(int)
df_a['sys_gov']   = (df_a['基本大类别']=='政府_国务院').astype(int)
df_a['用户编码']  = df_a['用户编码'].astype(int)

print("=== Reduced-form: incumbent_promoted ~ predecessor outcome (active sample) ===")
m = smf.logit(
    'ever_promoted ~ pred_up + pred_tuierxian + pred_down + pred_ret + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov',
    data=df_a).fit(disp=0, cov_type='cluster', cov_kwds={'groups': df_a['用户编码'].values})
print(f"  N = {int(m.nobs)}, baseline (pred_lateral) implicit")
print(f"{'var':<16} {'β':>10} {'SE':>8} {'z':>7} {'p':>8}")
for k in ['pred_up','pred_tuierxian','pred_down','pred_ret']:
    b, se = m.params[k], m.bse[k]
    print(f"  {k:<14} {b:>+10.4f} {se:>8.4f} {b/se:>+7.2f} {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):>8.4f}")
print()

# === Horse race ===
print("=== Horse race: incumbent_promoted ~ MVR_z + pred_outcome ===")
df_h = df_a[df_a['mvr_rank_z'].notna()].copy()
print(f"N = {len(df_h)}")
m2 = smf.logit(
    'ever_promoted ~ mvr_rank_z + pred_up + pred_tuierxian + pred_down + pred_ret + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov',
    data=df_h).fit(disp=0, cov_type='cluster', cov_kwds={'groups': df_h['用户编码'].values})
print(f"{'var':<16} {'β':>10} {'SE':>8} {'z':>7} {'p':>8}")
for k in ['mvr_rank_z','pred_up','pred_tuierxian','pred_down','pred_ret']:
    b, se = m2.params[k], m2.bse[k]
    print(f"  {k:<14} {b:>+10.4f} {se:>8.4f} {b/se:>+7.2f} {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):>8.4f}")
