#!/usr/bin/env python3
"""
generate_stats.py 完全刷新版
- 全 race_results_*.json を自動検出して集計
- score_tier 別・仮想収支集計を追加
- 日付範囲を自動取得
"""
import json
import requests
from datetime import datetime
from collections import defaultdict
import os

BASE_URL = "https://raw.githubusercontent.com/aipapa247272/keiba-auto-gist-updater/main/"

def fetch_all_results():
    """GitHubから全結果JSONを自動検出して取得"""
    # まず index.json 相当の API でファイル一覧を取得
    api_url = "https://api.github.com/repos/aipapa247272/keiba-auto-gist-updater/contents/"
    all_data = []

    try:
        resp = requests.get(api_url, timeout=15)
        files = resp.json()
        # race_results_YYYYMMDD.json をすべて抽出
        result_files = sorted([
            f['name'] for f in files
            if isinstance(f, dict)
            and f.get('name','').startswith('race_results_202')
            and f.get('name','').endswith('.json')
            and not f.get('name','').startswith('race_results_00')  # 誤ファイル除外
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
                # ymd が未設定の場合は補完
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


def calculate_statistics(all_data):
    """統計情報を計算（score_tier・仮想収支対応版）"""

    total_races = 0
    total_hits  = 0
    total_investment = 0
    total_return     = 0

    daily_stats   = []
    venue_stats   = defaultdict(lambda: {"races":0,"hits":0,"investment":0,"return":0})
    track_stats   = defaultdict(lambda: {"races":0,"hits":0,"investment":0,"return":0})
    tier_stats    = defaultdict(lambda: {"races":0,"hits":0,"investment":0,"return":0})

    # 仮想収支集計（複勝/ワイド/馬連）
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

        daily_stats.append({
            'date':          date,
            'ymd':           ymd,
            'races':         day_races,
            'hits':          day_hits,
            'investment':    day_investment,
            'return':        day_return,
            'profit':        day_profit,
            'hit_rate':      round((day_hits/day_races*100) if day_races>0 else 0, 1),
            'recovery_rate': round((day_return/day_investment*100) if day_investment>0 else 0, 1)
        })

        for race in day_data.get('races', []):
            venue  = race.get('venue', '不明')
            track  = race.get('track', '不明')
            tier   = race.get('score_tier', '?')
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

            # 仮想収支
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
        'daily':            daily_stats,
        'by_venue':         make_list(venue_stats, 'venue'),
        'by_track':         make_list(track_stats, 'track'),
        'by_score_tier':    make_list(tier_stats, 'tier'),
        'virtual_bets':     vb_list
    }


if __name__ == '__main__':
    print("📊 統計データ生成開始...")
    all_data = fetch_all_results()

    if not all_data:
        print("❌ データが取得できませんでした")
        exit(1)

    stats = calculate_statistics(all_data)

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
    if stats.get('virtual_bets'):
        print("\n🧪 仮想収支集計:")
        for v in stats['virtual_bets']:
            print(f"  {v['bet_type']:15}: {v['hits']}/{v['count']} ({v['hit_rate']}%) 回収率{v['recovery_rate']}%  収支¥{v['profit']:,}")
    print("\n✅ statistics.json に保存しました")
