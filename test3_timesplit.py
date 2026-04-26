"""
(a) Time-split MVR: estimate MVR using only data with start_year ≤ T_split.
    Then test the prediction on spells starting AFTER T_split.
    This removes look-ahead bias.
"""
import pandas as pd, numpy as np, time, re
from numba import njit
import statsmodels.api as sm
import statsmodels.formula.api as smf

senior = pd.read_pickle('senior_sample.pkl').sort_values(['用户编码','经历序号']).reset_index(drop=True)

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
level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
senior['level_num'] = senior['级别'].map(level_order)

# Train MVR on spells STARTING ≤ T_split
T_split = 2008
print(f"=== Time split at year {T_split} ===")
train = senior[senior['start_year'] <= T_split].copy()
print(f"Training spells: {len(train)} ({train['用户编码'].nunique()} people)")

# Build position transitions ONLY from training spells
train = train.sort_values(['用户编码','经历序号'])
trans = []
for uid, g in train.groupby('用户编码'):
    rows = g.to_dict('records')
    for i in range(len(rows)-1):
        a, b = rows[i], rows[i+1]
        # Only count transitions where BOTH endpoints are in training (start year ≤ T_split)
        if a['start_year'] <= T_split and b['start_year'] <= T_split:
            if a['position'] != b['position']:
                trans.append((a['position'], b['position']))
trans = pd.DataFrame(trans, columns=['from','to'])
print(f"Training transitions: {len(trans)}")

# Position frequency in training
pos_count = pd.concat([trans['from'], trans['to']]).value_counts()
keep = set(pos_count[pos_count>=3].index)
trans = trans[trans['from'].isin(keep) & trans['to'].isin(keep)]
edge_w = trans.groupby(['from','to']).size().reset_index(name='w')
positions_T = sorted(set(edge_w['from']).union(set(edge_w['to'])))
idx = {p:i for i,p in enumerate(positions_T)}
n_T = len(positions_T)
print(f"Positions in training network: {n_T}")

W = np.zeros((n_T, n_T))
for _, r in edge_w.iterrows():
    W[idx[r['from']], idx[r['to']]] += r['w']

# SpringRank warm start
def springrank_init(W, alpha=0.1):
    n = W.shape[0]
    d_in = W.sum(0); d_out = W.sum(1)
    L = -(W + W.T)
    np.fill_diagonal(L, d_in + d_out + alpha)
    b = d_in - d_out
    return np.argsort(np.linalg.solve(L, b)).astype(np.int64)

