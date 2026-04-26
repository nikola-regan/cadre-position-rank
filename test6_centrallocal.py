"""
Variant question: Does early-career central exposure predict reaching 正部+?

Sample: officials who reached at least 副厅 (level≥3).
Treatment: fraction of pre-副厅 years spent at 中央 organizations.
Outcome: ever reaching 正部+ (level≥6).

Mediation: does the effect run through higher MVR rank exposure later?
"""
import pandas as pd, numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf

# We need ALL CPED spells, not just senior_sample (which is 副部+ only)
all_records = pd.read_excel('/sessions/loving-bold-goldberg/mnt/CPED_V1.0/Full Data.xlsx', sheet_name='全部经历')
basic = pd.read_excel('/sessions/loving-bold-goldberg/mnt/CPED_V1.0/Full Data.xlsx', sheet_name='基本信息')

all_records['start_dt'] = pd.to_datetime(all_records['起始时间（YYYY-MM-DD）'], errors='coerce')
all_records['end_dt']   = pd.to_datetime(all_records['终止时间（（YYYY-MM-DD））'], errors='coerce')
level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
all_records['level_num'] = all_records['级别'].map(level_order)
basic['出生'] = pd.to_datetime(basic['出生日期(YYYY-MM-DD)'], errors='coerce')

# Drop 学校 (training/study spells, not career postings)
career = all_records[all_records['基本大类别']!='学校'].copy().sort_values(['用户编码','经历序号'])
career = career.dropna(subset=['start_dt','end_dt','level_num']).reset_index(drop=True)

# Identify central vs local for each spell
career['is_central'] = (career['是否全国性组织']=='是').astype(int)
career['dur_yrs'] = (career['end_dt']-career['start_dt']).dt.days/365.25
career['dur_yrs'] = career['dur_yrs'].clip(lower=0)

# For each person: time-to-副厅 = first record where level_num >= 3
def per_person_summary(g):
    g = g.sort_values('经历序号')
    # Years before reaching 副厅
    pre_fuet = g[g['level_num'] < 3]
    if len(pre_fuet) == 0:
        # Already 副厅 from start (could be top officials whose pre-副厅 history is missing)
        pre_yrs = 0
        pre_central_yrs = 0
        first_at_central = np.nan
    else:
        pre_yrs = pre_fuet['dur_yrs'].sum()
        pre_central_yrs = (pre_fuet['dur_yrs'] * pre_fuet['is_central']).sum()
        first_at_central = pre_fuet.iloc[0]['is_central']
    
    # Did they ever reach 副厅? (sample restriction)
    reach_fuet = (g['level_num']>=3).any()
    
    # Peak level
    peak = g['level_num'].max()
    
    # Year of first 副厅
    if reach_fuet:
        fuet_year = g[g['level_num']>=3].iloc[0]['start_dt'].year
    else:
        fuet_year = np.nan
    
    # First job year and age at first
    first_year = g.iloc[0]['start_dt'].year
    
    return pd.Series({
        'pre_fuet_yrs': pre_yrs,
        'pre_fuet_central_yrs': pre_central_yrs,
        'pre_fuet_central_frac': pre_central_yrs/pre_yrs if pre_yrs>0 else np.nan,
        'first_at_central': first_at_central,
        'reach_fuet': reach_fuet,
        'peak_level': peak,
        'fuet_year': fuet_year,
        'first_year': first_year,
    })

print("Computing per-person summary...")
person_sum = career.groupby('用户编码').apply(per_person_summary, include_groups=False).reset_index()
print(f"  Total people: {len(person_sum)}")

# Merge with 基本信息
person_sum = person_sum.merge(basic[['Unnamed: 0','姓名','出生','最高学历']],
                              left_on='用户编码', right_on='Unnamed: 0', how='left')
person_sum['age_at_first'] = person_sum['first_year'] - person_sum['出生'].dt.year

# Sample restriction: must reach 副厅 AND have observable early career (≥3 years pre-副厅)
sample = person_sum[(person_sum['reach_fuet']==True) & (person_sum['pre_fuet_yrs']>=3)].copy()
print(f"  Reach 副厅 + ≥3 yrs early career: {len(sample)}")
print()

