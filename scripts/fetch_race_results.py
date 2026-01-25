#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""レース結果自動取得スクリプト（Phase 3-1 改善版）"""

import os
import sys
import json
import time
import logging
import re
from datetime import datetime
from urllib import request, error

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

NAR_RESULT_URL = "https://nar.netkeiba.com/race/result.html"
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_DELAY = 2

def http_get(url, encoding='EUC-JP', timeout=REQUEST_TIMEOUT):
    """HTTP GETリクエスト"""
    for attempt in range(RETRY_COUNT):
        try:
            req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode(encoding, errors='ignore')
        except error.HTTPError as e:
            if e.code == 404:
                logging.warning(f"404: {url}")
                return None
            logging.error(f"HTTP {e.code}: {url}")
        except Exception as e:
            logging.error(f"Error ({attempt+1}/{RETRY_COUNT}): {e}")
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
    return None

def extract_race_results(html):
    """HTMLから着順と払戻を抽出（改善版）"""
    results = {'finishing_order': [], 'payouts': {}}
    
    # 着順の抽出（正規表現を使用）
    # パターン: 1着、2着、3着の馬番を探す
    order_pattern = r'<td[^>]*class="[^"]*txt_l[^"]*"[^>]*>.*?<a[^>]*>(\d+)</a>'
    matches = re.findall(order_pattern, html)
    
    if len(matches) >= 3:
        results['finishing_order'] = matches[:3]
        logging.info(f"  着順抽出成功: {'-'.join(results['finishing_order'])}")
    else:
        # 代替パターン: より広範囲に馬番を探す
        alt_pattern = r'umaban["\']?>(\d+)</span>'
        alt_matches = re.findall(alt_pattern, html)
        if len(alt_matches) >= 3:
            results['finishing_order'] = alt_matches[:3]
            logging.info(f"  着順抽出成功（代替）: {'-'.join(results['finishing_order'])}")
    
    # 三連複の払戻を抽出
    # パターン: 三連複の行から払戻金を探す
    sanrenpuku_pattern = r'三連複.*?(\d+(?:,\d+)*)\s*円'
    payout_match = re.search(sanrenpuku_pattern, html)
    
    if payout_match:
        payout_str = payout_match.group(1).replace(',', '')
        results['payouts']['sanrenpuku'] = int(payout_str)
        logging.info(f"  三連複払戻: {results['payouts']['sanrenpuku']:,}円")
    else:
        # 代替パターン
        alt_payout_pattern = r'<td[^>]*>\s*(\d+(?:,\d+)*)\s*</td>.*?三連複'
        alt_match = re.search(alt_payout_pattern, html, re.DOTALL)
        if alt_match:
            payout_str = alt_match.group(1).replace(',', '')
            results['payouts']['sanrenpuku'] = int(payout_str)
            logging.info(f"  三連複払戻（代替）: {results['payouts']['sanrenpuku']:,}円")
    
    return results

def fetch_race_result(race_id):
    """レース結果を取得"""
    url = f"{NAR_RESULT_URL}?race_id={race_id}"
    logging.info(f"レース結果取得中: {race_id}")
    
    html = http_get(url)
    if not html:
        logging.warning(f"HTMLを取得できませんでした: {race_id}")
        return None
    
    results = extract_race_results(html)
    
    if not results['finishing_order']:
        logging.warning(f"着順データが見つかりません: {race_id}")
        return None
    
    return results

def check_hit(prediction, result):
    """的中判定"""
    pred_set = set([
        str(prediction.get('honmei', {}).get('umaban', prediction.get('honmei'))),
        str(prediction.get('taikou', {}).get('umaban', prediction.get('taikou'))),
        str(prediction.get('ana', {}).get('umaban', prediction.get('ana')))
    ])
    result_set = set(result['finishing_order'][:3])
    
    hit = pred_set == result_set
    return {
        'hit': hit,
        'predicted': sorted(list(pred_set)),
        'actual': result['finishing_order'][:3]
    }

def calculate_profit(hit, investment, payout):
    """収支計算"""
    if hit and payout:
        return_amount = payout
        profit = return_amount - investment
        recovery_rate = (return_amount / investment * 100) if investment > 0 else 0
    else:
        return_amount = 0
        profit = -investment
        recovery_rate = 0
    return {
        'investment': investment,
        'return': return_amount,
        'profit': profit,
        'recovery_rate': round(recovery_rate, 1)
    }

