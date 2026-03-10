#!/usr/bin/env python3
"""
generate_stats.py 完全刷新版 v2
- 全 race_results_*.json を自動検出して集計
- score_tier 別・仮想収支集計を追加
- 日付範囲を自動取得
- ロジックバージョン別集計を追加（by_logic_version）
- final_predictions_YYYYMMDD.json から logic_version を読み取り
- venue / track の空文字バグ修正
"""
import json
import requests
from datetime import datetime
from collections import defaultdict
import os

BASE_URL = "https://raw.githubusercontent.com/aipapa247272/keiba-auto-gist-updater/main/"

# ロジックバージョンの日付マッピング（日付→バージョン）
# final_predictions から読み取れない場合のフォールバック
LOGIC_VERSION_DATES = {
    "v13.1": "20260306",   # 2026-03-06以降
    "v13.0": "20260227",   # 2026-02-27〜03-05
    "v12以前": "20260101", # 〜2026-02-26
}

def get_logic_version_by_date(ymd):
    """日付からロジックバージョンを推定（フォールバック用）"""
    if ymd >= "20260306":
        return "v13.1"
    elif ymd >= "20260227":
        return "v13.0"
    else:
        return "v12以前"


def fetch_logic_versions():
    """GitHubから全final_predictions_*.jsonのlogic_versionを取得"""
    api_url = "https://api.github.com/repos/aipapa247272/keiba-auto-gist-updater/contents/"
    version_map = {}  # ymd -> logic_version

    try:
        resp = requests.get(api_url, timeout=15)
        files = resp.json()
        pred_files = sorted([
            f['name'] for f in files
            if isinstance(f, dict)
            and f.get('name','').startswith('final_predictions_202')
            and f.get('name','').endswith('.json')
        ])
        print(f"📋 予想ファイル検出: {len(pred_files)} 件")
    except Exception as e:
        print(f"⚠️ 予想ファイル一覧取得失敗: {e}")
        return version_map

    for fname in pred_files:
        ymd = fname.replace('final_predictions_', '').replace('.json', '')
        url = f"{BASE_URL}{fname}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                lv = data.get('logic_version', '')
                if lv:
                    # バージョン文字列を短縮（例: "v13.1_断層・合成オッズ対応..." → "v13.1"）
                    short_lv = lv.split('_')[0] if '_' in lv else lv
                    version_map[ymd] = short_lv
                else:
                    version_map[ymd] = get_logic_version_by_date(ymd)
        except Exception:
            version_map[ymd] = get_logic_version_by_date(ymd)

    return version_map


def fetch_all_results():
    """GitHubから全結果JSONを自動検出して取得"""
    api_url = "https://api.github.com/repos/aipapa247272/keiba-auto-gist-updater/contents/"
    all_data = []

    try:
        resp = requests.get(api_url, timeout=15)
        files = resp.json()
        result_files = sorted([
            f['name'] for f in files
            if isinstance(f, dict)
            and f.get('name','').startswith('race_results_202')
            and f.get('name','').endswith('.json')
            and not f.get('name','').startswith('race_results_00')
        ])
        print(f"📂 検出: {len(result_files)} 件の結果ファイル")
    except Exception as e:
        print(f"❌ ファイル一覧取得失敗: {e}")
        return []

    for fname in result_files:
        ymd = fname.replace('race_results_', '').replace('.json', '')
        url = f"{BASE_URL}{fname}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if not data.get('ymd'):
                    data['ymd'] = ymd
                if not data.get('date'):
                    data['date'] = f"{ymd[:4]}/{ymd[4:6]}/{ymd[6:]}"
                all_data.append(data)
                races = data.get('total_races', len(data.get('races', [])))
                hits  = data.get('hit_count', 0)
                print(f"  ✅ {ymd}: {races}R / 的中{hits}")
            else:
                print(f"  ⚠️ {ymd}: HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ {ymd}: {e}")

    return all_data


