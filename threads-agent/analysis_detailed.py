# -*- coding: utf-8 -*-
import json
from statistics import mean, median, stdev
from collections import Counter
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data_path = 'data/post_history.json'
with open(data_path, 'r', encoding='utf-8') as f:
    posts = json.load(f)

print("\n" + "=" * 80)
print("【詳細分析：トップパフォーマーの共通特性】")
print("=" * 80)

# トップ10と全体の比較
top_10 = sorted(posts, key=lambda p: p.get('metrics_24h', {}).get('likes', 0), reverse=True)[:10]
bottom_10 = sorted(posts, key=lambda p: p.get('metrics_24h', {}).get('likes', 0))[:10]
all_posts = posts

def get_stats(post_list):
    chars = [len(p['content']) for p in post_list]
    lines = [p['content'].count('\n') for p in post_list]
    likes = [p.get('metrics_24h', {}).get('likes', 0) for p in post_list]
    views = [p.get('metrics_24h', {}).get('views', 0) for p in post_list]

    # フック分析
    hooks = Counter()
    for p in post_list:
        first = p['content'].split('\n')[0]
        if '？' in first or '?' in first:
            hooks['質問'] += 1
        elif re.match(r'^\d+', first):
            hooks['数字'] += 1
        elif any(w in first for w in ['実は', '今日', '昨日', '最近']):
            hooks['意外性'] += 1
        else:
            hooks['宣言'] += 1

    # パターン
    patterns = Counter([p.get('pattern', 'unknown') for p in post_list])

    # 表現形式
    list_fmt = sum(1 for p in post_list if any(s in p['content'] for s in ['・', '①', '1.']))

    return {
        'avg_chars': mean(chars) if chars else 0,
        'avg_lines': mean(lines) if lines else 0,
        'avg_likes': mean(likes) if likes else 0,
        'avg_views': mean(views) if views else 0,
        'top_pattern': patterns.most_common(1)[0][0] if patterns else 'none',
        'top_hook': hooks.most_common(1)[0][0] if hooks else 'none',
        'list_rate': list_fmt / len(post_list) * 100 if post_list else 0,
    }

top_stats = get_stats(top_10)
all_stats = get_stats(all_posts)
bottom_stats = get_stats(bottom_10)

print("\n## 比較：トップ10 vs 全体 vs ボトム10")
print("\n| 指標 | トップ10 | 全体平均 | ボトム10 |")
print("|---|---|---|---|")
print("| 平均文字数 | {:.0f}字 | {:.0f}字 | {:.0f}字 |".format(top_stats['avg_chars'], all_stats['avg_chars'], bottom_stats['avg_chars']))
print("| 平均改行数 | {:.1f}回 | {:.1f}回 | {:.1f}回 |".format(top_stats['avg_lines'], all_stats['avg_lines'], bottom_stats['avg_lines']))
print("| 平均いいね | {:.2f}個 | {:.2f}個 | {:.2f}個 |".format(top_stats['avg_likes'], all_stats['avg_likes'], bottom_stats['avg_likes']))
print("| 平均ビュー | {:.0f} | {:.0f} | {:.0f} |".format(top_stats['avg_views'], all_stats['avg_views'], bottom_stats['avg_views']))
print("| 最多パターン | {} | {} | {} |".format(top_stats['top_pattern'], all_stats['top_pattern'], bottom_stats['top_pattern']))
print("| 最多フック | {} | {} | {} |".format(top_stats['top_hook'], all_stats['top_hook'], bottom_stats['top_hook']))
print("| リスト形式率 | {:.0f}% | {:.0f}% | {:.0f}% |".format(top_stats['list_rate'], all_stats['list_rate'], bottom_stats['list_rate']))

# トップ5の詳細構成
print("\n\n## トップ5投稿の内部構造（段落の流れ）")

for i, p in enumerate(sorted(posts, key=lambda p: p.get('metrics_24h', {}).get('likes', 0), reverse=True)[:5], 1):
    likes = p.get('metrics_24h', {}).get('likes', 0)
    lines = p['content'].split('\n')

    print("\n{}. いいね {} | {}パターン".format(i, likes, p.get('pattern', '?')))
    print("   【段落構成】")

    # 最初の段落と最後の段落を表示
    para = []
    for j, line in enumerate(lines[:5]):
        if line.strip():
            para.append(line[:60])

    for j, line in enumerate(para[:3]):
        print("   {}. {}...".format(j+1, line))