def process_results(ymd):
    """レース結果の処理メイン"""
    pred_file = f"final_predictions_{ymd}.json"
    
    if not os.path.exists(pred_file):
        logging.error(f"予想ファイルなし: {pred_file}")
        return False
    
    with open(pred_file, 'r', encoding='utf-8') as f:
        predictions = json.load(f)
    
    if 'selected_predictions' not in predictions:
        logging.error("選定レースなし")
        return False
    
    selected_races = predictions['selected_predictions']
    logging.info(f"選定レース数: {len(selected_races)}")
    
    results_data = {
        'date': ymd,
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_races': len(selected_races),
            'hit_count': 0,
            'miss_count': 0,
            'unavailable_count': 0,
            'total_investment': 0,
            'total_return': 0,
            'total_profit': 0,
            'hit_rate': 0.0,
            'recovery_rate': 0.0
        },
        'results': []
    }
    
    for i, race in enumerate(selected_races, 1):
        race_id = race['race_id']
        race_info = race.get('race_info', {})
        race_name = f"{race_info.get('venue', 'N/A')} {race_info.get('レース名', 'N/A')}"
        
        logging.info(f"\n[{i}/{len(selected_races)}] {race_name}")
        
        result = fetch_race_result(race_id)
        race_result = {
            'race_id': race_id,
            'race_name': race_name,
            'result_available': result is not None
        }
        
        if result:
            hit_info = check_hit(race['predictions'], result)
            investment = race['betting_suggestions']['total_investment']
            payout = result['payouts'].get('sanrenpuku', 0)
            profit_info = calculate_profit(hit_info['hit'], investment, payout)
            
            race_result.update({
                'finishing_order': result['finishing_order'][:3],
                'payout_sanrenpuku': payout,
                'prediction': {
                    'honmei': race['predictions']['honmei']['umaban'],
                    'taikou': race['predictions']['taikou']['umaban'],
                    'ana': race['predictions']['ana']['umaban']
                },
                'hit': hit_info['hit'],
                'investment': investment,
                'return': profit_info['return'],
                'profit': profit_info['profit'],
                'recovery_rate': profit_info['recovery_rate']
            })
            
            results_data['summary']['total_investment'] += investment
            results_data['summary']['total_return'] += profit_info['return']
            results_data['summary']['total_profit'] += profit_info['profit']
            
            if hit_info['hit']:
                results_data['summary']['hit_count'] += 1
                logging.info(f"  ✅ 的中！ {payout:,}円 / {profit_info['profit']:+,}円")
            else:
                results_data['summary']['miss_count'] += 1
                logging.info(f"  ❌ 不的中 / {profit_info['profit']:+,}円")
                logging.info(f"     予想: {'-'.join(hit_info['predicted'])} / 実際: {'-'.join(hit_info['actual'])}")
        else:
            results_data['summary']['unavailable_count'] += 1
            race_result.update({
                'status': 'unavailable',
                'note': '結果取得不可'
            })
            logging.warning("  ⚠️ 取得不可")
        
        results_data['results'].append(race_result)
        time.sleep(1)
    
    completed = results_data['summary']['hit_count'] + results_data['summary']['miss_count']
    if completed > 0:
        results_data['summary']['hit_rate'] = round(
            results_data['summary']['hit_count'] / completed * 100, 1
        )
    
    if results_data['summary']['total_investment'] > 0:
        results_data['summary']['recovery_rate'] = round(
            results_data['summary']['total_return'] / 
            results_data['summary']['total_investment'] * 100, 1
        )
    
    output_file = f"race_results_{ymd}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)
    
    logging.info(f"\n{'='*60}")
    logging.info(f"[SUCCESS] {output_file}")
    logging.info(f"{'='*60}")
    logging.info(f"対象: {results_data['summary']['total_races']}R")
    logging.info(f"的中: {results_data['summary']['hit_count']}R / "
                f"不的中: {results_data['summary']['miss_count']}R / "
                f"取得不可: {results_data['summary']['unavailable_count']}R")
    logging.info(f"的中率: {results_data['summary']['hit_rate']:.1f}%")
    logging.info(f"投資: {results_data['summary']['total_investment']:,}円")
    logging.info(f"払戻: {results_data['summary']['total_return']:,}円")
    logging.info(f"収支: {results_data['summary']['total_profit']:+,}円")
    logging.info(f"回収率: {results_data['summary']['recovery_rate']:.1f}%")
    logging.info(f"{'='*60}\n")
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_race_results.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    if not ymd.isdigit() or len(ymd) != 8:
        logging.error("日付形式エラー: YYYYMMDD")
        sys.exit(1)
    
    success = process_results(ymd)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
