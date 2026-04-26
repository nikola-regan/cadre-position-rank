"""Huitfeldt-Kostøl-Nimczik-Weber MVR algorithm — Numba accelerated."""
import pandas as pd, numpy as np, time
from numba import njit
from sklearn.cluster import KMeans
from scipy.stats import spearmanr, kendalltau

edges   = pd.read_pickle('edges.pkl')
ranks   = pd.read_pickle('ranks.pkl')
records = pd.read_pickle('records.pkl')

positions = sorted(set(edges['from']).union(set(edges['to'])))
idx = {p:i for i,p in enumerate(positions)}
n = len(positions)
print(f"n positions: {n}")

W = np.zeros((n,n), dtype=np.float64)
for _, r in edges.iterrows():
    W[idx[r['from']], idx[r['to']]] += r['w']

sr = ranks.set_index('position')['spring_rank']
init_order = np.argsort([sr[p] for p in positions]).astype(np.int64)

@njit(cache=True)
def mvr_mcmc(W, init_order, n_iter, n_samples, burn_in, seed):
    np.random.seed(seed)
    n_ = len(init_order)
    order = init_order.copy()
    rank = np.empty(n_, dtype=np.int64)
    for k in range(n_):
        rank[order[k]] = k
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
            for k in range(n_):
                out[s, k] = rank[k]
            s += 1
    return out[:s]

@njit(cache=True)
def violations(W, rank):
    n_ = W.shape[0]
    v = 0.0
    for i in range(n_):
        for j in range(n_):
            if W[i,j] > 0 and rank[i] > rank[j]:
                v += W[i,j]
    return v

# JIT warm-up (small run)
print("compiling...")
_ = mvr_mcmc(W, init_order, 100, 5, 10, 0)
print("compiled.\n")

init_rank = np.empty(n, dtype=np.int64)
for k in range(n):
    init_rank[init_order[k]] = k
v_init = violations(W, init_rank)
print(f"violations under SpringRank ordering: {v_init:.0f} / {W.sum():.0f} ({100*v_init/W.sum():.1f}%)")

# 4 chains × 1M iterations × 200 samples each
print("\nRunning 4 chains × 1,000,000 iterations ...")
t0 = time.time()
all_samples = []
for c in range(4):
    s = mvr_mcmc(W, init_order, 1_000_000, 200, 200_000, c)
    fv = violations(W, s[-1])
    print(f"  chain {c}: final violations {fv:.0f} ({100*fv/W.sum():.2f}%)")
    all_samples.append(s)
print(f"  total time: {time.time()-t0:.1f}s")
all_samples = np.concatenate(all_samples, axis=0)
print(f"  total samples: {all_samples.shape}\n")

mean_rank = all_samples.mean(axis=0)
std_rank  = all_samples.std(axis=0)
print(f"rank range: [{mean_rank.min():.1f}, {mean_rank.max():.1f}]")
print(f"median std: {np.median(std_rank):.2f},  max std: {std_rank.max():.2f}")

rng_ = mean_rank.max() - mean_rank.min()
K = max(2, int(round(rng_ / (2 * np.median(std_rank)))))
print(f"K suggested by uncertainty: {K}")

km = KMeans(n_clusters=K, random_state=0, n_init=20).fit(mean_rank.reshape(-1,1))
order_layers = {old:new for new,old in enumerate(np.argsort(km.cluster_centers_.flatten()))}
layer = np.array([order_layers[l] for l in km.labels_])

out = pd.DataFrame({
    'position': positions,
    'mvr_mean_rank': mean_rank,
    'mvr_std_rank':  std_rank,
    'mvr_layer':     layer,
})
out['true_level'] = out['position'].map(ranks.set_index('position')['true_level'])
out['n_records']  = out['position'].map(records['position'].value_counts())

level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
out['true_rank_num'] = out['true_level'].map(level_order)
v = out.dropna(subset=['true_rank_num'])
sp,_ = spearmanr(v['mvr_mean_rank'], v['true_rank_num'])
kt,_ = kendalltau(v['mvr_mean_rank'], v['true_rank_num'])
print(f"\n=== Validation (n={len(v)}) ===")
print(f"  Spearman ρ = {sp:.3f}    Kendall τ = {kt:.3f}")

print("\n=== Mean MVR rank by 级别 ===")
print(v.groupby('true_level')['mvr_mean_rank'].agg(['mean','std','count']).reindex(level_order.keys()).dropna())

print(f"\n=== Layer × 级别 confusion (K={K}) ===")
ct = pd.crosstab(v['mvr_layer'], v['true_level'])
ct = ct.reindex(columns=[c for c in level_order.keys() if c in ct.columns])
print(ct)

out.to_pickle('mvr_ranks.pkl')
print("\n→ saved mvr_ranks.pkl")