# パターン別の詳細分析
print("\n\n## パターン別の成功因子分析")

pattern_success = {}
for p in posts:
    pname = p.get('pattern', 'unknown')
    likes = p.get('metrics_24h', {}).get('likes', 0)

    if pname not in pattern_success:
        pattern_success[pname] = {'likes': [], 'views': [], 'chars': [], 'lines': []}

    pattern_success[pname]['likes'].append(likes)
    pattern_success[pname]['views'].append(p.get('metrics_24h', {}).get('views', 0))
    pattern_success[pname]['chars'].append(len(p['content']))
    pattern_success[pname]['lines'].append(p['content'].count('\n'))

print("\n最も成功しているパターン（平均いいね順）：")
sorted_patterns = sorted(pattern_success.items(),
                        key=lambda x: mean(x[1]['likes']) if x[1]['likes'] else 0,
                        reverse=True)

for pname, stats in sorted_patterns[:5]:
    avg_likes = mean(stats['likes']) if stats['likes'] else 0
    avg_views = mean(stats['views']) if stats['views'] else 0
    avg_chars = mean(stats['chars']) if stats['chars'] else 0
    count = len(stats['likes'])

    if avg_likes > 0 or count == 1:  # いいね獲得 or 少数サンプル
        print("- {0}：{1}件 | 平均いいね{2:.2f} | 平均ビュー{3:.0f} | 平均文字数{4:.0f}".format(
            pname, count, avg_likes, avg_views, avg_chars))

# キーインサイト
print("\n\n## キーインサイト")

print("\n【冒頭フック - 勝率の詳細】")
hooks_detail = {}
for p in posts:
    first = p['content'].split('\n')[0]
    likes = p.get('metrics_24h', {}).get('likes', 0)
    views = p.get('metrics_24h', {}).get('views', 0)

    if '？' in first or '?' in first:
        htype = '質問'
    elif re.match(r'^\d+', first):
        htype = '数字'
    elif any(w in first for w in ['実は', '今日', '昨日', '最近']):
        htype = '意外性'
    else:
        htype = '宣言'

    if htype not in hooks_detail:
        hooks_detail[htype] = {'likes': [], 'views': []}

    hooks_detail[htype]['likes'].append(likes)
    hooks_detail[htype]['views'].append(views)

for htype in sorted(hooks_detail.keys(), key=lambda x: mean(hooks_detail[x]['likes']), reverse=True):
    data = hooks_detail[htype]
    avg_likes = mean(data['likes'])
    avg_views = mean(data['views'])
    count = len(data['likes'])
    win_rate = sum(1 for l in data['likes'] if l > 0) / len(data['likes']) * 100 if data['likes'] else 0

    print("- {0}形式：{1}件 | 平均いいね{2:.2f} | 平均ビュー{3:.0f} | いいね獲得率{4:.0f}%".format(
        htype, count, avg_likes, avg_views, win_rate))

# 最高パフォーマー群の共通点
print("\n\n【最高パフォーマー（いいね≥1）の共通特性】")
winners = [p for p in posts if p.get('metrics_24h', {}).get('likes', 0) >= 1]

print("- 該当投稿数：{}件（全体の{:.1f}%）".format(len(winners), len(winners)/len(posts)*100))

if winners:
    w_chars = [len(p['content']) for p in winners]
    w_lines = [p['content'].count('\n') for p in winners]
    w_patterns = Counter([p.get('pattern', '?') for p in winners])

    print("- 平均文字数：{:.0f}字（全体：{:.0f}字）".format(mean(w_chars), mean([len(p['content']) for p in posts])))
    print("- 平均改行数：{:.1f}回（全体：{:.1f}回）".format(mean(w_lines), mean([p['content'].count('\n') for p in posts])))
    print("- 最多パターン：{}（{}件）".format(w_patterns.most_common(1)[0][0], w_patterns.most_common(1)[0][1]))

    # 冒頭フック
    w_hooks = Counter()
    for p in winners:
        first = p['content'].split('\n')[0]
        if '？' in first or '?' in first:
            w_hooks['質問'] += 1
        elif re.match(r'^\d+', first):
            w_hooks['数字'] += 1
        elif any(w in first for w in ['実は', '今日']):
            w_hooks['意外性'] += 1
        else:
            w_hooks['宣言'] += 1

    print("- 最多フック：{}（{}件）".format(w_hooks.most_common(1)[0][0], w_hooks.most_common(1)[0][1]))

print("\n" + "=" * 80)
