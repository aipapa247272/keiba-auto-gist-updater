#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レース結果自動取得スクリプト（Phase 3-1 修正版 v3）

修正内容:
- NAR NetKeiba SP版のURL対応
- HTMLパース処理の改善（複数パターン対応）
- デバッグログの追加
"""

import os
import sys
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# NAR NetKeiba SP版のURL
NAR_RESULT_URL = "https://nar.sp.netkeiba.com/race/race_result.html"

def fetch_race_result(race_id, timeout=30, max_retries=3):
    """
    指定されたrace_idのレース結果を取得する
    
    Args:
        race_id: レースID
        timeout: タイムアウト（秒）
        max_retries: 最大リトライ回数
    
    Returns:
        dict: レース結果（着順、三連複払戻）
    """
    url = f"{NAR_RESULT_URL}?race_id={race_id}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.encoding = 'EUC-JP'
            
            if response.status_code == 404:
                print(f"[WARNING] レース結果未公開: {race_id}")
                return None
            
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 着順を取得（複数パターン対応）
            finishing_order = []
            
            # パターン1: PC版のテーブル
            result_table = soup.find('table', class_='All_Result_Table') or soup.find('table', class_='ResultMain')
            
            # パターン2: SP版のテーブル
            if not result_table:
                result_table = soup.find('table', class_='result_table') or soup.find('table', class_='RaceResultTable')
            
            # パターン3: その他のテーブル（class属性なし）
            if not result_table:
                result_table = soup.find('table')
            
            if result_table:
                rows = result_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        # 1列目が着順、2列目が馬番のパターン
                        chakujun = cells[0].get_text(strip=True)
                        umaban = cells[1].get_text(strip=True)
                        
                        # 着順が数字（1,2,3）の場合のみ追加
                        if chakujun in ['1', '2', '3']:
                            finishing_order.append(umaban)
                        
                        if len(finishing_order) >= 3:
                            break
            
            if len(finishing_order) < 3:
                print(f"[WARNING] 着順データが不完全: {race_id} - {finishing_order}")
                print(f"[DEBUG] HTML構造:")
                print(f"  テーブル数: {len(soup.find_all('table'))}")
                if result_table:
                    print(f"  行数: {len(result_table.find_all('tr'))}")
                return None
            
            # 三連複払戻を取得
            sanrenpuku_payout = 0
            
            # パターン1: Payout_Detail_Table
            payout_tables = soup.find_all('table', class_='Payout_Detail_Table')
            if len(payout_tables) >= 2:
                second_table = payout_tables[1]
                rows = second_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if cells and '三連複' in cells[0].get_text():
                        payout_text = cells[1].get_text(strip=True).replace(',', '').replace('円', '')
                        try:
                            sanrenpuku_payout = int(payout_text)
                        except ValueError:
                            pass
                        break
            
            # パターン2: SP版の払戻テーブル
            if sanrenpuku_payout == 0:
                payout_tables = soup.find_all('table', class_='payout_table')
                for table in payout_tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 2 and '三連複' in cells[0].get_text():
                            payout_text = cells[1].get_text(strip=True).replace(',', '').replace('円', '')
                            try:
                                sanrenpuku_payout = int(payout_text)
                            except ValueError:
                                pass
                            break
            
            result = {
                'finishing_order': finishing_order,
                'sanrenpuku_payout': sanrenpuku_payout
            }
            
            print(f"[INFO] レース結果取得成功: {race_id}")
            print(f"  着順: {'-'.join(finishing_order)}, 三連複: {sanrenpuku_payout}円")
            
            return result
            
        except requests.exceptions.Timeout:
            print(f"[WARNING] タイムアウト (試行 {attempt + 1}/{max_retries}): {race_id}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"[ERROR] レース結果取得エラー: {race_id} - {e}")
            return None
    
    return None

def check_hit(predicted_horses, result):
    """
    予想と結果を照合する（修正版 - horses配列対応）
    
    Args:
        predicted_horses: 予想上位3頭のリスト [{"馬番": 3, ...}, {"馬番": 12, ...}, ...]
        result: 実際の結果 {'finishing_order': ['2', '8', '9'], 'sanrenpuku_payout': 220}
    
    Returns:
        dict: 的中情報
    """
    if not result or not predicted_horses:
        return {
            'hit': False,
            'investment': 0,
            'payout': 0,
            'profit': 0
        }
    
    # 予想の馬番を取得（上位3頭）
    pred_set = set(str(horse.get('馬番', '')) for horse in predicted_horses[:3])
    actual_set = set(result['finishing_order'][:3])
    
    # 的中判定（3頭が完全一致）
    is_hit = pred_set == actual_set
    
    investment = 100  # 1レースあたり100円
    payout = result['sanrenpuku_payout'] if is_hit else 0
    profit = payout - investment
    
    return {
        'hit': is_hit,
        'investment': investment,
        'payout': payout,
        'profit': profit
    }

def process_results(ymd):
    """
    予想ファイルを読み込み、結果を取得・照合する
    
    Args:
        ymd: 日付（YYYYMMDD形式）
    
    Returns:
        bool: 成功/失敗
    """
    # 予想ファイルを読み込む
    pred_file = f"final_predictions_{ymd}.json"
    if not os.path.exists(pred_file):
        print(f"[ERROR] 予想ファイルが見つかりません: {pred_file}")
        return False
    
    with open(pred_file, 'r', encoding='utf-8') as f:
        predictions = json.load(f)
    
    # selected_predictions を取得
    if 'selected_predictions' not in predictions:
        print(f"[ERROR] selected_predictions が見つかりません")
        return False
    
    selected_races = predictions['selected_predictions']
    print(f"[INFO] 選定レース数: {len(selected_races)}")
    
    # 結果を格納するリスト
    results = []
    total_investment = 0
    total_return = 0
    hit_count = 0
    miss_count = 0
    unavailable_count = 0
    
    print(f"\n[INFO] レース結果取得中...")
    
    for race in selected_races:
        race_id = race.get('race_id', 'Unknown')
        
        # 結果を取得
        result = fetch_race_result(race_id)
        
        if result is None:
            # 結果取得不可
            results.append({
                'race_id': race_id,
                'venue': race.get('venue', 'Unknown'),
                'race_num': race.get('race_num', 'Unknown'),
                'race_name': race.get('race_name', 'Unknown'),
                'status': '結果取得不可',
                'hit': False,
                'investment': 0,
                'payout': 0,
                'profit': 0
            })
            unavailable_count += 1
            continue
        
        # 予想上位3頭を取得
        horses = race.get('horses', [])
        top3_horses = horses[:3]
        
        # 的中判定
        hit_info = check_hit(top3_horses, result)
        
        # 統計を更新
        total_investment += hit_info['investment']
        total_return += hit_info['payout']
        
        if hit_info['hit']:
            hit_count += 1
            status = '的中'
        else:
            miss_count += 1
            status = '不的中'
        
        # 予想と実績を表示
        pred_umaban = [str(h.get('馬番', '?')) for h in top3_horses]
        actual_umaban = result['finishing_order']
        
        print(f"  {race.get('venue', '?')}{race.get('race_num', '?')}R: {status}")
        print(f"    予想: {'-'.join(pred_umaban)} / 実績: {'-'.join(actual_umaban)}")
        print(f"    払戻: {hit_info['payout']}円 / 収支: {hit_info['profit']:+d}円")
        
        # 結果を追加
        results.append({
            'race_id': race_id,
            'venue': race.get('venue', 'Unknown'),
            'race_num': race.get('race_num', 'Unknown'),
            'race_name': race.get('race_name', 'Unknown'),
            'status': status,
            'predicted': pred_umaban,
            'actual': actual_umaban,
            'hit': hit_info['hit'],
            'investment': hit_info['investment'],
            'payout': hit_info['payout'],
            'profit': hit_info['profit']
        })
    
    # サマリーを計算
    total_profit = total_return - total_investment
    hit_rate = (hit_count / len(selected_races) * 100) if len(selected_races) > 0 else 0
    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0
    
    summary = {
        'date': ymd,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'total_races': len(selected_races),
            'hit_count': hit_count,
            'miss_count': miss_count,
            'unavailable_count': unavailable_count,
            'total_investment': total_investment,
            'total_return': total_return,
            'total_profit': total_profit,
            'hit_rate': round(hit_rate, 1),
            'recovery_rate': round(recovery_rate, 1)
        },
        'results': results
    }
    
    # 結果を保存
    output_file = f"race_results_{ymd}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] 結果を保存しました: {output_file}")
    print(f"\n📊 本日の成績")
    print(f"  対象: {len(selected_races)}R")
    print(f"  的中: {hit_count}R / 不的中: {miss_count}R / 取得不可: {unavailable_count}R")
    print(f"  的中率: {hit_rate:.1f}%")
    print(f"  投資: {total_investment}円")
    print(f"  払戻: {total_return}円")
    print(f"  収支: {total_profit:+d}円")
    print(f"  回収率: {recovery_rate:.1f}%")
    
    return True

def main():
    """
    メイン処理
    """
    if len(sys.argv) < 2:
        print("[ERROR] 使用方法: python fetch_race_results.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    # 日付の形式チェック
    try:
        datetime.strptime(ymd, '%Y%m%d')
    except ValueError:
        print(f"[ERROR] 無効な日付形式: {ymd}")
        sys.exit(1)
    
    print(f"[INFO] レース結果取得を開始します: {ymd}")
    
    success = process_results(ymd)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