def calculate_statistics(all_data, version_map):
    """統計情報を計算（ロジックバージョン別・venue/trackバグ修正版）"""

    total_races = 0
    total_hits  = 0
    total_investment = 0
    total_return     = 0

    daily_stats   = []
    venue_stats   = defaultdict(lambda: {"races":0,"hits":0,"investment":0,"return":0})
    track_stats   = defaultdict(lambda: {"races":0,"hits":0,"investment":0,"return":0})
    tier_stats    = defaultdict(lambda: {"races":0,"hits":0,"investment":0,"return":0})
    # ロジックバージョン別集計
    logic_stats   = defaultdict(lambda: {
        "races":0,"hits":0,"investment":0,"return":0,
        "dates": []  # 対象日付リスト
    })

    vb_stats = defaultdict(lambda: {"count":0,"hits":0,"investment":0,"return":0})

    for day_data in sorted(all_data, key=lambda d: d.get('ymd','99999999')):
        date = day_data.get('date', '')
        ymd  = day_data.get('ymd', '')

        day_races      = day_data.get('total_races', 0)
        day_hits       = day_data.get('hit_count',  0)
        day_investment = day_data.get('total_investment', 0)
        day_return     = day_data.get('total_return', 0)
        day_profit     = day_data.get('total_profit', day_return - day_investment)

        total_races      += day_races
        total_hits       += day_hits
        total_investment += day_investment
        total_return     += day_return

        # ロジックバージョンを特定
        logic_ver = version_map.get(ymd, get_logic_version_by_date(ymd))

        daily_stats.append({
            'date':          date,
            'ymd':           ymd,
            'logic_version': logic_ver,
            'races':         day_races,
            'hits':          day_hits,
            'investment':    day_investment,
            'return':        day_return,
            'profit':        day_profit,
            'hit_rate':      round((day_hits/day_races*100) if day_races>0 else 0, 1),
            'recovery_rate': round((day_return/day_investment*100) if day_investment>0 else 0, 1)
        })

        # ロジックバージョン別集計
        logic_stats[logic_ver]['races']      += day_races
        logic_stats[logic_ver]['hits']       += day_hits
        logic_stats[logic_ver]['investment'] += day_investment
        logic_stats[logic_ver]['return']     += day_return
        if ymd and ymd not in logic_stats[logic_ver]['dates']:
            logic_stats[logic_ver]['dates'].append(ymd)

        for race in day_data.get('races', []):
            # venue/track: 空文字・Noneの場合は'不明'に補完（バグ修正）
            venue  = race.get('venue', '') or '不明'
            track  = race.get('track', '') or '不明'
            tier   = race.get('score_tier', '?') or '?'
            hit    = 1 if race.get('hit', False) else 0
            inv    = race.get('investment', 0)
            ret    = race.get('return', 0)

            venue_stats[venue]['races']      += 1
            venue_stats[venue]['hits']       += hit
            venue_stats[venue]['investment'] += inv
            venue_stats[venue]['return']     += ret

            track_stats[track]['races']      += 1
            track_stats[track]['hits']       += hit
            track_stats[track]['investment'] += inv
            track_stats[track]['return']     += ret

            tier_stats[tier]['races']        += 1
            tier_stats[tier]['hits']         += hit
            tier_stats[tier]['investment']   += inv
            tier_stats[tier]['return']       += ret

            for key, vb in race.get('virtual_bets_result', {}).items():
                vb_stats[key]['count']      += 1
                vb_stats[key]['hits']       += 1 if vb.get('的中') else 0
                vb_stats[key]['investment'] += vb.get('投資', 100)
                vb_stats[key]['return']     += vb.get('払戻', 0)

    # 整形ヘルパ
    def make_list(d, key_field):
        out = []
        for k, s in d.items():
            out.append({
                key_field:       k,
                'races':         s['races'],
                'hits':          s['hits'],
                'hit_rate':      round((s['hits']/s['races']*100) if s['races']>0 else 0, 1),
                'investment':    s['investment'],
                'return':        s['return'],
                'profit':        s['return'] - s['investment'],
                'recovery_rate': round((s['return']/s['investment']*100) if s['investment']>0 else 0, 1)
            })
        out.sort(key=lambda x: x['races'], reverse=True)
        return out

    # ロジックバージョン別リスト（最新版が先頭）
    logic_list = []
    # バージョン番号で降順ソート
    version_order = {"v13.1": 0, "v13.0": 1, "v12以前": 2}
    for k, s in sorted(logic_stats.items(),
                        key=lambda x: version_order.get(x[0], 99)):
        dates_sorted = sorted(s['dates'])
        period_start = dates_sorted[0] if dates_sorted else ''
        period_end   = dates_sorted[-1] if dates_sorted else ''
        period_str   = f"{period_start[:4]}/{period_start[4:6]}/{period_start[6:]} 〜 {period_end[:4]}/{period_end[4:6]}/{period_end[6:]}" \
                       if period_start else ''
        logic_list.append({
            'logic_version': k,
            'period':        period_str,
            'active_days':   len(s['dates']),
            'races':         s['races'],
            'hits':          s['hits'],
            'hit_rate':      round((s['hits']/s['races']*100) if s['races']>0 else 0, 1),
            'investment':    s['investment'],
            'return':        s['return'],
            'profit':        s['return'] - s['investment'],
            'recovery_rate': round((s['return']/s['investment']*100) if s['investment']>0 else 0, 1)
        })

    # 最新ロジック（先頭）の統計を latest_logic_overall として別出し
    latest_logic_overall = logic_list[0] if logic_list else {}

    # 仮想収支リスト
    vb_list = []
    for k, s in vb_stats.items():
        vb_list.append({
            'bet_type':      k,
            'count':         s['count'],
            'hits':          s['hits'],
            'hit_rate':      round((s['hits']/s['count']*100) if s['count']>0 else 0, 1),
            'investment':    s['investment'],
            'return':        s['return'],
            'profit':        s['return'] - s['investment'],
            'recovery_rate': round((s['return']/s['investment']*100) if s['investment']>0 else 0, 1)
        })
    vb_list.sort(key=lambda x: x['recovery_rate'], reverse=True)

    overall_hit_rate = round((total_hits/total_races*100) if total_races>0 else 0, 1)
    overall_recovery = round((total_return/total_investment*100) if total_investment>0 else 0, 1)

    # ============================================================
    # A: verification_stats（自動ロジック検証サマリー累積統計）
    # ============================================================
    axis_in_top3_total    = 0
    axis_in_top3_count    = 0
    score_top1_in_top3_total = 0
    score_top1_count      = 0
    rule93_total          = 0.0
    rule93_count          = 0
    miss_pattern_dist     = {}
    upset_count           = 0
    upset_total           = 0
    odds_ratio_sum        = 0.0
    odds_ratio_count      = 0
    predicted_in_top3_sum = 0
    total_verify_races    = 0

    for day_data in all_data:
        for race in day_data.get('races', []):
            rv = race.get('race_verification', {})
            if not rv:
                continue
            total_verify_races += 1

            # 1. 軸馬3着以内率
            axis_in_top3_total += 1
            if rv.get('axis_in_top3', False):
                axis_in_top3_count += 1

            # 2. 93法則実績
            rate = rv.get('93rule_pop_in_top3_rate')
            if rate is not None:
                rule93_total += float(rate)
                rule93_count += 1

            # 3. スコアTop1 3着以内率
            if rv.get('score_top1_rank') is not None:
                score_top1_count += 1
                if rv.get('score_top1_in_top3', False):
                    score_top1_in_top3_total += 1

            # 4. 外れパターン分布
            mp = rv.get('miss_pattern', '不明')
            miss_pattern_dist[mp] = miss_pattern_dist.get(mp, 0) + 1

            # 5. 荒れ度
            upset_total += 1
            if rv.get('is_upset', False):
                upset_count += 1

            # 6. 合成オッズ精度
            ratio = rv.get('odds_ratio')
            if ratio is not None:
                odds_ratio_sum  += ratio
                odds_ratio_count += 1

            # 7. 上位3着内の予測馬数（平均）
            predicted_in_top3_sum += rv.get('predicted_in_top3_count', 0)

    verification_stats = {
        'total_verify_races': total_verify_races,
        'axis_in_top3_rate': round(
            axis_in_top3_count / axis_in_top3_total * 100, 1
        ) if axis_in_top3_total > 0 else 0.0,
        'score_top1_in_top3_rate': round(
            score_top1_in_top3_total / score_top1_count * 100, 1
        ) if score_top1_count > 0 else 0.0,
        '93rule_avg_rate': round(
            rule93_total / rule93_count, 1
        ) if rule93_count > 0 else 0.0,
        'miss_pattern_distribution': miss_pattern_dist,
        'upset_rate': round(
            upset_count / upset_total * 100, 1
        ) if upset_total > 0 else 0.0,
        'avg_odds_ratio': round(
            odds_ratio_sum / odds_ratio_count, 3
        ) if odds_ratio_count > 0 else None,
        'avg_predicted_in_top3': round(
            predicted_in_top3_sum / total_verify_races, 2
        ) if total_verify_races > 0 else 0.0,
        # 参考値: ideal は axis_in_top3 > 50%, score_top1 > 40%, 93rule > 70%
        'note': 'axis_in_top3 > 50%, score_top1_in_top3 > 40%, 93rule_avg > 70% が精度改善の目安'
    }

    return {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'overall': {
            'total_races':      total_races,
            'total_hits':       total_hits,
            'total_investment': total_investment,
            'total_return':     total_return,
            'total_profit':     total_return - total_investment,
            'hit_rate':         overall_hit_rate,
            'recovery_rate':    overall_recovery
        },
        'latest_logic_overall': latest_logic_overall,   # 最新ロジック単独統計
        'daily':                daily_stats,
        'by_logic_version':     logic_list,              # ★ロジックバージョン別
        'by_venue':             make_list(venue_stats, 'venue'),
        'by_track':             make_list(track_stats, 'track'),
        'by_score_tier':        make_list(tier_stats, 'tier'),
        'virtual_bets':         vb_list,
        'verification_stats':   verification_stats  # A: 自動ロジック検証サマリー累積統計
    }


