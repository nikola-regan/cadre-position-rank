"""Test 1: properly handle NaN before cluster SE."""
import pandas as pd, numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf

panel = pd.read_pickle('panel.pkl')

df = panel[(panel['level_num']==5) & (panel['mvr_mean_rank'].notna()) &
           (panel['start_year']<=2010) & (panel['ever_promoted'].notna()) &
           (panel['age'].notna()) & (panel['最高学历'].notna())].copy()

df['edu_grad']  = (df['最高学历'].isin(['硕士','博士'])).astype(int)
df['edu_phd']   = (df['最高学历']=='博士').astype(int)
df['sys_party'] = (df['基本大类别']=='党委').astype(int)
df['sys_gov']   = (df['基本大类别']=='政府_国务院').astype(int)
df['sys_npc']   = (df['基本大类别']=='人大').astype(int)
df['sys_cppcc'] = (df['基本大类别']=='政协').astype(int)
df['admin_cent']= (df['admin']=='中央').astype(int)
df['admin_prov']= (df['admin']=='省级').astype(int)
df['tenure_yrs']= df['tenure_at_level']/12.0

# IMPORTANT: drop NaN in tenure too
df = df.dropna(subset=['tenure_yrs','age','mvr_rank_z'])
df = df.reset_index(drop=True)
df['用户编码'] = df['用户编码'].astype(int)
print(f"N = {len(df)}, unique people = {df['用户编码'].nunique()}")
print(f"Promotion rate: {df['ever_promoted'].mean()*100:.1f}%\n")

def fit(formula, data):
    return smf.logit(formula, data=data).fit(disp=0, cov_type='cluster',
        cov_kwds={'groups': data['用户编码'].values})

models = {
    'M1: bare':           'ever_promoted ~ mvr_rank_z',
    'M2: +person':        'ever_promoted ~ mvr_rank_z + age + tenure_yrs + edu_grad + edu_phd',
    'M3: +system':        'ever_promoted ~ mvr_rank_z + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov + sys_npc + sys_cppcc',
    'M4: +admin level':   'ever_promoted ~ mvr_rank_z + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov + sys_npc + sys_cppcc + admin_cent + admin_prov',
}

print(f"{'Model':<22} {'β(MVR_z)':>10} {'SE':>8} {'z':>7} {'p':>8}  N")
print("-"*65)
for name, f in models.items():
    m = fit(f, df)
    b = m.params['mvr_rank_z']; se = m.bse['mvr_rank_z']
    z = b/se; p = 2*(1-sm.stats.stattools.stats.norm.cdf(abs(z)))
    print(f"{name:<22} {b:>+10.4f} {se:>8.4f} {z:>+7.2f} {p:>8.4f}  {int(m.nobs)}")

# Quartile sanity check
print("\n=== Promotion rate by MVR rank quartile ===")
df['q'] = pd.qcut(df['mvr_rank_z'], 4, labels=['Q1(low)','Q2','Q3','Q4(high)'])
qs = df.groupby('q', observed=True)['ever_promoted'].agg(['count','mean'])
qs['promotion_rate_%'] = (qs['mean']*100).round(1)
print(qs[['count','promotion_rate_%']])

# By system AND quartile (the 退二线 hypothesis)
print("\n=== Promotion rate by 系统 × MVR quartile ===")
ct = df.groupby([df['基本大类别'], df['q']], observed=True)['ever_promoted'].mean().unstack()
ct = (ct*100).round(1)
print(ct)

# Drop 人大/政协 (退二线 endpoints) and re-test
print("\n=== Re-test EXCLUDING 人大/政协 spells (drop 退二线 endpoints) ===")
df_active = df[~df['基本大类别'].isin(['人大','政协'])].reset_index(drop=True)
print(f"N = {len(df_active)}, promotion rate = {df_active['ever_promoted'].mean()*100:.1f}%")
m = fit('ever_promoted ~ mvr_rank_z', df_active)
b = m.params['mvr_rank_z']; se = m.bse['mvr_rank_z']
z = b/se; p = 2*(1-sm.stats.stattools.stats.norm.cdf(abs(z)))
print(f"  bare logit: β = {b:+.4f}  SE = {se:.4f}  z = {z:+.2f}  p = {p:.4f}")

m = fit('ever_promoted ~ mvr_rank_z + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov', df_active)
b = m.params['mvr_rank_z']; se = m.bse['mvr_rank_z']
z = b/se; p = 2*(1-sm.stats.stattools.stats.norm.cdf(abs(z)))
print(f"  full controls: β = {b:+.4f}  SE = {se:.4f}  z = {z:+.2f}  p = {p:.4f}")

# Quartile within active
print("\n  Promotion rate by MVR quartile (excluding 人大/政协):")
df_active['q'] = pd.qcut(df_active['mvr_rank_z'], 4, labels=['Q1(low)','Q2','Q3','Q4(high)'])
qs = df_active.groupby('q', observed=True)['ever_promoted'].agg(['count','mean'])
qs['promotion_rate_%'] = (qs['mean']*100).round(1)
print(qs[['count','promotion_rate_%']])
