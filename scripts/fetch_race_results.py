#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# fetch_race_results.py v11 - 払戻金全券種対応版（v5ベース）
# v5からの変更点:
# - 複数払戻テーブルを探索（中央競馬は2テーブル）
# - 複勝は最小値を取得
# - 全券種対応（単勝、複勝、枠連、馬連、馬単、ワイド、三連複、三連単）


def load_cancellation_info(ymd):
    """
    開催中止情報を読み込む
    
    Args:
        ymd (str): 対象日付（YYYYMMDD）
    
    Returns:
        dict: 開催中止情報
    """
    try:
        with open(f'cancellation_info_{ymd}.json', 'r', encoding='utf-8') as f:
            info = json.load(f)
            print(f"📋 開催中止情報を読み込みました")
            if info.get('is_cancelled'):
                print(f"   理由: {info.get('reason', '不明')}")
                venues = info.get('venues', [])
                if venues:
                    print(f"   対象: {', '.join(venues)}")
            return info
    except FileNotFoundError:
        print(f"📋 開催中止情報なし（通常開催）")
        return {"is_cancelled": False}
    except Exception as e:
        print(f"⚠️ 開催中止情報の読み込みエラー: {e}")
        return {"is_cancelled": False}

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
    
    # 開催中止情報を読み込む
    cancellation_info = load_cancellation_info(ymd)
    
    print(f"\n{'='*50}")
    print(f"📅 対象日付: {ymd[:4]}/{ymd[4:6]}/{ymd[6:8]}")
    print(f"{'='*50}\n")
    
    # 予想データを読み込む
    try:
        with open('latest_predictions.json', 'r', encoding='utf-8') as f:
            predictions = json.load(f)
    except FileNotFoundError:
        print("❌ エラー: latest_predictions.json が見つかりません")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSONデコードエラー: {e}")
        return None
    
    # 日付検証
    pred_date = predictions.get('date', '')
    expected_date = f"{ymd[:4]}/{ymd[4:6]}/{ymd[6:8]}"
    
    if pred_date != expected_date:
        print(f"⚠️ 警告: 予想の対象日付（{pred_date}）が指定日付（{expected_date}）と一致しません")
    
    selected = predictions.get('selected_predictions', [])
    
    if not selected:
        print("❌ エラー: 予想データが空です")
        return None
    
    print(f"📊 対象レース数: {len(selected)}\n")
    
    results = []
    hit_count = 0
    miss_count = 0
    unavailable_count = 0
    total_investment = 0
    total_return = 0
    
    for i, race in enumerate(selected, 1):
        race_id = race.get('race_id', '')
        venue = race.get('venue', '不明')
        race_name = race.get('race_name', '不明')
        race_num = race.get('race_num', '')
        
        print(f"[{i}/{len(selected)}] {venue} 第{str(race_num).zfill(2)}競走'{race_name}' ")
        
        betting_plan = race.get('betting_plan', {})
        axis_list = betting_plan.get('軸', betting_plan.get('axis', []))
        axis_horses = [horse['馬番'] if isinstance(horse, dict) else horse for horse in axis_list]

        if not axis_horses:
            print("  ⚠️ 軸馬が指定されていません")
            continue
        
        predicted = '-'.join(map(str, axis_horses))
        
        investment = race.get('investment', betting_plan.get('investment_amount', 0))

        total_investment += investment
        
        # 結果を取得
        race_result = fetch_single_race_result(race_id)
        
        if not race_result:
            # 開催中止情報をチェック
            status = "結果取得不可"
            
            if cancellation_info.get('is_cancelled'):
                cancelled_venues = cancellation_info.get('venues', [])
                reason = cancellation_info.get('reason', '開催中止')
                
                # venue が中止対象に含まれるか、または全会場中止の場合
                if not cancelled_venues or venue in cancelled_venues:
                    status = reason
                    print(f"  ⚠️ {reason}")
            
            unavailable_count += 1
            results.append({
                'race_id': race_id,
                'venue': venue,
                'race_num': race_num,
                'race_name': race_name,
                'distance': race.get('distance', ''),
                'track': race.get('track', ''),
                'status': status,
                'predicted': predicted,
                'investment': investment,
                'return': 0,
                'profit': -investment
            })
            continue
        
        actual = race_result['sanrenpuku_result']
        payout = race_result['sanrenpuku_payout']
        
        hit = (sorted(axis_horses) == sorted([int(x) for x in actual.split('-')]))
        
        if hit:
            hit_count += 1
            status = '的中'
            race_return = payout
            total_return += race_return
            print(f"  🎯 的中！ ¥{payout:,}")
        else:
            miss_count += 1
            status = '不的中'
            race_return = 0
            print(f"  ❌ 不的中")
        
        profit = race_return - investment
        
        results.append({
            'race_id': race_id,
            'venue': venue,
            'race_num': race_num,
            'race_name': race_name,
            'distance': race.get('distance', ''),
            'track': race.get('track', ''),
            'status': status,
            'predicted': predicted,
            'actual': actual,
            'result_sanrenpuku': actual,
            'payout_sanrenpuku': payout,
            'hit': hit,
            'investment': investment,
            'return': race_return,
            'profit': profit,
            'payouts': race_result['payouts'],
            'horse_weights': race_result['horse_weights'],
            'weather': race_result['weather'],
            'track_condition': race_result['track_condition']
        })
        
        # レート制限
        time.sleep(2)
    
    total_profit = total_return - total_investment
    total_races = len(results)
    hit_rate = (hit_count / total_races * 100) if total_races > 0 else 0
    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0
    
    summary = {
        'date': expected_date,
        'total_races': total_races,
        'hit_count': hit_count,
        'miss_count': miss_count,
        'unavailable_count': unavailable_count,
        'total_investment': total_investment,
        'total_return': total_return,
        'total_profit': total_profit,
        'hit_rate': round(hit_rate, 1),
        'recovery_rate': round(recovery_rate, 1),
        'races': results,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    output_file = f'race_results_{ymd}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"📊 集計結果")
    print(f"{'='*50}")
    print(f"  対象レース: {total_races}R")
    print(f"  的中: {hit_count}R / 不的中: {miss_count}R / 結果未取得: {unavailable_count}R")
    print(f"  投資額: ¥{total_investment:,}")
    print(f"  払戻: ¥{total_return:,}")
    print(f"  損益: {'¥' if total_profit >= 0 else '-¥'}{abs(total_profit):,}")
    print(f"  的中率: {hit_rate:.1f}%")
    print(f"  回収率: {recovery_rate:.1f}%")
    print(f"\n💾 結果を {output_file} に保存しました")
    
    return summary


def get_venue_info(race_id):
    """
    レースIDから競馬場情報を取得
    """
    venue_code = race_id[4:6]
    
    venue_map = {
        '01': ('中央', '札幌'),
        '02': ('中央', '函館'),
        '03': ('中央', '福島'),
        '04': ('中央', '新潟'),
        '05': ('中央', '東京'),
        '06': ('中央', '中山'),
        '07': ('中央', '中京'),
        '08': ('中央', '京都'),
        '09': ('中央', '阪神'),
        '10': ('中央', '小倉'),
        '30': ('地方', '門別'),
        '35': ('地方', '盛岡'),
        '36': ('地方', '水沢'),
        '42': ('地方', '浦和'),
        '43': ('地方', '船橋'),
        '44': ('地方', '大井'),
        '45': ('地方', '川崎'),
        '46': ('地方', '金沢'),
        '47': ('地方', '笠松'),
        '48': ('地方', '名古屋'),
        '50': ('地方', '園田'),
        '51': ('地方', '姫路'),
        '54': ('地方', '高知'),
        '55': ('地方', '佐賀'),
    }
    
    return venue_map.get(venue_code, ('不明', '不明'))


def fetch_single_race_result(race_id):
    """
    個別レースの結果を取得
    """
    race_type, venue_name = get_venue_info(race_id)
    
    if race_type == '中央':
        url = f'https://race.netkeiba.com/race/result.html?race_id={race_id}'
    else:
        url = f'https://nar.netkeiba.com/race/result.html?race_id={race_id}'
    
    print(f"  🔍 結果取得: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 結果テーブルを取得
        result_table = soup.select_one('table.race_table_01, table.Shutuba_Table')
        
        if not result_table:
            print(f"  ⚠️ 結果テーブルが見つかりません")
            return None
        
        rows = result_table.select('tr')
        
        if len(rows) < 4:
            print(f"  ⚠️ 結果データが不足")
            return None
        
        top_3 = []
        horse_weights = []
        
        for i in range(3):
            row = rows[i + 1]
            cols = row.select('td')
            
            if not cols:
                continue
            
            horse_number = ''
            
            # 複数の方法で馬番を取得
            rank_col = cols[0] if cols else None
            if rank_col and rank_col.get_text(strip=True).isdigit():
                next_col_idx = 1
                if len(cols) > next_col_idx:
                    horse_number = cols[next_col_idx].get_text(strip=True)
            
            if not horse_number or not horse_number.isdigit():
                umaban_span = row.select_one('.Umaban')
                if umaban_span:
                    horse_number = umaban_span.get_text(strip=True)
            
            if not horse_number or not horse_number.isdigit():
                for col in cols[1:5]:
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
            print(f"  ❌ 上位3頭のデータが不足 (取得数: {len(top_3)})")
            return None
        
        sanrenpuku_result = '-'.join(sorted(top_3))
        print(f"  🎯 三連複: {sanrenpuku_result}")
        
                # 払戻表を取得（v11: 複数テーブル対応）
        payout_tables = []
        
        # 地方競馬
        local_table = soup.select_one('table.Payout_Detail_Table')
        if local_table:
            payout_tables.append(local_table)
        
        # 中央競馬（2テーブル）
        central_tables = soup.select('table[summary="払い戻し"], table[summary="ワイド"]')
        if central_tables:
            payout_tables.extend(central_tables)
        
        # フォールバック
        if not payout_tables:
            fallback = soup.select_one('table.pay_table_01')
            if fallback:
                payout_tables.append(fallback)
        
        payouts = {}
        sanrenpuku_payout = 0
        
        # 券種の正規化マップ
        bet_type_map = {
            '単勝': '単勝',
            '複勝': '複勝',
            '枠連': '枠連',
            '馬連': '馬連',
            '馬単': '馬単',
            'ワイド': 'ワイド',
            '三連複': '三連複',
            '3連複': '三連複',
            '三連単': '三連単',
            '3連単': '三連単'
        }
        
        if payout_tables:
            # 全テーブルから行を収集
            all_payout_rows = []
            for table in payout_tables:
                all_payout_rows.extend(table.select('tr'))
            
            payout_rows = all_payout_rows
            
            for row in payout_rows:
                th = row.select_one('th')
                if not th:
                    continue
                
                bet_type_raw = th.get_text(strip=True)
                bet_type = bet_type_map.get(bet_type_raw, bet_type_raw)
                
                # 払戻金を取得
                payout_td = row.select('td.txt_r, td')
                
                if payout_td:
                    payout_values = []
                    for td in payout_td:
                        payout_text = td.get_text(strip=True).replace(',', '').replace('円', '').replace('¥', '')
                        # 数字のみ抽出
                        import re
                        numbers = re.findall(r'\d+', payout_text)
                        for num in numbers:
                            try:
                                payout_value = int(num)
                                if payout_value >= 100:
                                    payout_values.append(payout_value)
                            except ValueError:
                                pass
                    
                    if payout_values:
                        # 複勝は最小値、それ以外は最初の値
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
