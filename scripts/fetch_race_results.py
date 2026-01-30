import requests
from bs4 import BeautifulSoup
import json
import sys
from datetime import datetime

def fetch_race_results(ymd):
    """
    指定日付のレース結果を取得
    ymd: YYYYMMDD形式の日付文字列
    """
    
    # latest_predictions.json からデータを読み込む
    try:
        with open('latest_predictions.json', 'r', encoding='utf-8') as f:
            predictions_data = json.load(f)
    except FileNotFoundError:
        print(f"エラー: latest_predictions.json が見つかりません")
        return None
    
    # 日付が一致するか確認
    if predictions_data.get('ymd') != ymd:
        print(f"警告: 予想データの日付 ({predictions_data.get('ymd')}) と指定日付 ({ymd}) が一致しません")
    
    # 選定されたレースを取得
    selected_races = predictions_data.get('selected_predictions', [])
    
    results = []
    
    for race in selected_races:
        race_id = race.get('race_id')
        venue = race.get('venue', 'Unknown')
        race_name = race.get('race_name', 'Unknown')
        race_num = race.get('race_num', 'Unknown')
        distance = race.get('distance', '')
        track = race.get('track', '')
        
        # 予想買い目を取得
        betting = race.get('betting_suggestions', {}).get('main', {})
        predicted_combinations = betting.get('combinations', [])
        investment = betting.get('total_investment', 100)
        
        # レース結果を取得
        race_result = fetch_single_race_result(race_id, ymd)
        
        if race_result is None:
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
                'payouts': {}
            })
            continue
        
        # 三連複の払戻を取得
        sanrenpuku_result = race_result.get('sanrenpuku_result', '')
        sanrenpuku_payout = race_result.get('sanrenpuku_payout', 0)
        
        # 的中判定
        hit = False
        return_amount = 0
        
        if sanrenpuku_result and predicted_combinations:
            # 予想と結果を比較
            actual_numbers = set(sanrenpuku_result.split('-'))
            
            for combo in predicted_combinations:
                predicted_numbers = set(combo.split('-'))
                if actual_numbers == predicted_numbers:
                    hit = True
                    return_amount = sanrenpuku_payout
                    break
        
        profit = return_amount - investment
        
        results.append({
            'race_id': race_id,
            'venue': venue,
            'race_num': race_num,
            'race_name': race_name,
            'distance': distance,
            'track': track,
            'status': '的中' if hit else '不的中',
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
    
    # サマリーを計算
    total_races = len(results)
    hit_count = sum(1 for r in results if r['status'] == '的中')
    miss_count = sum(1 for r in results if r['status'] == '不的中')
    unavailable_count = sum(1 for r in results if r['status'] == '結果取得不可')
    
    total_investment = sum(r['investment'] for r in results)
    total_return = sum(r['return'] for r in results)
    total_profit = total_return - total_investment
    
    hit_rate = (hit_count / total_races * 100) if total_races > 0 else 0
    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0
    
    output_data = {
        'date': datetime.now().strftime('%Y%m%d'),
        'ymd': ymd,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'total_races': total_races,
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
    
    # 結果をファイルに保存
    output_filename = f'race_results_{ymd}.json'
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 結果を {output_filename} に保存しました")
    
    return output_data


def fetch_single_race_result(race_id, ymd):
    """
    単一レースの結果を netkeiba.com から取得
    
    Args:
        race_id: レースID
        ymd: 日付（YYYYMMDD形式）
    
    Returns:
        dict: レース結果データ（配当・馬体重含む）
    """
    
    # NetKeiba のレース結果ページURL
    url = f'https://race.netkeiba.com/race/result.html?race_id={race_id}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 着順表を取得
        result_table = soup.select_one('table.race_table_01')
        
        if not result_table:
            print(f"❌ レース結果テーブルが見つかりません: {race_id}")
            return None
        
        # 1着、2着、3着の馬番を取得
        rows = result_table.select('tr')[1:]  # ヘッダー行をスキップ
        
        top_3 = []
        horse_weights = []
        
        for i, row in enumerate(rows[:3]):  # 上位3頭のみ
            cols = row.select('td')
            if len(cols) >= 8:
                horse_number = cols[2].get_text(strip=True)
                top_3.append(horse_number)
                
                # 馬体重を取得（例: "480(+4)"）
                weight_text = cols[14].get_text(strip=True) if len(cols) > 14 else ''
                horse_weights.append({
                    'rank': i + 1,
                    'horse_number': horse_number,
                    'weight': weight_text
                })
        
        if len(top_3) < 3:
            print(f"❌ 着順データが不足しています: {race_id}")
            return None
        
        sanrenpuku_result = '-'.join(sorted(top_3))
        
        # 払戻表を取得
        payout_table = soup.select_one('table.pay_table_01')
        payouts = {}
        sanrenpuku_payout = 0
        
        if payout_table:
            payout_rows = payout_table.select('tr')
            
            for row in payout_rows:
                th = row.select_one('th')
                if not th:
                    continue
                
                bet_type = th.get_text(strip=True)
                
                # 払戻金を取得
                payout_td = row.select('td.txt_r')
                if payout_td:
                    payout_text = payout_td[0].get_text(strip=True).replace(',', '').replace('円', '')
                    try:
                        payout_value = int(payout_text)
                        payouts[bet_type] = payout_value
                        
                        if bet_type == '三連複':
                            sanrenpuku_payout = payout_value
                    except ValueError:
                        pass
        
        # 天候・馬場状態を取得
        weather = ''
        track_condition = ''
        
        race_data_box = soup.select_one('.race_otherdata')
        if race_data_box:
            data_text = race_data_box.get_text()
            if '天候' in data_text:
                weather = data_text.split('天候:')[1].split('/')[0].strip()
            if '馬場' in data_text:
                track_condition = data_text.split('馬場:')[1].split('/')[0].strip()
        
        return {
            'sanrenpuku_result': sanrenpuku_result,
            'sanrenpuku_payout': sanrenpuku_payout,
            'payouts': payouts,
            'horse_weights': horse_weights,
            'weather': weather,
            'track_condition': track_condition
        }
        
    except Exception as e:
        print(f"❌ レース結果取得エラー ({race_id}): {e}")
        return None


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('使用方法: python fetch_race_results.py YYYYMMDD')
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    if len(ymd) != 8 or not ymd.isdigit():
        print('エラー: 日付は YYYYMMDD 形式で指定してください')
        sys.exit(1)
    
    fetch_race_results(ymd)
