import requests
from bs4 import BeautifulSoup
import json
import sys
import os
from datetime import datetime
import time

def fetch_race_results(ymd):
    """
    指定日付のレース結果を取得
    ymd: YYYYMMDD形式の日付文字列
    """
    
    # =====================================================
    # バグ修正1: final_predictions_{ymd}.json を優先読み込み
    # latest_predictions.json は日付不一致の場合があるため
    # =====================================================
    pred_file = f'final_predictions_{ymd}.json'
    fallback_file = 'latest_predictions.json'
    
    predictions_data = None
    
    # まず final_predictions_{ymd}.json を試みる
    if os.path.exists(pred_file):
        try:
            with open(pred_file, 'r', encoding='utf-8') as f:
                predictions_data = json.load(f)
            print(f"✅ {pred_file} を使用")
        except Exception as e:
            print(f"⚠️ {pred_file} の読み込み失敗: {e}")
            predictions_data = None
    
    # ファイルが存在しない場合は latest_predictions.json にフォールバック
    if predictions_data is None:
        if not os.path.exists(fallback_file):
            print(f"❌ エラー: {pred_file} も {fallback_file} も見つかりません")
            return None
        try:
            with open(fallback_file, 'r', encoding='utf-8') as f:
                predictions_data = json.load(f)
            print(f"⚠️ {pred_file} が見つからないため {fallback_file} を使用")
        except Exception as e:
            print(f"❌ エラー: {fallback_file} の読み込み失敗: {e}")
            return None
    
    # 日付チェック: 不一致の場合は処理を中断（バグ修正1の核心）
    data_ymd = predictions_data.get('ymd')
    if data_ymd != ymd:
        print(f"❌ エラー: 予想データの日付 ({data_ymd}) と指定日付 ({ymd}) が一致しません")
        print(f"   処理を中断します。正しい予想ファイルを確認してください。")
        return None
    
    # 選定されたレースを取得
    selected_races = predictions_data.get('selected_predictions', [])
    
    if not selected_races:
        print(f"❌ エラー: 選定レースが見つかりません")
        return None
    
    print(f"📊 {len(selected_races)} レースの結果を取得します...")
    
    results = []
    
    for idx, race in enumerate(selected_races, 1):
        race_id = race.get('race_id')
        venue = race.get('venue') or race.get('競馬場') or 'Unknown'
        race_name = race.get('race_name') or race.get('レース名') or 'Unknown'
        race_num = race_id[-2:] if race_id and len(race_id) >= 2 else 'Unknown'
        distance = race.get('距離', race.get('distance', ''))
        track = race.get('track', '')
        
        print(f"\n[{idx}/{len(selected_races)}] {venue} R{race_num} {race_name} (ID: {race_id})")
        
        betting_plan = race.get('betting_plan', {})
        axis_horses = betting_plan.get('軸', [])
        
        # =====================================================
        # バグ修正2: 馬番がNone/空文字の場合のガード処理
        # =====================================================
        predicted_combinations = []
        axis_numbers_raw = []
        
        for h in axis_horses[:3]:
            uma_num = h.get('馬番')
            # None や空文字、'None'文字列を除外
            if uma_num is None or str(uma_num).strip() == '' or str(uma_num).strip().lower() == 'none':
                print(f"  ⚠️ 馬番が不正な値: {uma_num} → スキップ")
                continue
            axis_numbers_raw.append(str(uma_num).strip())
        
        if len(axis_numbers_raw) >= 3:
            axis_numbers = sorted(axis_numbers_raw[:3])
            predicted_combinations = ['-'.join(axis_numbers)]
            print(f"  🎯 予想: {predicted_combinations[0]}")
        else:
            print(f"  ⚠️ 有効な軸馬が{len(axis_numbers_raw)}頭のみ（3頭必要）→ 予想なしとして記録")
        
        investment = race.get('investment', 2400)
        
        race_result = fetch_single_race_result(race_id, ymd)
        
        if race_result is None:
            print(f"  ❌ 結果取得失敗")
            results.append({
                'race_id': race_id,
                'venue': venue,
                'race_num': race_num,
                'race_name': race_name,
                'distance': distance,
                'track': track,
                'status': '結果取得不可',
                'predicted': predicted_combinations,
                'actual': [],
                'hit': False,
                'investment': investment,
                'return': 0,
                'profit': -investment,
                'payouts': {},
                'horse_weights': [],
                'weather': '',
                'track_condition': ''
            })
            continue
        
        sanrenpuku_result = race_result.get('sanrenpuku_result', '')
        sanrenpuku_payout = race_result.get('sanrenpuku_payout', 0)
        
        hit = False
        return_amount = 0
        
        # 予想がある場合のみ的中判定
        if sanrenpuku_result and predicted_combinations:
            actual_numbers = set(sanrenpuku_result.split('-'))
            
            for combo in predicted_combinations:
                predicted_numbers = set(combo.split('-'))
                if actual_numbers == predicted_numbers:
                    hit = True
                    return_amount = sanrenpuku_payout
                    print(f"  ✅ 的中！ 払戻: ¥{sanrenpuku_payout:,}")
                    break
        
        if not hit:
            if not predicted_combinations:
                print(f"  ⚠️ 予想なし（馬番データ不足のためスキップ）")
            else:
                print(f"  ❌ 不的中")
        
        profit = return_amount - investment
        
        results.append({
            'race_id': race_id,
            'venue': venue,
            'race_num': race_num,
            'race_name': race_name,
            'distance': distance,
            'track': track,
            'status': '的中' if hit else ('予想なし' if not predicted_combinations else '不的中'),
            'predicted': predicted_combinations,
            'actual': [sanrenpuku_result] if sanrenpuku_result else [],
            'result_sanrenpuku': sanrenpuku_result,
            'payout_sanrenpuku': sanrenpuku_payout,
            'hit': hit,
            'investment': investment,
            'return': return_amount,
            'profit': profit,
            'payouts': race_result.get('payouts', {}),
            'horse_weights': race_result.get('horse_weights', []),
            'weather': race_result.get('weather', ''),
            'track_condition': race_result.get('track_condition', '')
        })
        
        time.sleep(1)
    
    total_races = len(results)
    hit_count = sum(1 for r in results if r['status'] == '的中')
    miss_count = sum(1 for r in results if r['status'] == '不的中')
    unavailable_count = sum(1 for r in results if r['status'] == '結果取得不可')
    no_pred_count = sum(1 for r in results if r['status'] == '予想なし')
    
    # 的中率計算は「予想あり」レースのみを対象にする
    valid_races = hit_count + miss_count
    
    total_investment = sum(r['investment'] for r in results)
    total_return = sum(r['return'] for r in results)
    total_profit = total_return - total_investment
    
    hit_rate = (hit_count / valid_races * 100) if valid_races > 0 else 0
    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0
    
    print(f"\n{'='*50}")
    print(f"📊 結果サマリー")
    print(f"{'='*50}")
    print(f"総レース数: {total_races}")
    print(f"的中: {hit_count} / 不的中: {miss_count} / 取得不可: {unavailable_count} / 予想なし: {no_pred_count}")
    print(f"投資額: ¥{total_investment:,}")
    print(f"払戻額: ¥{total_return:,}")
    print(f"収支: {'+' if total_profit >= 0 else ''}¥{total_profit:,}")
    print(f"的中率: {hit_rate:.1f}%（予想ありレース{valid_races}件中）")
    print(f"回収率: {recovery_rate:.1f}%")
    print(f"{'='*50}\n")
    
    date_obj = datetime.strptime(ymd, '%Y%m%d')
    date_str = date_obj.strftime('%Y/%m/%d')
    
    output_data = {
        'date': date_str,
        'ymd': ymd,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_races': total_races,
        'hit_count': hit_count,
        'miss_count': miss_count,
        'unavailable_count': unavailable_count,
        'no_pred_count': no_pred_count,
        'valid_races': valid_races,
        'total_investment': total_investment,
        'total_return': total_return,
        'total_profit': total_profit,
        'hit_rate': round(hit_rate, 1),
        'recovery_rate': round(recovery_rate, 1),
        'races': results
    }
    
    output_filename = f'race_results_{ymd}.json'
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    with open('latest_results.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 結果を {output_filename} と latest_results.json に保存しました")
    
    return output_data


def get_venue_info(race_id):
    venue_code = race_id[4:6]
    
    if int(venue_code) <= 10:
        venues = {
            "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
            "05": "東京", "06": "中山", "07": "中京", "08": "京都",
            "09": "阪神", "10": "小倉"
        }
        return 'central', venues.get(venue_code, f"不明({venue_code})")
    
    local_venues = {
        "30": "門別", "35": "盛岡", "36": "水沢",
        "42": "浦和", "43": "船橋", "44": "大井", "45": "川崎",
        "46": "金沢", "47": "笠松", "48": "名古屋",
        "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"
    }
    return 'local', local_venues.get(venue_code, f"不明({venue_code})")


def fetch_single_race_result(race_id, ymd):
    race_type, venue_name = get_venue_info(race_id)
    
    if race_type == 'central':
        base_url = 'https://race.netkeiba.com'
    else:
        base_url = 'https://nar.netkeiba.com'
    
    url = f'{base_url}/race/result.html?race_id={race_id}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': base_url
    }
    
    try:
        print(f"  🏇 {race_type.upper()} - {venue_name}")
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        result_table = soup.select_one('table.Shutuba_Table')
        if not result_table:
            result_table = soup.select_one('table.race_table_01')
        if not result_table:
            result_table = soup.select_one('table.RaceCommon_Table')
        
        if not result_table:
            print(f"  ❌ レース結果テーブルが見つかりません")
            return None
        
        rows = result_table.select('tr')
        if len(rows) < 4:
            print(f"  ❌ 着順データが不足")
            return None
        
        top_3 = []
        horse_weights = []
        
        data_rows = [r for r in rows if r.select('td')][:3]
        
        for i, row in enumerate(data_rows):
            cols = row.select('td')
            
            if len(cols) < 3:
                continue
            
            horse_number = ''
            rank_td = cols[0].get_text(strip=True)
            
            if rank_td == str(i+1):
                if len(cols) > 2:
                    horse_number = cols[2].get_text(strip=True)
                if not horse_number.isdigit() and len(cols) > 3:
                    horse_number = cols[3].get_text(strip=True)
            
            if not horse_number or not horse_number.isdigit():
                umaban = row.select_one('.Umaban')
                if umaban:
                    horse_number = umaban.get_text(strip=True)
            
            if not horse_number or not horse_number.isdigit():
                for col in cols[1:5]:
                    text = col.get_text(strip=True)
                    if text.isdigit() and 1 <= int(text) <= 18:
                        horse_number = text
                        break
            
            if horse_number and horse_number.isdigit():
                top_3.append(horse_number)
                print(f"  🐎 {i+1}着: {horse_number}番")
            
            weight_text = ''
            for col in cols[-5:]:
                text = col.get_text(strip=True)
                if '(' in text and ')' in text:
                    weight_text = text
                    break
            
            if weight_text:
                horse_weights.append({
                    'rank': i + 1,
                    'horse_number': horse_number,
                    'weight': weight_text
                })
        
        if len(top_3) < 3:
            print(f"  ❌ 上位3頭のデータが不足")
            return None
        
        # 着順通りの並び（sorted()なし）
        sanrenpuku_result = '-'.join(top_3)
        print(f"  🎯 三連複: {sanrenpuku_result}")
        
        payout_tables = []
        local_table = soup.select_one('table.Payout_Detail_Table')
        if local_table:
            payout_tables.append(local_table)
        
        central_tables = soup.select('table[summary="払い戻し"], table[summary="ワイド"]')
        if central_tables:
            payout_tables.extend(central_tables)
        
        if not payout_tables:
            fallback = soup.select_one('table.pay_table_01')
            if fallback:
                payout_tables.append(fallback)
        
        payouts = {}
        sanrenpuku_payout = 0
        
        bet_type_map = {
            '単勝': '単勝', '複勝': '複勝', '枠連': '枠連', '馬連': '馬連',
            '馬単': '馬単', 'ワイド': 'ワイド', '三連複': '三連複', '三連単': '三連単',
            '3連複': '三連複', '3連単': '三連単'
        }
        
        if payout_tables:
            for table in payout_tables:
                payout_rows = table.select('tr')
                
                for row in payout_rows:
                    th = row.select_one('th')
                    if not th:
                        continue
                    
                    raw_bet_type = th.get_text(strip=True)
                    bet_type = bet_type_map.get(raw_bet_type, raw_bet_type)
                    
                    all_td = row.select('td')
                    if len(all_td) < 2:
                        continue
                    
                    payout_td = all_td[1] if len(all_td) >= 2 else all_td[-1]
                    payout_text = payout_td.get_text(separator='\n', strip=True)
                    payout_values = []
                    
                    lines = payout_text.split('\n')
                    import re
                    for line in lines:
                        clean_line = line.replace(',', '').replace('円', '').replace('¥', '').strip()
                        numbers = re.findall(r'\d+', clean_line)
                        for num_str in numbers:
                            try:
                                payout_value = int(num_str)
                                if payout_value >= 100:
                                    payout_values.append(payout_value)
                            except ValueError:
                                pass
                    
                    if payout_values:
                        if bet_type == '複勝':
                            final_payout = min(payout_values)
                        else:
                            final_payout = payout_values[0]
                        
                        payouts[bet_type] = final_payout
                        
                        if bet_type == '三連複':
                            sanrenpuku_payout = final_payout
                            print(f"  💰 三連複払戻: ¥{final_payout:,}")
        
        weather = ''
        track_condition = ''
        
        race_data_box = soup.select_one('.RaceData01, .RaceData02, .race_otherdata')
        
        if race_data_box:
            data_text = race_data_box.get_text()
            import re
            weather_match = re.search(r'天候[:\s]*([^\s/]+)', data_text)
            if weather_match:
                weather = weather_match.group(1)
            
            track_match = re.search(r'馬場[:\s]*([^\s/]+)', data_text)
            if track_match:
                track_condition = track_match.group(1)
        
        return {
            'sanrenpuku_result': sanrenpuku_result,
            'sanrenpuku_payout': sanrenpuku_payout,
            'payouts': payouts,
            'horse_weights': horse_weights,
            'weather': weather,
            'track_condition': track_condition,
            'race_type': race_type,
            'venue_name': venue_name
        }
        
    except requests.RequestException as e:
        print(f"  ❌ ネットワークエラー: {e}")
        return None
    except Exception as e:
        print(f"  ❌ 予期しないエラー: {e}")
        return None


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('使用方法: python fetch_race_results.py YYYYMMDD')
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    if len(ymd) != 8 or not ymd.isdigit():
        print('❌ エラー: 日付は YYYYMMDD 形式で指定してください')
        sys.exit(1)
    
    result = fetch_race_results(ymd)
    
    if result:
        print(f"\n✅ 処理完了")
        sys.exit(0)
    else:
        print(f"\n❌ 処理失敗")
        sys.exit(1)