if __name__ == '__main__':
    print("📊 統計データ生成開始...")

    print("\n📋 ロジックバージョン情報を取得中...")
    version_map = fetch_logic_versions()
    print(f"  → {len(version_map)} 件のバージョン情報を取得")

    all_data = fetch_all_results()

    if not all_data:
        print("❌ データが取得できませんでした")
        exit(1)

    stats = calculate_statistics(all_data, version_map)

    with open('statistics.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    o = stats['overall']
    print(f"\n{'='*50}")
    print(f"📊 全体統計 ({len(all_data)}日分)")
    print(f"{'='*50}")
    print(f"総レース数: {o['total_races']}R")
    print(f"的中数:     {o['total_hits']}R  ({o['hit_rate']}%)")
    print(f"投資額:     ¥{o['total_investment']:,}")
    print(f"払戻額:     ¥{o['total_return']:,}")
    print(f"収支:       ¥{o['total_profit']:,}")
    print(f"回収率:     {o['recovery_rate']}%")
    print(f"{'='*50}")

    if stats.get('by_logic_version'):
        print("\n📈 ロジックバージョン別統計:")
        for lv in stats['by_logic_version']:
            print(f"  [{lv['logic_version']}] {lv['period']}")
            print(f"    {lv['races']}R / 的中{lv['hits']}R ({lv['hit_rate']}%) / 回収率{lv['recovery_rate']}% / 収支¥{lv['profit']:,}")

    if stats.get('virtual_bets'):
        print("\n🧪 仮想収支集計:")
        for v in stats['virtual_bets']:
            print(f"  {v['bet_type']:15}: {v['hits']}/{v['count']} ({v['hit_rate']}%) 回収率{v['recovery_rate']}%  収支¥{v['profit']:,}")

    print("\n✅ statistics.json に保存しました")
