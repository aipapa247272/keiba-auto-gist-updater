import json
import requests
from datetime import datetime
from collections import defaultdict

def fetch_all_results():
    """GitHubから全結果JSONを取得"""
    base_url = "https://raw.githubusercontent.com/aipapa247272/keiba-auto-gist-updater/main/"
    
    # 取得する日付リスト（2/13-2/14の実績分）
    dates = [
        "20260213",
        "20260214"
    ]
    
    all_data = []
    
    for ymd in dates:
        url = f"{base_url}race_results_{ymd}.json"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                all_data.append(data)
                print(f"✅ {ymd} 取得成功")
            else:
                print(f"⚠️ {ymd} 取得失敗 (HTTP {response.status_code})")
        except Exception as e:
            print(f"❌ {ymd} エラー: {e}")
    
    return all_data

def calculate_statistics(all_data):
    """統計情報を計算"""
    
    # 全体集計
    total_races = 0
    total_hits = 0
    total_investment = 0
    total_return = 0
    
    # 日別データ
    daily_stats = []
    
    # 波乱度別集計
    turbulence_stats = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "return": 0})
    
    # 競馬場別集計
    venue_stats = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "return": 0})
    
    # トラック別集計
    track_stats = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "return": 0})
    
    for day_data in all_data:
        date = day_data.get('date', '')
        ymd = day_data.get('ymd', '')
        
        day_races = day_data.get('total_races', 0)
        day_hits = day_data.get('hit_count', 0)
        day_investment = day_data.get('total_investment', 0)
        day_return = day_data.get('total_return', 0)
        day_profit = day_data.get('total_profit', 0)
        
        total_races += day_races
        total_hits += day_hits
        total_investment += day_investment
        total_return += day_return
        
        daily_stats.append({
            'date': date,
            'ymd': ymd,
            'races': day_races,
            'hits': day_hits,
            'investment': day_investment,
            'return': day_return,
            'profit': day_profit,
            'hit_rate': round((day_hits / day_races * 100) if day_races > 0 else 0, 1),
            'recovery_rate': round((day_return / day_investment * 100) if day_investment > 0 else 0, 1)
        })
        
        # レース別詳細集計（波乱度・競馬場・トラック）
        for race in day_data.get('races', []):
            # ここでは波乱度データがないため、後で予想データから取得する必要あり
            venue = race.get('venue', '不明')
            track = race.get('track', '不明')
            hit = 1 if race.get('hit', False) else 0
            investment = race.get('investment', 0)
            return_amount = race.get('return', 0)
            
            # 競馬場別
            venue_stats[venue]['races'] += 1
            venue_stats[venue]['hits'] += hit
            venue_stats[venue]['investment'] += investment
            venue_stats[venue]['return'] += return_amount
            
            # トラック別
            track_stats[track]['races'] += 1
            track_stats[track]['hits'] += hit
            track_stats[track]['investment'] += investment
            track_stats[track]['return'] += return_amount
    
    # 全体統計
    overall_hit_rate = round((total_hits / total_races * 100) if total_races > 0 else 0, 1)
    overall_recovery_rate = round((total_return / total_investment * 100) if total_investment > 0 else 0, 1)
    total_profit = total_return - total_investment
    
    # 競馬場別統計整形
    venue_list = []
    for venue, stats in venue_stats.items():
        venue_list.append({
            'venue': venue,
            'races': stats['races'],
            'hits': stats['hits'],
            'hit_rate': round((stats['hits'] / stats['races'] * 100) if stats['races'] > 0 else 0, 1),
            'investment': stats['investment'],
            'return': stats['return'],
            'recovery_rate': round((stats['return'] / stats['investment'] * 100) if stats['investment'] > 0 else 0, 1)
        })
    venue_list.sort(key=lambda x: x['races'], reverse=True)
    
    # トラック別統計整形
    track_list = []
    for track, stats in track_stats.items():
        track_list.append({
            'track': track,
            'races': stats['races'],
            'hits': stats['hits'],
            'hit_rate': round((stats['hits'] / stats['races'] * 100) if stats['races'] > 0 else 0, 1),
            'investment': stats['investment'],
            'return': stats['return'],
            'recovery_rate': round((stats['return'] / stats['investment'] * 100) if stats['investment'] > 0 else 0, 1)
        })
    track_list.sort(key=lambda x: x['races'], reverse=True)
    
    return {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'overall': {
            'total_races': total_races,
            'total_hits': total_hits,
            'total_investment': total_investment,
            'total_return': total_return,
            'total_profit': total_profit,
            'hit_rate': overall_hit_rate,
            'recovery_rate': overall_recovery_rate
        },
        'daily': daily_stats,
        'by_venue': venue_list,
        'by_track': track_list
    }

if __name__ == '__main__':
    print("📊 統計データ生成開始...")
    
    # 全結果取得
    all_data = fetch_all_results()
    
    if not all_data:
        print("❌ データが取得できませんでした")
        exit(1)
    
    # 統計計算
    stats = calculate_statistics(all_data)
    
    # JSON保存
    with open('statistics.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"📊 全体統計")
    print(f"{'='*50}")
    print(f"総レース数: {stats['overall']['total_races']}")
    print(f"的中数: {stats['overall']['total_hits']}")
    print(f"的中率: {stats['overall']['hit_rate']}%")
    print(f"投資額: ¥{stats['overall']['total_investment']:,}")
    print(f"払戻額: ¥{stats['overall']['total_return']:,}")
    print(f"収支: ¥{stats['overall']['total_profit']:,}")
    print(f"回収率: {stats['overall']['recovery_rate']}%")
    print(f"{'='*50}\n")
    
    print("✅ statistics.json に保存しました")
