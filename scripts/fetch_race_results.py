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
        # ★ 修正v5: venue/race_name/race_num の取得ロジック修正
        venue = race.get('venue') or race.get('競馬場') or 'Unknown'
        race_name = race.get('race_name') or race.get('レース名') or 'Unknown'
        # race_id から race_num を抽出（末尾2桁）
        race_num = race_id[-2:] if race_id and len(race_id) >= 2 else 'Unknown'
        distance = race.get('距離', race.get('distance', ''))
        track = race.get('track', '')
        
        print(f"\n[{idx}/{len(selected_races)}] {venue} R{race_num} {race_name} (ID: {race_id})")
        
        # 予想買い目を取得
        # ★ 修正v3: betting_plan から軸馬を取得
        betting_plan = race.get('betting_plan', {})
        axis_horses = betting_plan.get('軸', [])
        
        # 軸馬の馬番から三連複の組み合わせを生成
        predicted_combinations = []
        if len(axis_horses) >= 3:
            axis_numbers = sorted([str(h.get('馬番', '')) for h in axis_horses[:3]])
            predicted_combinations = ['-'.join(axis_numbers)]
        
        # ★ 修正v4: 投資額を race から取得（キー名を 'investment' に修正）
        investment = race.get('investment', 2400)
        
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
    
    # ★ 修正: ymd から日付を生成
    date_obj = datetime.strptime(ymd, '%Y%m%d')
    date_str = date_obj.strftime('%Y/%m/%d')
    
    output_data = {
        'date': date_str,  # ★ 修正: YYYY/MM/DD 形式
        'ymd': ymd,
        'generated_at': date_obj.strftime('%Y-%m-%d %H:%M:%S'),  # ★ 修正
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


def get_venue_info(race_id):
    """
    レースIDから競馬場情報を取得
    返り値: (race_type, venue_name)
    - race_type: 'central'(中央競馬) または 'local'(地方競馬)
    - venue_name: 競馬場名
    """
    venue_code = race_id[4:6]
    
    # 中央競馬: 01-10
    if int(venue_code) <= 10:
        venues = {
            "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
            "05": "東京", "06": "中山", "07": "中京", "08": "京都",
            "09": "阪神", "10": "小倉"
        }
        return 'central', venues.get(venue_code, f"不明({venue_code})")
    
    # 地方競馬: 11以上
    local_venues = {
        "30": "門別", "35": "盛岡", "36": "水沢",
        "42": "浦和", "43": "船橋", "44": "大井", "45": "川崎",
        "46": "金沢", "47": "笠松", "48": "名古屋",
        "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"
    }
    return 'local', local_venues.get(venue_code, f"不明({venue_code})")


def fetch_single_race_result(race_id, ymd):
    """
    単一レースの結果を netkeiba.com から取得
    中央競馬と地方競馬の両方に対応
    """
    
    # 競馬場タイプを判定
    race_type, venue_name = get_venue_info(race_id)
    
    # URLを選択
    if race_type == 'central':
        base_url = 'https://race.netkeiba.com'
    else:
        base_url = 'https://nar.netkeiba.com'
    
    url = f'{base_url}/race/result.html?race_id={race_id}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': base_url,
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        print(f"  🏇 {race_type.upper()} - {venue_name}")
        print(f"  🔗 URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # デバッグ: ページタイトルを確認
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.get_text(strip=True)
            print(f"  📄 ページタイトル: {title_text}")
        
        # 着順表を取得（複数のセレクタを試行）
        result_table = None
        
        # セレクタ1: Shutuba_Table (地方競馬で使用)
        result_table = soup.select_one('table.Shutuba_Table')
        
        # セレクタ2: race_table_01 (中央競馬で使用)
        if not result_table:
            result_table = soup.select_one('table.race_table_01')
        
        # セレクタ3: RaceCommon_Table
        if not result_table:
            result_table = soup.select_one('table.RaceCommon_Table')
        
        # セレクタ4: 最初の大きなテーブル
        if not result_table:
            all_tables = soup.find_all('table')
            for table in all_tables:
                rows = table.find_all('tr')
                if len(rows) > 5:  # 5行以上あるテーブル
                    result_table = table
                    print(f"  ℹ️ 汎用テーブル検出 (行数: {len(rows)})")
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
            
            if len(cols) < 3:
                print(f"  ⚠️ {i+1}着のデータが不完全 (列数: {len(cols)})")
                continue
            
            # 馬番を取得（複数の方法を試行）
            horse_number = ''
            
            # 方法1: 着順が1位のtdを探し、その後の馬番tdを取得
            rank_td = cols[0].get_text(strip=True)
            if rank_td == str(i+1):  # 着順確認
                # 地方競馬: 通常2列目が馬番
                if len(cols) > 2:
                    horse_number = cols[2].get_text(strip=True)
                
                # 中央競馬: 場合によっては3列目
                if not horse_number.isdigit() and len(cols) > 3:
                    horse_number = cols[3].get_text(strip=True)
            
            # 方法2: Umaban クラス
            if not horse_number or not horse_number.isdigit():
                umaban = row.select_one('.Umaban')
                if umaban:
                    horse_number = umaban.get_text(strip=True)
            
            # 方法3: 数字のみのtdを探す
            if not horse_number or not horse_number.isdigit():
                for col in cols[1:5]:  # 最初の数列をスキャン
                    text = col.get_text(strip=True)
                    if text.isdigit() and 1 <= int(text) <= 18:
                        horse_number = text
                        break
            
            if horse_number and horse_number.isdigit():
                top_3.append(horse_number)
                print(f"  🐎 {i+1}着: {horse_number}番")
            else:
                print(f"  ⚠️ {i+1}着の馬番が取得できません")
            
            # 馬体重を取得
            weight_text = ''
            for col in cols[-5:]:  # 後方5列から馬体重を探す
                text = col.get_text(strip=True)
                if '(' in text and ')' in text:  # 馬体重の形式: 450(+2)
                    weight_text = text
                    break
            
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
        
        # 払戻表を取得（v12: 複数テーブル対応・8種全対応）
        payout_tables = []
        
        # 地方競馬のテーブルを優先取得
        local_table = soup.select_one('table.Payout_Detail_Table')
        if local_table:
            payout_tables.append(local_table)
        
        # 中央競馬のテーブル（払い戻し + ワイド）
        central_tables = soup.select('table[summary="払い戻し"], table[summary="ワイド"]')
        if central_tables:
            payout_tables.extend(central_tables)
        
        # フォールバック: pay_table_01
        if not payout_tables:
            fallback = soup.select_one('table.pay_table_01')
            if fallback:
                payout_tables.append(fallback)
        
        payouts = {}
        sanrenpuku_payout = 0
        
        # 券種の正規化マップ（8種対応）
        bet_type_map = {
            '単勝': '単勝', '複勝': '複勝', '枠連': '枠連', '馬連': '馬連',
            '馬単': '馬単', 'ワイド': 'ワイド', '三連複': '三連複', '三連単': '三連単',
            '3連複': '三連複', '3連単': '三連単'
        }
        
        if payout_tables:
            # 全テーブルから払戻データを抽出
            for table in payout_tables:
                payout_rows = table.select('tr')
                
                for row in payout_rows:
                    th = row.select_one('th')
                    if not th:
                        continue
                    
                    raw_bet_type = th.get_text(strip=True)
                    bet_type = bet_type_map.get(raw_bet_type, raw_bet_type)
                    
                    # 払戻金を取得
                    payout_td = row.select('td.txt_r, td')
                    payout_values = []
                    
                    if payout_td:
                        for td in payout_td:
                            payout_text = td.get_text(strip=True).replace(',', '').replace('円', '').replace('¥', '').replace('<br>', '\n')
                            # 数字のみ抽出
                            import re
                            numbers = re.findall(r'\d+', payout_text)
                            for num_str in numbers:
                                try:
                                    payout_value = int(num_str)
                                    if payout_value >= 100:  # 最低配当は100円
                                        payout_values.append(payout_value)
                                except ValueError:
                                    pass
                    
                    # 複勝は最小値、その他は最初の値
                    if payout_values:
                        if bet_type == '複勝':
                            final_payout = min(payout_values)
                        else:
                            final_payout = payout_values[0]
                        
                        payouts[bet_type] = final_payout
                        
                        if bet_type == '三連複':
                            sanrenpuku_payout = final_payout
                            print(f"  💰 三連複払戻: ¥{final_payout:,}")
        else:
            print(f"  ⚠️ 払戻テーブルが見つかりません")
        
        # 天候・馬場状態を取得
        weather = ''
        track_condition = ''
        
        # 複数のセレクタを試行
        race_data_box = soup.select_one('.RaceData01, .RaceData02, .race_otherdata')
        
        if race_data_box:
            data_text = race_data_box.get_text()
            
            # 天候
            import re
            weather_match = re.search(r'天候[:\s]*([^\s/]+)', data_text)
            if weather_match:
                weather = weather_match.group(1)
            
            # 馬場状態
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
