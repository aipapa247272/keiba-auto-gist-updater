#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レース結果自動取得スクリプト（Phase 3-1 修正版 v6 - 完全版）

修正内容:
- HTMLパース処理を実際の構造に完全対応
- 着順と三連複払戻を正しく取得
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
    """
    url = f"{NAR_RESULT_URL}?race_id={race_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.encoding = 'EUC-JP'
            
            if response.status_code == 404:
                print(f"[WARNING] レース結果未公開: {race_id}")
                return None
            
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 着順を取得
            finishing_order = []
            
            # テーブルを探す
            result_table = soup.find('table', id='All_Result_Table')
            if not result_table:
                result_table = soup.find('table', class_='RaceCommon_Table')
            
            if not result_table:
                print(f"[WARNING] 結果テーブルが見つかりません: {race_id}")
                return None
            
            rows = result_table.find_all('tr')
            
            for row in rows:
                # 着順セルを探す
                result_num_cell = row.find('td', class_='Result_Num')
                if not result_num_cell:
                    continue
                
                rank_div = result_num_cell.find('div', class_='Rank')
                if not rank_div:
                    continue
                
                rank_text = rank_div.get_text(strip=True)
                
                # "1着" → "1" を抽出
                if '着' in rank_text:
                    rank = rank_text.replace('着', '').replace('\n', '').strip()
                    if rank in ['1', '2', '3']:
                        # 馬番を取得（3列目のNumセル）
                        num_cells = row.find_all('td', class_='Num')
                        if len(num_cells) >= 2:
                            umaban = num_cells[1].get_text(strip=True)
                            finishing_order.append(umaban)
                
                if len(finishing_order) >= 3:
                    break
            
            if len(finishing_order) < 3:
                print(f"[WARNING] 着順データが不完全: {race_id} - {finishing_order}")
                return None
            
            # 三連複払戻を取得
            sanrenpuku_payout = 0
            
            # 払戻テーブルを探す
            payout_table = soup.find('table', class_='Payout_Detail_Table')
            
            if payout_table:
                fuku3_row = payout_table.find('tr', class_='Fuku3')
                if fuku3_row:
                    payout_cell = fuku3_row.find('td', class_='Payout')
                    if payout_cell:
                        payout_text = payout_cell.get_text(strip=True)
                        # "420円" → "420"
                        payout_nums = payout_text.replace('円', '').replace(',', '').strip()
                        try:
                            sanrenpuku_payout = int(payout_nums)
                        except ValueError:
                            print(f"[WARNING] 三連複払戻の解析失敗: {payout_text}")
            
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
    予想と結果を照合する
    """
    if not result or not predicted_horses:
        return {
            'hit': False,
            'investment': 0,
            'payout': 0,
            'profit': 0
        }
    
    pred_set = set(str(horse.get('馬番', '')) for horse in predicted_horses[:3])
    actual_set = set(result['finishing_order'][:3])
    
    is_hit = pred_set == actual_set
    
    investment = 100
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
    """
    pred_file = f"final_predictions_{ymd}.json"
    if not os.path.exists(pred_file):
        print(f"[ERROR] 予想ファイルが見つかりません: {pred_file}")
        return False
    
    with open(pred_file, 'r', encoding='utf-8') as f:
        predictions = json.load(f)
    
    if 'selected_predictions' not in predictions:
        print(f"[ERROR] selected_predictions が見つかりません")
        return False
    
    selected_races = predictions['selected_predictions']
    print(f"[INFO] 選定レース数: {len(selected_races)}")
    
    results = []
    total_investment = 0
    total_return = 0
    hit_count = 0
    miss_count = 0
    unavailable_count = 0
    
    print(f"\n[INFO] レース結果取得中...")
    
    for race in selected_races:
        race_id = race.get('race_id', 'Unknown')
        
        result = fetch_race_result(race_id)
        
        if result is None:
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
        
        horses = race.get('horses', [])
        top3_horses = horses[:3]
        
        hit_info = check_hit(top3_horses, result)
        
        total_investment += hit_info['investment']
        total_return += hit_info['payout']
        
        if hit_info['hit']:
            hit_count += 1
            status = '的中'
        else:
            miss_count += 1
            status = '不的中'
        
        pred_umaban = [str(h.get('馬番', '?')) for h in top3_horses]
        actual_umaban = result['finishing_order']
        
        print(f"  {race.get('venue', '?')}{race.get('race_num', '?')}R: {status}")
        print(f"    予想: {'-'.join(pred_umaban)} / 実績: {'-'.join(actual_umaban)}")
        print(f"    払戻: {hit_info['payout']}円 / 収支: {hit_info['profit']:+d}円")
        
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
    if len(sys.argv) < 2:
        print("[ERROR] 使用方法: python fetch_race_results.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
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