@njit(cache=True)
def mvr_mcmc(W, init_order, n_iter, n_samples, burn_in, seed):
    np.random.seed(seed)
    n_ = len(init_order)
    order = init_order.copy()
    rank = np.empty(n_, dtype=np.int64)
    for k in range(n_): rank[order[k]] = k
    out = np.empty((n_samples, n_), dtype=np.int32)
    interval = max(1, (n_iter - burn_in) // n_samples)
    s = 0
    for it in range(n_iter):
        p = np.random.randint(0, n_-1)
        a = order[p]; b = order[p+1]
        delta = W[a,b] - W[b,a]
        if delta < 0 or (delta == 0 and np.random.random() < 0.5):
            order[p] = b; order[p+1] = a
            rank[a] = p+1; rank[b] = p
        if it >= burn_in and (it - burn_in) % interval == 0 and s < n_samples:
            for k in range(n_): out[s, k] = rank[k]
            s += 1
    return out[:s]

init = springrank_init(W)
_ = mvr_mcmc(W, init, 100, 5, 10, 0)  # JIT warmup

print("Running MCMC...")
t0 = time.time()
samples = []
for c in range(4):
    s = mvr_mcmc(W, init, 1_000_000, 200, 200_000, c)
    samples.append(s)
samples = np.concatenate(samples, axis=0)
print(f"Done in {time.time()-t0:.1f}s, samples shape {samples.shape}")

mean_rank_T = samples.mean(axis=0)
std_rank_T  = samples.std(axis=0)
mvr_T = pd.DataFrame({
    'position': positions_T,
    'mvr_rank_T': mean_rank_T,
    'mvr_std_T':  std_rank_T,
})

# z-score within formal level (using training-period level mode for each position)
pos_level_T = train.groupby('position')['级别'].agg(lambda x: x.mode().iloc[0] if len(x.mode())>0 else None)
mvr_T['true_level'] = mvr_T['position'].map(pos_level_T)
# Validation
from scipy.stats import spearmanr
mvr_T['lv_num'] = mvr_T['true_level'].map(level_order)
v = mvr_T.dropna(subset=['lv_num'])
rho, _ = spearmanr(v['mvr_rank_T'], v['lv_num'])
print(f"\nTrain MVR validation (Spearman vs 级别): ρ = {rho:.3f}")

# z-score within 副部 level
mvr_T['mvr_z_T'] = mvr_T.groupby('true_level')['mvr_rank_T'].transform(lambda x: (x-x.mean())/x.std())

# Save
mvr_T.to_pickle('mvr_T2008.pkl')

# === Test on POST-T_split sample ===
print(f"\n=== Test sample: 副部 spells starting > {T_split} (out-of-sample) ===")
test = senior[senior['start_year'] > T_split].copy()

# Compute outcomes (next-spell promotion, ever-promoted)
senior['future_max_level'] = senior.groupby('用户编码')['level_num'].transform(
    lambda s: s[::-1].cummax()[::-1].shift(-1))
senior['ever_promoted'] = (senior['future_max_level'] > senior['level_num']).astype('Int64')

# Merge
basic = pd.read_excel('/sessions/loving-bold-goldberg/mnt/CPED_V1.0/Full Data.xlsx', sheet_name='基本信息')
basic['出生'] = pd.to_datetime(basic['出生日期(YYYY-MM-DD)'], errors='coerce')
senior = senior.merge(basic[['姓名','出生','最高学历']], on='姓名', how='left')
senior['age'] = (senior['start_dt'] - senior['出生']).dt.days/365.25
senior['_dur'] = (senior['end_dt'] - senior['start_dt']).dt.days/30.4
senior['_dur'] = senior['_dur'].clip(lower=0)
senior['tenure_yrs'] = (senior.groupby(['用户编码','level_num'])['_dur'].cumsum() - senior['_dur'])/12.0
senior = senior.merge(mvr_T[['position','mvr_rank_T','mvr_std_T','mvr_z_T']], on='position', how='left')

# Test sample: 副部 spells starting > T_split, with valid pre-T MVR
mask = (senior['level_num']==5) & (senior['start_year']>T_split) & \
       (senior['mvr_rank_T'].notna()) & (senior['ever_promoted'].notna()) & \
       (senior['age'].notna()) & (senior['tenure_yrs'].notna())
df = senior[mask].copy()

# Active subsample (drop 退二线)
df['active'] = (~df['基本大类别'].isin(['人大','政协','行业协会_人民团体'])).astype(int)
df['edu_grad']  = (df['最高学历'].isin(['硕士','博士'])).astype(int)
df['edu_phd']   = (df['最高学历']=='博士').astype(int)
df['sys_party'] = (df['基本大类别']=='党委').astype(int)
df['sys_gov']   = (df['基本大类别']=='政府_国务院').astype(int)
df['sys_npc']   = (df['基本大类别']=='人大').astype(int)
df['sys_cppcc'] = (df['基本大类别']=='政协').astype(int)
df['admin_cent']= (df['admin']=='中央').astype(int)
df['admin_prov']= (df['admin']=='省级').astype(int)
df = df.dropna(subset=['mvr_z_T']).reset_index(drop=True)
df['用户编码'] = df['用户编码'].astype(int)

print(f"  Test sample: {len(df)} spells, {df['用户编码'].nunique()} people")
print(f"  Promotion rate (any level up): {df['ever_promoted'].mean()*100:.1f}%")

def fit(formula, data):
    return smf.logit(formula, data=data).fit(disp=0, cov_type='cluster',
                cov_kwds={'groups': data['用户编码'].values})

print(f"\n=== Time-split out-of-sample logit (subjects: 副部 spells started after {T_split}) ===")
# Full sample
print("\n  -- Full sample (incl 退二线) --")
m = fit('ever_promoted ~ mvr_z_T', df)
b, se = m.params['mvr_z_T'], m.bse['mvr_z_T']
print(f"     bare:     β = {b:+.4f}  SE = {se:.4f}  z = {b/se:+.2f}  p = {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")

m = fit('ever_promoted ~ mvr_z_T + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov + sys_npc + sys_cppcc', df)
b, se = m.params['mvr_z_T'], m.bse['mvr_z_T']
print(f"     +ctrls:   β = {b:+.4f}  SE = {se:.4f}  z = {b/se:+.2f}  p = {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")

# Active only
df_a = df[df['active']==1].reset_index(drop=True)
print(f"\n  -- Active systems only (n = {len(df_a)}) --")
m = fit('ever_promoted ~ mvr_z_T', df_a)
b, se = m.params['mvr_z_T'], m.bse['mvr_z_T']
print(f"     bare:     β = {b:+.4f}  SE = {se:.4f}  z = {b/se:+.2f}  p = {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")

m = fit('ever_promoted ~ mvr_z_T + age + tenure_yrs + edu_grad + edu_phd + sys_party + sys_gov', df_a)
b, se = m.params['mvr_z_T'], m.bse['mvr_z_T']
print(f"     +ctrls:   β = {b:+.4f}  SE = {se:.4f}  z = {b/se:+.2f}  p = {2*(1-sm.stats.stattools.stats.norm.cdf(abs(b/se))):.4f}")

# Quartile (active)
df_a['q'] = pd.qcut(df_a['mvr_z_T'], 4, labels=['Q1','Q2','Q3','Q4'])
qs = df_a.groupby('q', observed=True)['ever_promoted'].agg(['count','mean'])
qs['promotion_rate_%'] = (qs['mean']*100).round(1)
print(f"\n  Promotion rate by MVR_T quartile (active only):")
print(qs[['count','promotion_rate_%']])
