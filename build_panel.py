"""
Build person × spell panel:
- Each row = one career spell (a contiguous appointment to one position)
- Merge MVR rank of position
- Compute outcome: did the person reach a HIGHER formal rank in any later spell?
"""
import pandas as pd, numpy as np, re

senior = pd.read_pickle('senior_sample.pkl').sort_values(['用户编码','经历序号']).reset_index(drop=True)
mvr = pd.read_pickle('mvr_ranks.pkl')
basic = pd.read_excel('/sessions/loving-bold-goldberg/mnt/CPED_V1.0/Full Data.xlsx', sheet_name='基本信息')

def admin_level(row):
    dq = row['地区级别']
    if row['是否全国性组织']=='是': return '中央'
    if pd.isna(dq): return '省级'
    if dq=='副省级城市': return '副省级市'
    if dq=='地级市（区）': return '地级市'
    return '其他'

def normalize_title(t):
    if pd.isna(t): return None
    t = str(t).strip()
    t = re.split(r'[、，,]', t)[0].strip()
    repl = {'代市长':'市长','代省长':'省长','代理市长':'市长','代理省长':'省长'}
    return repl.get(t, t)

senior['admin'] = senior.apply(admin_level, axis=1)
senior['title'] = senior['具体职务'].apply(normalize_title)
senior = senior[senior['title'].notna()].copy()
senior['position'] = (senior['admin'] + '|' + senior['基本大类别'].astype(str) + '|' +
                      senior['职务一级关键词'].astype(str) + '|' + senior['title'])
senior['start_dt'] = pd.to_datetime(senior['起始时间（YYYY-MM-DD）'], errors='coerce')
senior['end_dt']   = pd.to_datetime(senior['终止时间（（YYYY-MM-DD））'], errors='coerce')
senior['start_year'] = senior['start_dt'].dt.year

# Map MVR rank
senior = senior.merge(mvr[['position','mvr_mean_rank','mvr_std_rank']], on='position', how='left')

level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
senior['level_num'] = senior['级别'].map(level_order)

# Birthday for age
basic['出生'] = pd.to_datetime(basic['出生日期(YYYY-MM-DD)'], errors='coerce')
senior = senior.merge(basic[['姓名','出生','最高学历']], on='姓名', how='left')
senior['age'] = (senior['start_dt'] - senior['出生']).dt.days / 365.25

# For each spell, future max level reached
senior = senior.sort_values(['用户编码','经历序号'])
senior['future_max_level'] = senior.groupby('用户编码')['level_num'].transform(lambda s: s[::-1].cummax()[::-1].shift(-1))

# Outcome: ever-promoted relative to current
senior['ever_promoted'] = (senior['future_max_level'] > senior['level_num']).astype('Int64')

# Tenure at current level: months at level_num before this spell
def tenure_at_level(g):
    g = g.copy()
    g['_t'] = (g['end_dt'] - g['start_dt']).dt.days / 30.4
    g['_cum_at_level'] = 0.0
    for i in range(len(g)):
        if pd.notna(g.iloc[i]['level_num']):
            cum = g.iloc[:i].loc[g.iloc[:i]['level_num']==g.iloc[i]['level_num'], '_t'].sum()
            g.iloc[i, g.columns.get_loc('_cum_at_level')] = cum
    return g['_cum_at_level']

# faster: vectorize
senior['_dur'] = (senior['end_dt'] - senior['start_dt']).dt.days/30.4
senior['_dur'] = senior['_dur'].clip(lower=0)
senior['tenure_at_level'] = senior.groupby(['用户编码','level_num'])['_dur'].cumsum() - senior['_dur']

# Last available year by person (for censoring concerns)
senior['last_obs_year'] = senior.groupby('用户编码')['start_year'].transform('max')

print(f"Total spells in senior_sample: {len(senior)}")
print(f"Spells with MVR rank match: {senior['mvr_mean_rank'].notna().sum()}")
print(f"Spells at 副部 (level 5) with MVR: {((senior['level_num']==5)&(senior['mvr_mean_rank'].notna())).sum()}")
print()

# Z-score MVR rank within formal level
senior['mvr_rank_z'] = senior.groupby('级别')['mvr_mean_rank'].transform(lambda x: (x - x.mean())/x.std())

# Save
senior.to_pickle('panel.pkl')
panel_clean = senior[['用户编码','姓名','经历序号','start_year','level_num','级别',
                     'position','基本大类别','admin','mvr_mean_rank','mvr_std_rank',
                     'mvr_rank_z','age','出生','最高学历','tenure_at_level',
                     'future_max_level','ever_promoted','last_obs_year']]
panel_clean.to_csv('panel.csv', index=False)
print("→ saved panel.pkl, panel.csv")

# --- Sample for Test 1: 副部 spells beginning by 2010, with valid MVR rank ---
t1 = senior[(senior['level_num']==5) & (senior['mvr_mean_rank'].notna()) & 
            (senior['start_year']<=2010)].copy()
print(f"\n=== Test 1 sample: 副部 spells starting ≤2010 with MVR ===")
print(f"  Spells: {len(t1)}")
print(f"  Unique people: {t1['用户编码'].nunique()}")
print(f"  Outcome distribution (ever promoted to 正部+ later):")
print(f"     Yes: {(t1['ever_promoted']==1).sum()} ({100*(t1['ever_promoted']==1).mean():.1f}%)")
print(f"     No:  {(t1['ever_promoted']==0).sum()} ({100*(t1['ever_promoted']==0).mean():.1f}%)")
print(f"  Mean MVR rank z: {t1['mvr_rank_z'].mean():.3f}")
print(f"  Mean age at spell start: {t1['age'].mean():.1f}")
print(f"  Mean tenure at 副部 already: {t1['tenure_at_level'].mean():.1f} months")
