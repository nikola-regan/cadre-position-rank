"""
1. K-means clustering into layers
2. Identify deviations: positions whose SpringRank differs most from their 级别
3. Generate plots
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from sklearn.cluster import KMeans

# Try to use a CJK font if available
for fp in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
           '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
           '/usr/share/fonts/truetype/arphic/uming.ttc']:
    try:
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.family'] = ['Noto Sans CJK JP','WenQuanYi Micro Hei','AR PL UMing CN','DejaVu Sans']
        break
    except Exception:
        pass
plt.rcParams['axes.unicode_minus'] = False

ranks = pd.read_pickle('ranks.pkl')

level_order = {'小于副处':0,'副处':1,'正处':2,'副厅':3,'正厅':4,'副部':5,'正部':6,'副国':7,'正国':8}
ranks['true_rank_num'] = ranks['true_level'].map(level_order)
valid = ranks.dropna(subset=['true_rank_num']).copy()

# --- 1. K-means into layers --------------------------------------------
# Try K=7 (matching 副厅..正国)
ks = [5, 7, 9, 11]
inertias = []
for k in ks:
    km = KMeans(n_clusters=k, random_state=0, n_init=10).fit(valid[['spring_rank']])
    inertias.append(km.inertia_)
print("K-means inertias:")
for k,i in zip(ks,inertias):
    print(f"  K={k}: {i:.2f}")
print()

# Final clustering with K=7
km7 = KMeans(n_clusters=7, random_state=0, n_init=10).fit(valid[['spring_rank']])
valid['layer'] = km7.labels_
# Re-label layers in increasing rank order (0=lowest, 6=highest)
layer_means = valid.groupby('layer')['spring_rank'].mean().sort_values()
relabel = {old:new for new,old in enumerate(layer_means.index)}
valid['layer'] = valid['layer'].map(relabel)

print("=== Layer composition (k=7) ===")
ct = pd.crosstab(valid['layer'], valid['true_level'])
ct = ct.reindex(columns=[c for c in level_order.keys() if c in ct.columns])
print(ct)
print()

# --- 2. Deviation analysis -----------------------------------------------
# For each 级别, compute mean & std SpringRank, then z-score each position
mu = valid.groupby('true_level')['spring_rank'].transform('mean')
sd = valid.groupby('true_level')['spring_rank'].transform('std')
valid['z_dev'] = (valid['spring_rank'] - mu) / sd

# Top positions over- and under-ranked relative to their 级别
print("=== Top 15 positions OVER-ranked (estimated rank > formal level) ===")
top_over = valid.nlargest(15, 'z_dev')[['position','true_level','spring_rank','z_dev','n_records']]
for _,r in top_over.iterrows():
    print(f"  z={r['z_dev']:+.2f}  s={r['spring_rank']:+.2f}  级别={r['true_level']}  n={int(r['n_records'])}  | {r['position']}")
print()
print("=== Top 15 positions UNDER-ranked (estimated rank < formal level) ===")
top_under = valid.nsmallest(15, 'z_dev')[['position','true_level','spring_rank','z_dev','n_records']]
for _,r in top_under.iterrows():
    print(f"  z={r['z_dev']:+.2f}  s={r['spring_rank']:+.2f}  级别={r['true_level']}  n={int(r['n_records'])}  | {r['position']}")

# --- 3. Plots ------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

# Plot A: SpringRank by 级别 (boxplot)
order = ['正处','副厅','正厅','副部','正部','副国','正国']
data = [valid[valid['true_level']==lv]['spring_rank'].values for lv in order]
bp = axes[0].boxplot(data, labels=order, patch_artist=True)
for patch, color in zip(bp['boxes'], plt.cm.viridis(np.linspace(0.15, 0.85, len(order)))):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
axes[0].set_xlabel('Formal Rank (CPED 级别)')
axes[0].set_ylabel('SpringRank (estimated)')
axes[0].set_title(f'Estimated rank vs formal level\nSpearman ρ = 0.886, n = {len(valid)} positions')
axes[0].grid(alpha=0.3)

# Plot B: layer composition
ct_pct = ct.div(ct.sum(axis=1), axis=0) * 100
ct_pct.plot(kind='barh', stacked=True, ax=axes[1], colormap='viridis', width=0.8)
axes[1].set_xlabel('% of positions in layer')
axes[1].set_ylabel('Estimated layer (k-means, K=7)')
axes[1].set_title('Composition of estimated layers by formal rank')
axes[1].legend(title='Formal rank', bbox_to_anchor=(1.02,1), loc='upper left', fontsize=8)
axes[1].grid(alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('validation_plots.png', dpi=140, bbox_inches='tight')
print("\n→ saved validation_plots.png")

# Save deviation table
valid_out = valid[['position','true_level','spring_rank','z_dev','layer','n_records']].sort_values('spring_rank', ascending=False)
valid_out.to_csv('positions_ranked.csv', index=False)
print("→ saved positions_ranked.csv")
