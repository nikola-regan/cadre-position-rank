"""
Conditional (fixed-effects) logit — the correct model for binary outcome with person FE.
Only mixed-outcome people contribute to identification by construction.
"""
import pandas as pd, numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit
import statsmodels.api as sm

panel = pd.read_pickle('panel.pkl').sort_values(['用户编码','经历序号'])

panel['next_level_num']  = panel.groupby('用户编码')['level_num'].shift(-1)
panel['next_promoted']   = (panel['next_level_num'] > panel['level_num']).astype('Int64')
panel['active'] = (~panel['基本大类别'].isin(['人大','政协','行业协会_人民团体'])).astype(int)

df = panel[(panel['level_num']==5) & (panel['mvr_mean_rank'].notna()) &
           (panel['next_level_num'].notna()) & (panel['active']==1) &
           (panel['age'].notna()) & (panel['tenure_at_level'].notna())].copy()
df['tenure_yrs'] = df['tenure_at_level']/12.0
df = df.dropna(subset=['mvr_rank_z','age','tenure_yrs','next_promoted']).reset_index(drop=True)

# Conditional Logit needs each entity to have ≥1 with y=1 AND ≥1 with y=0 to contribute
print("=== Conditional Logit (proper FE for binary outcome) ===")
df['用户编码'] = df['用户编码'].astype(int)
df['next_promoted'] = df['next_promoted'].astype(int)

X = df[['mvr_rank_z','age','tenure_yrs']]
m = ConditionalLogit(df['next_promoted'], X, groups=df['用户编码']).fit(disp=0)
print(m.summary())

# How many people effectively contribute
n_contrib = df.groupby('用户编码')['next_promoted'].nunique()
n_used = (n_contrib > 1).sum()
n_used_obs = df[df['用户编码'].isin(n_contrib[n_contrib>1].index)].shape[0]
print(f"\nEntities contributing to identification: {n_used} (those with mixed outcomes)")
print(f"Observations from these entities: {n_used_obs}")

# Robustness: also condition on system + admin level interactions (but those are spell-varying)
print("\n=== With additional spell-level controls (system, admin) ===")
df['sys_party'] = (df['基本大类别']=='党委').astype(int)
df['sys_gov']   = (df['基本大类别']=='政府_国务院').astype(int)
df['admin_cent']= (df['admin']=='中央').astype(int)
df['admin_prov']= (df['admin']=='省级').astype(int)
X2 = df[['mvr_rank_z','age','tenure_yrs','sys_party','sys_gov','admin_cent','admin_prov']]
m2 = ConditionalLogit(df['next_promoted'], X2, groups=df['用户编码']).fit(disp=0)
print(m2.summary())

# Also try with party+government only (drop other systems)
print("\n=== Restricted to 党委 + 政府 only ===")
df_pg = df[df['基本大类别'].isin(['党委','政府_国务院'])].copy()
print(f"N = {len(df_pg)}, unique people = {df_pg['用户编码'].nunique()}")
X3 = df_pg[['mvr_rank_z','age','tenure_yrs']]
m3 = ConditionalLogit(df_pg['next_promoted'], X3, groups=df_pg['用户编码']).fit(disp=0)
print(m3.summary())

# Marginal effect interpretation
b = m3.params['mvr_rank_z']
or_ = np.exp(b)
print(f"\nOdds ratio for 1-σ MVR_z increase: {or_:.3f}")
print(f"  → A 1-σ increase in 副部岗位 MVR rank multiplies promotion odds by {or_:.2f}x")
