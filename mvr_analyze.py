"""Compare MVR vs SpringRank, plot uncertainty, identify high-uncertainty roles."""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf')
plt.rcParams['font.family'] = ['Droid Sans Fallback']
plt.rcParams['axes.unicode_minus'] = False

mvr = pd.read_pickle('mvr_ranks.pkl')
sr  = pd.read_pickle('ranks.pkl')

m = mvr.merge(sr[['position','spring_rank']], on='position')

level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
m['true_rank_num'] = m['true_level'].map(level_order)
v = m.dropna(subset=['true_rank_num']).copy()

# --- Deviation analysis with MVR ranks, weighted by inverse uncertainty
# z_dev = (mvr_rank - mean_at_level) / std_at_level
mu = v.groupby('true_level')['mvr_mean_rank'].transform('mean')
sd = v.groupby('true_level')['mvr_mean_rank'].transform('std')
v['z_dev'] = (v['mvr_mean_rank'] - mu) / sd

# Robust deviation: weight by inverse rank uncertainty
v['z_dev_robust'] = v['z_dev'] / (v['mvr_std_rank']/v['mvr_std_rank'].median())

# --- 4-panel plot ---
fig, axes = plt.subplots(2, 2, figsize=(15, 11))

# A. SpringRank vs MVR scatter (sanity check both methods agree)
ax = axes[0,0]
sc = ax.scatter(v['spring_rank'], v['mvr_mean_rank'], c=v['true_rank_num'],
                cmap='viridis', s=20, alpha=0.7)
ax.set_xlabel('SpringRank (连续值)')
ax.set_ylabel('MVR Mean Rank (位次,0–469)')
ax.set_title(f'两种方法的 rank 估计对比\n(SpearmanCorr({len(v)}) = {v["spring_rank"].corr(v["mvr_mean_rank"], method="spearman"):.3f})')
plt.colorbar(sc, ax=ax, label='行政级别(数值)', ticks=[0,1,2,3,4,5,6,7,8])
ax.grid(alpha=0.3)

# B. Rank uncertainty distribution
ax = axes[0,1]
for lv, color in zip(['副厅','正厅','副部','正部','副国'],
                     plt.cm.viridis(np.linspace(0.2, 0.85, 5))):
    sub = v[v['true_level']==lv]['mvr_std_rank']
    ax.hist(sub, bins=30, alpha=0.55, color=color, label=f'{lv} (n={len(sub)})')
ax.set_xlabel('MVR Rank Std Dev (rank uncertainty)')
ax.set_ylabel('# 岗位')
ax.set_title(f'每个岗位的 rank 不确定性\n中位数 std = {v["mvr_std_rank"].median():.1f} (满程 469)')
ax.legend(fontsize=9)
ax.grid(alpha=0.3)

# C. MVR mean rank ± std by 级别
ax = axes[1,0]
order_lv = ['正处','副厅','正厅','副部','正部','副国','正国']
for i, lv in enumerate(order_lv):
    sub = v[v['true_level']==lv]
    if len(sub) == 0: continue
    x = np.full(len(sub), i) + np.random.RandomState(i).uniform(-0.18, 0.18, len(sub))
    ax.errorbar(x, sub['mvr_mean_rank'], yerr=sub['mvr_std_rank'],
                fmt='o', alpha=0.5, markersize=3, capsize=0,
                color=plt.cm.viridis(i/len(order_lv)))
ax.set_xticks(range(len(order_lv)))
ax.set_xticklabels(order_lv)
ax.set_xlabel('行政级别')
ax.set_ylabel('MVR Mean Rank (含标准差 errorbar)')
ax.set_title(f'每个岗位的估计 rank ± 不确定性\nSpearman ρ = 0.881')
ax.grid(alpha=0.3)

# D. K=13 layer composition
ct = pd.crosstab(v['mvr_layer'], v['true_level'])
ct = ct.reindex(columns=[c for c in level_order.keys() if c in ct.columns])
ct_pct = ct.div(ct.sum(axis=1), axis=0) * 100
ct_pct.plot(kind='barh', stacked=True, ax=axes[1,1], colormap='viridis', width=0.85)
axes[1,1].set_xlabel('该层岗位占比(%)')
axes[1,1].set_ylabel('MVR 聚类层 (K=13,0=最低)')
axes[1,1].set_title(f'K=13 层 (由 rank 不确定性决定) × 行政级别')
axes[1,1].legend(title='行政级别', bbox_to_anchor=(1.02,1), loc='upper left', fontsize=8)
axes[1,1].grid(alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('mvr_results.png', dpi=140, bbox_inches='tight')
print("→ saved mvr_results.png")

# --- High uncertainty positions (likely lateral move hubs / boundary positions)
print("\n=== Top 15 岗位 with HIGHEST rank uncertainty (lateral hubs) ===")
high_u = v.nlargest(15, 'mvr_std_rank')[['position','true_level','mvr_mean_rank','mvr_std_rank','n_records']]
for _, r in high_u.iterrows():
    print(f"  std={r['mvr_std_rank']:5.1f}  rank={r['mvr_mean_rank']:6.1f}  级别={r['true_level']}  n={int(r['n_records']):3d}  | {r['position']}")

# --- Deviation top picks with uncertainty caveats
print("\n=== Top 10 OVER-ranked (z>0) with LOW uncertainty (high-confidence outliers) ===")
robust_over = v[v['mvr_std_rank'] < v['mvr_std_rank'].median()].nlargest(10, 'z_dev')
for _, r in robust_over.iterrows():
    print(f"  z={r['z_dev']:+.2f}  rank={r['mvr_mean_rank']:6.1f}±{r['mvr_std_rank']:.1f}  级别={r['true_level']}  | {r['position']}")

print("\n=== Top 10 UNDER-ranked (z<0) with LOW uncertainty (high-confidence stepping stones) ===")
robust_under = v[v['mvr_std_rank'] < v['mvr_std_rank'].median()].nsmallest(10, 'z_dev')
for _, r in robust_under.iterrows():
    print(f"  z={r['z_dev']:+.2f}  rank={r['mvr_mean_rank']:6.1f}±{r['mvr_std_rank']:.1f}  级别={r['true_level']}  | {r['position']}")

v[['position','true_level','mvr_mean_rank','mvr_std_rank','mvr_layer','z_dev','n_records']].sort_values('mvr_mean_rank', ascending=False).to_csv('mvr_positions_ranked.csv', index=False)
print("\n→ saved mvr_positions_ranked.csv")
