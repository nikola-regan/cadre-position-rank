"""
SpringRank rank estimation (De Bacco, Larremore, Moore 2018).
Edge i→j (career move from position i to position j) implies s_j ≈ s_i + 1.
Solve sparse linear system to get ranks.
"""
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix, identity, diags
from scipy.sparse.linalg import spsolve
from collections import defaultdict

edges = pd.read_pickle('edges.pkl')
pos_rank = pd.read_pickle('pos_rank.pkl')
records = pd.read_pickle('records.pkl')

# 1. Index positions
positions = sorted(set(edges['from']).union(set(edges['to'])))
idx = {p:i for i,p in enumerate(positions)}
n = len(positions)
print(f"n positions: {n}")

# 2. Build adjacency matrix
A = np.zeros((n, n))
for _, r in edges.iterrows():
    A[idx[r['from']], idx[r['to']]] += r['w']

# 3. SpringRank linear system
# L s = b where
#   L[k,k] = d_in[k] + d_out[k] + alpha
#   L[k,i] = -(A[i,k] + A[k,i])  for i != k
#   b[k]   = d_in[k] - d_out[k]
d_out = A.sum(axis=1)   # row sum
d_in  = A.sum(axis=0)   # col sum

alpha = 0.1   # regularization
L = -(A + A.T)
np.fill_diagonal(L, d_in + d_out + alpha)
b = d_in - d_out

s = np.linalg.solve(L, b)

# 4. Center
s = s - s.mean()
print(f"rank range: [{s.min():.3f}, {s.max():.3f}]")
print(f"rank std:   {s.std():.3f}")

# 5. Save with position labels
out = pd.DataFrame({'position': positions, 'spring_rank': s})
out['true_level'] = out['position'].map(pos_rank)
out['n_records'] = out['position'].map(records['position'].value_counts())
out.to_pickle('ranks.pkl')

# 6. Validation: rank vs 级别
level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
out['true_rank_num'] = out['true_level'].map(level_order)

valid = out.dropna(subset=['true_rank_num'])
from scipy.stats import spearmanr, kendalltau
sp, sp_p = spearmanr(valid['spring_rank'], valid['true_rank_num'])
kt, kt_p = kendalltau(valid['spring_rank'], valid['true_rank_num'])
print()
print(f"=== Validation against 行政级别 ({len(valid)} positions) ===")
print(f"Spearman ρ = {sp:.3f}  (p = {sp_p:.2e})")
print(f"Kendall τ  = {kt:.3f}  (p = {kt_p:.2e})")

# Mean spring_rank by 级别
print("\n=== Mean SpringRank by 级别 ===")
print(valid.groupby('true_level')['spring_rank'].agg(['mean','std','count']).reindex(level_order.keys()).dropna())
