import requests
from bs4 import BeautifulSoup
import json
import sys
from datetime import datetime
import time

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
        print(f"❌ エラー: latest_predictions.json が見つかりません")
        return None
    
    # 日付が一致するか確認
    if predictions_data.get('ymd') != ymd:
        print(f"⚠️ 警告: 予想データの日付 ({predictions_data.get('ymd')}) と指定日付 ({ymd}) が一致しません")
    
    # 選定されたレースを取得
    selected_races = predictions_data.get('selected_predictions', [])
    
    if not selected_races:
        print(f"❌ エラー: 選定レースが見つかりません")
        return None
    
    print(f"📊 {len(selected_races)} レースの結果を取得します...")
    
    results = []
    
    for idx, race in enumerate(selected_races, 1):
        race_id = race.get('race_id')
        venue = race.get('venue', 'Unknown')
        race_name = race.get('race_name', 'Unknown')
        race_num = race.get('race_num', 'Unknown')
        distance = race.get('distance', '')
        track = race.get('track', '')
        
        print(f"\n[{idx}/{len(selected_races)}] {venue} {race_name} (ID: {race_id})")
        
        # 予想買い目を取得
        betting = race.get('betting_suggestions', {}).get('main', {})
        predicted_combinations = betting.get('combinations', [])
        investment = betting.get('total_investment', 100)
        
        # レース結果を取得
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
        
        # 三連複の払戻を取得
        sanrenpuku_result = race_result.get('sanrenpuku_result', '')
        sanrenpuku_payout = race_result.get('sanrenpuku_payout', 0)
        
        # 的中判定
        hit = False
        return_amount = 0
        
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
            print(f"  ❌ 不的中")
        
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
        
        # レート制限対策（次のリクエストまで1秒待機）
        time.sleep(1)
    
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
    
    print(f"\n{'='*50}")
    print(f"📊 結果サマリー")
    print(f"{'='*50}")
    print(f"総レース数: {total_races}")
    print(f"的中: {hit_count} / 不的中: {miss_count} / 取得不可: {unavailable_count}")
    print(f"投資額: ¥{total_investment:,}")
    print(f"払戻額: ¥{total_return:,}")
    print(f"収支: {'+' if total_profit >= 0 else ''}¥{total_profit:,}")
    print(f"的中率: {hit_rate:.1f}%")
    print(f"回収率: {recovery_rate:.1f}%")
    print(f"{'='*50}\n")
    
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
    """
    
    url = f'https://race.netkeiba.com/race/result.html?race_id={race_id}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://race.netkeiba.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        print(f"  🔗 URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # デバッグ: ページタイトルを確認
        page_title = soup.find('title')
        if page_title:
            print(f"  📄 ページタイトル: {page_title.get_text(strip=True)}")
        
        # 着順表を取得（複数のセレクタを試行）
        result_table = None
        
        # セレクタ1: race_table_01
        result_table = soup.select_one('table.race_table_01')
        
        # セレクタ2: Race_Result_Table
        if not result_table:
            result_table = soup.select_one('table.Race_Result_Table')
        
        # セレクタ3: ResultRefund
        if not result_table:
            result_table = soup.select_one('div.ResultRefund table')
        
        # セレクタ4: 最初の大きなテーブル
        if not result_table:
            all_tables = soup.find_all('table')
            for table in all_tables:
                if len(table.find_all('tr')) > 5:  # 5行以上あるテーブル
                    result_table = table
                    break
        
        if not result_table:
            print(f"  ❌ レース結果テーブルが見つかりません")
            # デバッグ: ページの一部を出力
            print(f"  📝 ページの最初の500文字:")
            print(soup.get_text()[:500])
            return None
        
        print(f"  ✅ 結果テーブル発見")
        
        # 着順データを取得
        rows = result_table.select('tr')
        
        if len(rows) < 4:  # ヘッダー含めて最低4行必要
            print(f"  ❌ 着順データが不足 (行数: {len(rows)})")
            return None
        
        top_3 = []
        horse_weights = []
        
        # ヘッダー行をスキップして上位3頭を取得
        data_rows = [r for r in rows if r.select('td')][:3]
        
        for i, row in enumerate(data_rows):
            cols = row.select('td')
            
            if len(cols) < 8:
                print(f"  ⚠️ {i+1}着のデータが不完全")
                continue
            
            # 馬番を取得（複数の方法を試行）
            horse_number = ''
            
            # 方法1: 2番目のtd
            if len(cols) > 2:
                horse_number = cols[2].get_text(strip=True)
            
            # 方法2: Umaban クラス
            if not horse_number:
                umaban = row.select_one('.Umaban')
                if umaban:
                    horse_number = umaban.get_text(strip=True)
            
            if horse_number:
                top_3.append(horse_number)
                print(f"  🐎 {i+1}着: {horse_number}番")
            
            # 馬体重を取得
            weight_text = ''
            if len(cols) > 14:
                weight_text = cols[14].get_text(strip=True)
            
            if weight_text:
                horse_weights.append({
                    'rank': i + 1,
                    'horse_number': horse_number,
                    'weight': weight_text
                })
        
        if len(top_3) < 3:
            print(f"  ❌ 上位3頭のデータが不足 (取得数: {len(top_3)})")
            return None
        
        sanrenpuku_result = '-'.join(sorted(top_3))
        print(f"  🎯 三連複: {sanrenpuku_result}")
        
        # 払戻表を取得
        payout_table = soup.select_one('table.pay_table_01')
        if not payout_table:
            payout_table = soup.select_one('table.Payout_Detail_Table')
        
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
                if not payout_td:
                    payout_td = row.select('td')
                
                if payout_td:
                    payout_text = payout_td[0].get_text(strip=True).replace(',', '').replace('円', '').replace('¥', '')
                    try:
                        payout_value = int(payout_text)
                        payouts[bet_type] = payout_value
                        
                        if bet_type == '三連複':
                            sanrenpuku_payout = payout_value
                            print(f"  💰 三連複払戻: ¥{payout_value:,}")
                    except ValueError:
                        pass
        else:
            print(f"  ⚠️ 払戻テーブルが見つかりません")
        
        # 天候・馬場状態を取得
        weather = ''
        track_condition = ''
        
        race_data_box = soup.select_one('.race_otherdata')
        if not race_data_box:
            race_data_box = soup.select_one('.RaceData01')
        
        if race_data_box:
            data_text = race_data_box.get_text()
            if '天候' in data_text:
                weather = data_text.split('天候:')[1].split('/')[0].strip() if '天候:' in data_text else ''
            if '馬場' in data_text:
                track_condition = data_text.split('馬場:')[1].split('/')[0].strip() if '馬場:' in data_text else ''
        
        return {
            'sanrenpuku_result': sanrenpuku_result,
            'sanrenpuku_payout': sanrenpuku_payout,
            'payouts': payouts,
            'horse_weights': horse_weights,
            'weather': weather,
            'track_condition': track_condition
        }
        
    except requests.RequestException as e:
        print(f"  ❌ ネットワークエラー: {e}")
        return None
    except Exception as e:
        print(f"  ❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
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
