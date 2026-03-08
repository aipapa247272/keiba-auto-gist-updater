import requests
from bs4 import BeautifulSoup
import json
import sys
import os
from datetime import datetime
import time
from itertools import combinations as iter_combinations

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
    
    # 日付チェック: 当日 or 前日データのみ許容（夜間バッチ未更新時のフォールバック対応）
    # Bug Fix ①: 翌朝に前日の latest_predictions.json が残っている場合に0レースになる問題を修正
    from datetime import datetime as _dt, timedelta as _td
    data_ymd = predictions_data.get('ymd')
    prev_ymd = (_dt.strptime(ymd, "%Y%m%d") - _td(days=1)).strftime("%Y%m%d")
    if data_ymd != ymd and data_ymd != prev_ymd:
        print(f"❌ エラー: 予想データの日付 ({data_ymd}) は当日({ymd})・前日({prev_ymd})のいずれとも一致しません")
        print(f"   処理を中断します。正しい予想ファイルを確認してください。")
        return None
    if data_ymd == prev_ymd:
        print(f"⚠️ 注意: 前日({data_ymd})の予想データを使用しています（当日データ未生成の可能性）")
    
    # 選定されたレースを取得
    selected_races = predictions_data.get('selected_predictions', [])
    
    if not selected_races:
        print(f"⚠️ 選定レース0件（全レース基準未達でスキップ）: {ymd}")
        # 予想なし日も正常終了として結果ファイルを生成する
        from datetime import datetime as _dt2
        no_pred_result = {
            "date": f"{ymd[:4]}/{ymd[4:6]}/{ymd[6:]}",
            "ymd": ymd,
            "generated_at": _dt2.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rescraped": False,
            "no_predictions": True,
            "reason": "選定レース0件（合成オッズ不足・断層なし等でスキップ）",
            "fund_management_v": "v13.1",
            "total_races": 0,
            "hit_count": 0,
            "miss_count": 0,
            "unavailable_count": 0,
            "no_pred_count": 0,
            "valid_races": 0,
            "total_investment": 0,
            "total_return": 0,
            "total_profit": 0,
            "hit_rate": 0.0,
            "recovery_rate": 0.0,
            "races": []
        }
        output_filename = f'race_results_{ymd}.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            import json as _json
            _json.dump(no_pred_result, f, ensure_ascii=False, indent=2)
        print(f"✅ {output_filename} を生成（予想なし）")
        return no_pred_result
    
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
        opponent_numbers_raw = []
        
        for h in axis_horses[:3]:
            uma_num = h.get('馬番')
            if uma_num is None or str(uma_num).strip() == '' or str(uma_num).strip().lower() == 'none':
                print(f"  ⚠️ 軸馬番が不正: {uma_num} → スキップ")
                continue
            axis_numbers_raw.append(str(uma_num).strip())
        
        # 相手馬番も取得
        opponent_horses_raw = betting_plan.get('相手', [])
        for h in opponent_horses_raw:
            uma_num = h.get('馬番')
            if uma_num is None or str(uma_num).strip() == '' or str(uma_num).strip().lower() == 'none':
                continue
            opponent_numbers_raw.append(str(uma_num).strip())
        
        # =====================================================
        # v12修正: 全買い目リストを優先使用（軸2頭+相手構成対応）
        # =====================================================
        all_combos_direct = betting_plan.get('全買い目', [])
        if all_combos_direct:
            predicted_combinations = all_combos_direct
            print(f"  🎯 予想: 全買い目{len(predicted_combinations)}通り (軸{axis_numbers_raw})")
        elif len(axis_numbers_raw) >= 3:
            # 旧ロジックフォールバック（軸3頭以上の場合）
            all_nums = axis_numbers_raw + opponent_numbers_raw
            axis_set = set(axis_numbers_raw)
            all_combos = [
                '-'.join(sorted(combo))
                for combo in iter_combinations(all_nums, 3)
                if any(n in axis_set for n in combo)
            ]
            predicted_combinations = all_combos
            print(f"  🎯 予想(旧): 軸{axis_numbers_raw} 相手{opponent_numbers_raw} → {len(predicted_combinations)}通り")
        else:
            print(f"  ⚠️ 買い目なし（全買い目リスト空、軸{len(axis_numbers_raw)}頭）→ 予想なしとして記録")
        
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
                'start_time': race.get('start_time', ''),
                'betting_plan': betting_plan,
                'status': '結果取得不可',
                'predicted': predicted_combinations,
                'actual': [],
                'hit': False,
                'investment': investment,
                'return': 0,
                'profit': -investment,
                'payouts': {},
                'horse_weights': [],
                'all_horses_result': [],   # Phase1
                'virtual_bets_result': {},  # テスト用仮想買い目
                'weather': '',
                'track_condition': ''
            })
            continue
        
        # ─── Phase1: DASスコア照合 ──────────────────────────
        all_horses_raw = race_result.get('all_horses_data', [])
        # 予測データ（軸+相手）からDASスコア辞書を作成
        das_score_map = {}
        for h in betting_plan.get('軸', []):
            num = str(h.get('馬番', '')).strip()
            score = h.get('スコア') or h.get('evaluation_score')
            if num and score is not None:
                das_score_map[num] = float(score)
        for h in betting_plan.get('相手', []):
            num = str(h.get('馬番', '')).strip()
            score = h.get('スコア') or h.get('evaluation_score')
            if num and score is not None:
                das_score_map[num] = float(score)
        # 全馬に DASスコアを設定（予測外馬は None のまま）
        for h in all_horses_raw:
            h['DASスコア'] = das_score_map.get(h['馬番'])
        # 役割ラベルも追加（軸/相手/予測外）
        axis_set_str = set(axis_numbers_raw)
        opp_set_str  = set(opponent_numbers_raw)
        for h in all_horses_raw:
            num = h['馬番']
            if num in axis_set_str:
                h['役割'] = '軸'
            elif num in opp_set_str:
                h['役割'] = '相手'
            else:
                h['役割'] = '予測外'
        all_horses_result = all_horses_raw
        # ─────────────────────────────────────────────────────

        # ─── 仮想買い目 払戻計算 ────────────────────────────
        virtual_bets_plan = race.get('virtual_bets_plan', {})
        # フォールバック: virtual_bets_planが空の場合 betting_planの軸馬から自動生成
        if not virtual_bets_plan:
            axis_list_vb = betting_plan.get('軸', [])
            axis_nums_vb = [str(h.get('馬番')) for h in axis_list_vb if h.get('馬番') is not None]
            if len(axis_nums_vb) >= 1:
                virtual_bets_plan['複勝_軸1'] = {'type': '複勝', '馬番': axis_nums_vb[0], '投資': 100}
            if len(axis_nums_vb) >= 2:
                virtual_bets_plan['複勝_軸2'] = {'type': '複勝', '馬番': axis_nums_vb[1], '投資': 100}
                n1 = min(axis_nums_vb[0], axis_nums_vb[1], key=int)
                n2 = max(axis_nums_vb[0], axis_nums_vb[1], key=int)
                virtual_bets_plan['ワイド_軸1-2'] = {'type': 'ワイド', '組み合わせ': f'{n1}-{n2}', '投資': 100}
                virtual_bets_plan['馬連_軸1-2']  = {'type': '馬連',  '組み合わせ': f'{n1}-{n2}', '投資': 100}
            if len(axis_nums_vb) >= 3:
                virtual_bets_plan['複勝_軸3'] = {'type': '複勝', '馬番': axis_nums_vb[2], '投資': 100}
                n1b = min(axis_nums_vb[1], axis_nums_vb[2], key=int)
                n2b = max(axis_nums_vb[1], axis_nums_vb[2], key=int)
                virtual_bets_plan['ワイド_軸2-3'] = {'type': 'ワイド', '組み合わせ': f'{n1b}-{n2b}', '投資': 100}
                virtual_bets_plan['馬連_軸2-3']  = {'type': '馬連',  '組み合わせ': f'{n1b}-{n2b}', '投資': 100}
            if virtual_bets_plan:
                print(f"  ℹ️ virtual_bets_plan を betting_planから自動生成: {list(virtual_bets_plan.keys())}")
        virtual_bets_result = {}
        actual_payouts = race_result.get('payouts', {})

        for bet_key, bet_info in virtual_bets_plan.items():
            bet_type = bet_info.get('type', '')
            investment_v = bet_info.get('投資', 100)
            payout_v = 0
            hit_v = False

            if bet_type == '複勝':
                # Bug Fix ③: 複勝払戻計算修正
                # 正しい計算式: 払戻オッズ(100円あたり) × 投資額 ÷ 100
                # 例: オッズ210円 × 投資300円 ÷ 100 = 630円
                horse_num = str(bet_info.get('馬番', ''))
                top3_list = (race_result.get('sanrenpuku_result') or '').split('-')
                hit_v = horse_num in top3_list
                if hit_v:
                    odds_per_100 = actual_payouts.get('複勝', 0)
                    payout_v = round(odds_per_100 * investment_v / 100)
                else:
                    payout_v = 0

            elif bet_type in ('ワイド', '馬連'):
                combo = bet_info.get('組み合わせ', '')
                combo_nums = set(combo.split('-'))
                top3_nums = set((race_result.get('sanrenpuku_result') or '').split('-'))
                if bet_type == 'ワイド':
                    # ワイド: 上位3頭中に2頭が含まれれば的中
                    if len(combo_nums & top3_nums) >= 2:
                        # Bug Fix ③: ワイド払戻計算修正 (オッズ×投資額÷100)
                        hit_v = True
                        odds_per_100 = actual_payouts.get('ワイド', 0)
                        payout_v = round(odds_per_100 * investment_v / 100)
                else:
                    # 馬連: 1着・2着の2頭が一致
                    top2_nums = set((race_result.get('sanrenpuku_result') or '').split('-')[:2])
                    if combo_nums == top2_nums:
                        # Bug Fix ③: 馬連払戻計算修正 (オッズ×投資額÷100)
                        hit_v = True
                        odds_per_100 = actual_payouts.get('馬連', 0)
                        payout_v = round(odds_per_100 * investment_v / 100)

            virtual_bets_result[bet_key] = {
                'type': bet_type,
                '投資': investment_v,
                '払戻': payout_v,
                '収支': payout_v - investment_v,
                '的中': hit_v
            }
        # ─────────────────────────────────────────────────────

        sanrenpuku_result = race_result.get('sanrenpuku_result', '')
        sanrenpuku_payout = race_result.get('sanrenpuku_payout', 0)
        payouts = race_result.get('payouts', {})
        
        # ── Bug Fix ④: 三連複払戻 多段フォールバック ──────────────────
        # payoutsから三連複を補完（キー名バリエーション対応）
        if not sanrenpuku_payout:
            for key in ('三連複', '3連複', 'Fuku3'):
                v = payouts.get(key, 0)
                if v:
                    sanrenpuku_payout = v
                    print(f"  💰 三連複払戻({key}から補完): ¥{v:,}")
                    break
        # それでも0 → NARサイトへ再スクレイピング（ワンショット）
        if not sanrenpuku_payout and race_result:
            _retry = fetch_single_race_result(race_id, ymd)
            if _retry and _retry.get('sanrenpuku_payout', 0):
                sanrenpuku_payout = _retry['sanrenpuku_payout']
                print(f"  🔄 三連複払戻(再取得成功): ¥{sanrenpuku_payout:,}")
            elif _retry:
                for key in ('三連複', '3連複'):
                    v = _retry.get('payouts', {}).get(key, 0)
                    if v:
                        sanrenpuku_payout = v
                        print(f"  🔄 三連複払戻(再取得payouts補完): ¥{v:,}")
                        break
        
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
        
        payout_missing = False
        if hit and return_amount == 0:
            # Bug Fix ④: 的中だが払戻額が取得できなかった
            payout_missing = True
            print(f"  ⚠️ 【払戻バグ検出】hit=True だが三連複払戻=0 → payout_missing=True")
            print(f"     race_id={race_id}  result={sanrenpuku_result}  payouts={payouts}")

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
            'start_time': race.get('start_time', ''),
            'betting_plan': betting_plan,
            'status': '的中' if hit else ('予想なし' if not predicted_combinations else '不的中'),
            'predicted': predicted_combinations,
            'actual': [sanrenpuku_result] if sanrenpuku_result else [],
            'result_sanrenpuku': sanrenpuku_result,
            'payout_sanrenpuku': sanrenpuku_payout,
            'hit': hit,
            'payout_missing': payout_missing,
            'investment': investment,
            'return': return_amount,
            'profit': profit,
            'payouts': race_result.get('payouts', {}),
            'horse_weights': race_result.get('horse_weights', []),
            'all_horses_result': all_horses_result,   # Phase1
            'virtual_bets_result': virtual_bets_result,  # テスト用仮想買い目
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
        
        # NARサイトはEUC-JPエンコーディング
        html_bytes = response.content
        html_text = None
        for enc in ['euc-jp', 'shift_jis', 'utf-8']:
            try:
                decoded = html_bytes.decode(enc)
                if '単勝' in decoded or 'ワイド' in decoded or '払戻' in decoded:
                    html_text = decoded
                    print(f"  📄 エンコーディング: {enc}")
                    break
            except Exception:
                continue
        if html_text is None:
            html_text = html_bytes.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_text, 'html.parser')
        
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
        all_horses_data = []  # Phase1: 全馬着順データ
        
        all_data_rows = [r for r in rows if r.select('td')]
        data_rows = all_data_rows[:3]
        
        # ─── 全馬データ取得（Phase1） ───────────────────────
        for i, row in enumerate(all_data_rows):
            cols = row.select('td')
            if len(cols) < 3:
                continue
            
            rank_text = cols[0].get_text(strip=True)
            # 取消・除外などはスキップ
            if not rank_text.isdigit():
                continue
            
            horse_num = cols[2].get_text(strip=True) if len(cols) > 2 else ''
            if not horse_num or not horse_num.isdigit():
                umaban = row.select_one('.Umaban')
                if umaban:
                    horse_num = umaban.get_text(strip=True)
            if not horse_num or not horse_num.isdigit():
                for col in cols[1:5]:
                    text = col.get_text(strip=True)
                    if text.isdigit() and 1 <= int(text) <= 18:
                        horse_num = text
                        break
            
            horse_name = cols[3].get_text(strip=True) if len(cols) > 3 else ''
            popularity = cols[9].get_text(strip=True) if len(cols) > 9 else ''
            if not popularity.isdigit():
                # フォールバック: 後ろから探す
                for col in reversed(cols[:12]):
                    t = col.get_text(strip=True)
                    if t.isdigit() and 1 <= int(t) <= 18:
                        popularity = t
                        break
            
            if horse_num and horse_num.isdigit():
                all_horses_data.append({
                    '馬番': horse_num,
                    '着順': int(rank_text),
                    '人気': int(popularity) if popularity.isdigit() else None,
                    '馬名': horse_name,
                    'DASスコア': None   # メインループで照合して設定
                })
        # ─────────────────────────────────────────────────────
        
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
        # NARのPayoutDetailTableは複数テーブルに分かれている場合があるのでselectで全取得
        local_tables = soup.select('table.Payout_Detail_Table')
        if local_tables:
            payout_tables.extend(local_tables)
            print(f"  📊 Payout_Detail_Table: {len(local_tables)}テーブル取得")
        
        # JRAページ用テーブル（summary属性で識別）
        central_tables = soup.select('table[summary="払い戻し"], table[summary="ワイド"]')
        if central_tables:
            payout_tables.extend(central_tables)
        
        # 追加フォールバック: NAR別パターン
        if not payout_tables:
            # payoff_tableやpay_tableクラスも試みる
            extra = soup.select('table.payoff_table, table.pay_table_01, table.Payout')
            if extra:
                payout_tables.extend(extra)
                print(f"  📊 fallback payout table: {len(extra)}テーブル取得")
        
        if not payout_tables:
            # 最終手段: thに券種名が含まれるtableを全探索
            for tbl in soup.find_all('table'):
                ths = tbl.select('th')
                th_texts = [th.get_text(strip=True) for th in ths]
                if any(t in th_texts for t in ['単勝', '複勝', '馬連', '三連複', '三連単']):
                    payout_tables.append(tbl)
                    print(f"  📊 th検索でpayoutテーブル発見")
                    break
        
        payouts = {}
        sanrenpuku_payout = 0

        import re as _re

        # trクラスで券種を識別（文字化けに依存しない確実な方法）
        TR_CLASS_MAP = {
            'Tansho':  '単勝',
            'Fukusho': '複勝',
            'Wakuren': '枠連',
            'Umaren':  '馬連',
            'Wide':    'ワイド',
            'Wakutan': '枠単',
            'Umatan':  '馬単',
            'Fuku3':   '三連複',
            'Tan3':    '三連単',
        }

        if payout_tables:
            for table in payout_tables:
                for row in table.select('tr'):
                    tr_classes = row.get('class', [])
                    # trクラスで券種を特定
                    bet_type = None
                    for cls in tr_classes:
                        if cls in TR_CLASS_MAP:
                            bet_type = TR_CLASS_MAP[cls]
                            break
                    # クラスで判定できなければthテキストにフォールバック
                    if not bet_type:
                        th = row.select_one('th')
                        if not th:
                            continue
                        raw = th.get_text(strip=True)
                        fallback_map = {
                            '単勝':'単勝','複勝':'複勝','枠連':'枠連','馬連':'馬連',
                            '馬単':'馬単','ワイド':'ワイド','三連複':'三連複','三連単':'三連単',
                            '3連複':'三連複','3連単':'三連単'
                        }
                        bet_type = fallback_map.get(raw)
                        if not bet_type:
                            continue

                    # td.Payout から払戻金を取得
                    payout_td = row.select_one('td.Payout')
                    if not payout_td:
                        all_td = row.select('td')
                        if len(all_td) < 2:
                            continue
                        payout_td = all_td[1]

                    payout_text = payout_td.get_text(separator='\n', strip=True)
                    payout_values = []
                    for seg in payout_text.split('\n'):
                        clean = seg.replace(',', '').replace('円', '').replace('¥', '').strip()
                        for num_str in _re.findall(r'\d+', clean):
                            try:
                                v = int(num_str)
                                if v >= 100:
                                    payout_values.append(v)
                            except ValueError:
                                pass

                    if payout_values:
                        if bet_type == '複勝':
                            final_payout = min(payout_values)
                        elif bet_type == 'ワイド':
                            final_payout = min(payout_values)  # 最小オッズを代表値
                        else:
                            final_payout = payout_values[0]

                        if bet_type not in payouts:  # 重複登録防止
                            payouts[bet_type] = final_payout

                        if bet_type == '三連複':
                            sanrenpuku_payout = final_payout
                            print(f"  💰 三連複払戻: ¥{final_payout:,}")
                        else:
                            print(f"  💴 {bet_type}: ¥{final_payout:,}")
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
            'all_horses_data': all_horses_data,   # Phase1: 全馬着順データ
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

