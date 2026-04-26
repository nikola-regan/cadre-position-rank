"""
Build position-level transition network from CPED senior_sample.
Position node = (admin_level, org_type, 职务一级关键词, normalized_具体职务)
"""
import pandas as pd
import numpy as np
import re

df = pd.read_pickle('senior_sample.pkl').reset_index(drop=True)

# --- 1. Admin level -----------------------------------------------------
def admin_level(row):
    if row['是否全国性组织'] == '是':
        return '中央'
    dq = row['地区级别']
    if pd.isna(dq):
        return '省级'      # 默认: 在省份字段下且无 地区级别 → 省级
    if dq == '副省级城市':
        return '副省级市'
    if dq == '地级市（区）':
        return '地级市'
    return '其他'

df['admin'] = df.apply(admin_level, axis=1)
print("admin level distribution:")
print(df['admin'].value_counts())
print()

# --- 2. Title normalization --------------------------------------------
def normalize_title(t):
    if pd.isna(t): return None
    t = str(t).strip()
    # 去掉并列附属头衔(党组成员、党委委员、副秘书长 这类作为后缀)
    t = re.split(r'[、，,]', t)[0]
    t = t.strip()
    # 一些常见同义合并
    repl = {
        '代市长': '市长',
        '代省长': '省长',
        '代理市长': '市长',
        '代理省长': '省长',
    }
    return repl.get(t, t)

df['title'] = df['具体职务'].apply(normalize_title)

# --- 3. Position ID ----------------------------------------------------
df['position'] = (
    df['admin'].astype(str) + '|' +
    df['基本大类别'].astype(str) + '|' +
    df['职务一级关键词'].astype(str) + '|' +
    df['title'].astype(str)
)

# Drop positions with NaN/None title
df = df[df['title'].notna()].copy()

# --- 4. Position frequency ---------------------------------------------
pos_counts = df['position'].value_counts()
print(f"Total unique positions: {len(pos_counts)}")
print(f"Positions with >= 5 records: {(pos_counts >= 5).sum()}")
print(f"Positions with >= 10 records: {(pos_counts >= 10).sum()}")
print()

# Keep only positions with >= 3 records to reduce noise
keep = set(pos_counts[pos_counts >= 3].index)
df = df[df['position'].isin(keep)].copy()
print(f"After filter (>=3): {df['position'].nunique()} positions, {len(df)} records")
print()

# --- 5. Build transitions ----------------------------------------------
df = df.sort_values(['用户编码','经历序号'])

trans = []
for uid, g in df.groupby('用户编码'):
    rows = g.to_dict('records')
    for i in range(len(rows)-1):
        a, b = rows[i], rows[i+1]
        if a['position'] == b['position']:
            continue  # 同岗位连续记录跳过
        trans.append({
            'from': a['position'],
            'to':   b['position'],
            'from_rank': a['级别'],
            'to_rank':   b['级别'],
        })

trans_df = pd.DataFrame(trans)
print(f"Total transitions: {len(trans_df)}")

# Edge weights
edge_w = trans_df.groupby(['from','to']).size().reset_index(name='w')
print(f"Unique directed edges: {len(edge_w)}")
print()

# --- 6. Position → 级别 mapping (for validation later) -----------------
# 一个 position 可能横跨多个级别(因为同一职位在不同年代/地区编码可能不一致),取 mode
pos_rank = df.groupby('position')['级别'].agg(lambda x: x.mode().iloc[0] if len(x.mode())>0 else None)
print(f"positions with assigned 级别: {pos_rank.notna().sum()}")
print()
print("级别 across positions:")
print(pos_rank.value_counts())

# Save
edge_w.to_pickle('edges.pkl')
pos_rank.to_pickle('pos_rank.pkl')
df[['用户编码','经历序号','position','级别','admin','基本大类别','title']].to_pickle('records.pkl')
print("\n→ saved edges.pkl, pos_rank.pkl, records.pkl")