# Outcome: reach 正部+ (level≥6)
sample['reach_zhengbu'] = (sample['peak_level']>=6).astype(int)
sample['reach_fubu']    = (sample['peak_level']>=5).astype(int)

print("=== Sample summary ===")
print(f"  Reach 副厅:  {len(sample)}")
print(f"    of which reached 副部+:  {sample['reach_fubu'].sum()} ({sample['reach_fubu'].mean()*100:.1f}%)")
print(f"    of which reached 正部+:  {sample['reach_zhengbu'].sum()} ({sample['reach_zhengbu'].mean()*100:.1f}%)")
print()
print(f"  Pre-副厅 central fraction: mean={sample['pre_fuet_central_frac'].mean():.3f}, median={sample['pre_fuet_central_frac'].median():.3f}")
print(f"  Distribution:")
print(sample['pre_fuet_central_frac'].describe(percentiles=[.25,.5,.75,.9]).round(3))

# Decile
sample['central_decile'] = pd.qcut(sample['pre_fuet_central_frac'].rank(method='first'),
                                    10, labels=False)
print("\n=== Reach 正部+ by central exposure decile ===")
ct = sample.groupby('central_decile').agg(
    n=('用户编码','count'),
    central_frac=('pre_fuet_central_frac','mean'),
    reach_zhengbu_pct=('reach_zhengbu', lambda x: (x.mean()*100).round(1))
).round(3)
print(ct)

# Logit: reach_zhengbu ~ central_frac + controls
sample['edu_grad'] = (sample['最高学历'].isin(['硕士','博士'])).astype(int)
sample['edu_phd']  = (sample['最高学历']=='博士').astype(int)
sample['用户编码'] = sample['用户编码'].astype(int)
sample['fuet_cohort_2000s'] = (sample['fuet_year']>=2000).astype(int)
sample = sample.dropna(subset=['pre_fuet_central_frac','age_at_first','first_year']).copy()

print(f"\n=== Logit: reach_zhengbu ~ pre_fuet_central_frac (+ controls) ===")
print(f"N = {len(sample)}")

m1 = smf.logit('reach_zhengbu ~ pre_fuet_central_frac', data=sample).fit(disp=0)
print("\n  M1 bare:")
b, se = m1.params['pre_fuet_central_frac'], m1.bse['pre_fuet_central_frac']
print(f"    β = {b:+.4f}  SE = {se:.4f}  z = {b/se:+.2f}  p = {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")
print(f"    OR per 10pp central frac: {np.exp(b*0.1):.3f}")

m2 = smf.logit('reach_zhengbu ~ pre_fuet_central_frac + edu_grad + edu_phd + age_at_first + first_year + fuet_cohort_2000s',
               data=sample).fit(disp=0)
print("\n  M2 +controls (education + age + cohort):")
print(m2.summary().tables[1])

# Heterogeneity by 学历
print("\n=== Heterogeneity: effect by 学历 ===")
for ed_lab, mask in [('本科及以下', sample['edu_grad']==0),
                      ('硕士', (sample['edu_grad']==1) & (sample['edu_phd']==0)),
                      ('博士', sample['edu_phd']==1)]:
    sub = sample[mask]
    if len(sub) < 30 or sub['reach_zhengbu'].sum() < 5: continue
    m = smf.logit('reach_zhengbu ~ pre_fuet_central_frac + age_at_first + first_year', 
                  data=sub).fit(disp=0)
    b = m.params['pre_fuet_central_frac']; se = m.bse['pre_fuet_central_frac']
    rate0 = sub.loc[sub['pre_fuet_central_frac']<sub['pre_fuet_central_frac'].median(), 'reach_zhengbu'].mean()
    rate1 = sub.loc[sub['pre_fuet_central_frac']>=sub['pre_fuet_central_frac'].median(), 'reach_zhengbu'].mean()
    print(f"  {ed_lab:12s}  n={len(sub):4d}  β={b:+.3f}±{se:.3f}  p={2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.3f}"
          f"  低央 → 高央: {rate0*100:.1f}% → {rate1*100:.1f}%")

# Save sample
sample.to_pickle('central_local_sample.pkl')
print("\n→ saved central_local_sample.pkl")
