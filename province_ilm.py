"""
Provincial ILM analysis: 广东 / 上海 / 北京.
For each province: build intra-province transition network, run MVR-MCMC,
output ranks. Then compare positions across provinces.
"""
import pandas as pd, numpy as np, time, re
from numba import njit
from sklearn.cluster import KMeans
from scipy.stats import spearmanr

senior = pd.read_pickle('senior_sample.pkl').reset_index(drop=True)

def admin_level(row):
    dq = row['地区级别']
    if pd.isna(dq): return '省级'
    if dq == '副省级城市': return '副省级市'
    if dq == '地级市（区）': return '地级市'
    return '其他'

def normalize_title(t):
    if pd.isna(t): return None
    t = str(t).strip()
    t = re.split(r'[、，,]', t)[0].strip()
    repl = {'代市长':'市长','代省长':'省长','代理市长':'市长','代理省长':'省长'}
    return repl.get(t, t)

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
            for k in range(n_): out[s,k] = rank[k]
            s += 1
    return out[:s]

# Springrank-style warm start
def springrank_init(W, alpha=0.1):
    n = W.shape[0]
    d_in = W.sum(0); d_out = W.sum(1)
    L = -(W + W.T)
    np.fill_diagonal(L, d_in + d_out + alpha)
    b = d_in - d_out
    s = np.linalg.solve(L, b)
    return np.argsort(s).astype(np.int64)

def run_province(province, min_records=2):
    sub = senior[senior['地方一级关键词']==province].copy()
    sub['admin'] = sub.apply(admin_level, axis=1)
    sub['title'] = sub['具体职务'].apply(normalize_title)
    sub = sub[sub['title'].notna()].copy()
    sub['position'] = (sub['admin'] + '|' + sub['基本大类别'].astype(str) + '|' +
                       sub['职务一级关键词'].astype(str) + '|' + sub['title'])
    
    pos_cnt = sub['position'].value_counts()
    keep = set(pos_cnt[pos_cnt>=min_records].index)
    sub = sub[sub['position'].isin(keep)].copy()
    
    # transitions: consecutive records WITHIN this province, same person
    sub = sub.sort_values(['用户编码','经历序号'])
    trans = []
    for uid, g in sub.groupby('用户编码'):
        rows = g.to_dict('records')
        for i in range(len(rows)-1):
            a, b = rows[i], rows[i+1]
            if a['position'] == b['position']: continue
            trans.append((a['position'], b['position']))
    trans = pd.DataFrame(trans, columns=['from','to'])
    
    if len(trans) < 50:
        return None
    
    edge_w = trans.groupby(['from','to']).size().reset_index(name='w')
    positions = sorted(set(edge_w['from']).union(set(edge_w['to'])))
    idx = {p:i for i,p in enumerate(positions)}
    n = len(positions)
    
    W = np.zeros((n,n))
    for _, r in edge_w.iterrows():
        W[idx[r['from']], idx[r['to']]] += r['w']
    
    init = springrank_init(W)
    
    # Pool MCMC samples from 4 chains
    samples = []
    for c in range(4):
        s = mvr_mcmc(W, init, 500_000, 100, 100_000, c)
        samples.append(s)
    samples = np.concatenate(samples, axis=0)
    
    mean_rank = samples.mean(axis=0)
    std_rank  = samples.std(axis=0)
    
    out = pd.DataFrame({
        'position': positions,
        f'rank_{province}': mean_rank,
        f'std_{province}':  std_rank,
        f'n_{province}':    [int(pos_cnt[p]) for p in positions],
    })
    out['true_level'] = out['position'].map(sub.groupby('position')['级别'].agg(lambda x: x.mode().iloc[0] if len(x.mode())>0 else None))
    return out, len(trans), n

results = {}
for prov in ['广东省','上海市','北京市']:
    t0 = time.time()
    r = run_province(prov, min_records=2)
    if r is None:
        print(f"{prov}: too few transitions, skipped")
        continue
    out, n_trans, n_pos = r
    print(f"{prov}: {n_pos} positions, {n_trans} transitions ({time.time()-t0:.1f}s)")
    results[prov] = out

# --- Compare ---
print("\n=== Validation per province ===")
level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
for prov, df_p in results.items():
    df_p['lv_num'] = df_p['true_level'].map(level_order)
    v = df_p.dropna(subset=['lv_num'])
    rho, _ = spearmanr(v[f'rank_{prov}'], v['lv_num'])
    print(f"  {prov}: Spearman ρ = {rho:.3f} (n={len(v)})")

# Merge by position to find shared positions across provinces
merged = None
for prov, df_p in results.items():
    sel = df_p[['position','true_level',f'rank_{prov}',f'std_{prov}',f'n_{prov}']]
    merged = sel if merged is None else merged.merge(sel, on=['position','true_level'], how='outer')

n_shared = merged.dropna(subset=['rank_广东省','rank_上海市','rank_北京市']).shape[0]
print(f"\n岗位共现于三省的: {n_shared}")

# Spearman across pairs of provinces (using only shared positions)
print("\n=== 跨省 rank 一致性(只用三省共有的岗位) ===")
shared = merged.dropna(subset=['rank_广东省','rank_上海市','rank_北京市'])
for p1, p2 in [('广东省','上海市'),('广东省','北京市'),('上海市','北京市')]:
    rho, _ = spearmanr(shared[f'rank_{p1}'], shared[f'rank_{p2}'])
    print(f"  {p1} vs {p2}:  ρ = {rho:.3f}  (n={len(shared)})")

# Find positions ranked differently across provinces
shared = shared.copy()
# normalize ranks within each province to [0,1] for comparability
for p in ['广东省','上海市','北京市']:
    r = shared[f'rank_{p}']
    shared[f'norm_{p}'] = (r - r.min()) / (r.max() - r.min())

shared['norm_max'] = shared[['norm_广东省','norm_上海市','norm_北京市']].max(axis=1)
shared['norm_min'] = shared[['norm_广东省','norm_上海市','norm_北京市']].min(axis=1)
shared['norm_range'] = shared['norm_max'] - shared['norm_min']

print("\n=== Top 12 岗位 with LARGEST cross-province rank divergence ===")
top_div = shared.nlargest(12, 'norm_range')[['position','true_level','norm_广东省','norm_上海市','norm_北京市','norm_range']]
for _, r in top_div.iterrows():
    print(f"  Δ={r['norm_range']:.2f}  GD={r['norm_广东省']:.2f}  SH={r['norm_上海市']:.2f}  BJ={r['norm_北京市']:.2f}  级别={r['true_level']}  | {r['position']}")

print("\n=== Top 8 岗位 with SMALLEST divergence (consensus rankings) ===")
low_div = shared.nsmallest(8, 'norm_range')[['position','true_level','norm_广东省','norm_上海市','norm_北京市','norm_range']]
for _, r in low_div.iterrows():
    print(f"  Δ={r['norm_range']:.2f}  GD={r['norm_广东省']:.2f}  SH={r['norm_上海市']:.2f}  BJ={r['norm_北京市']:.2f}  级别={r['true_level']}  | {r['position']}")

merged.to_csv('province_ilm_merged.csv', index=False)
shared.to_csv('province_shared_positions.csv', index=False)
print("\n→ saved province_ilm_merged.csv and province_shared_positions.csv")
