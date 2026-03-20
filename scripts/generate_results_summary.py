#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_results_summary.py - 結果サマリー生成スクリプト v2 (v12対応)

race_results_{ymd}.json と final_predictions_{ymd}.json を照合し、
results_summary_{ymd}.json を生成する

v12対応:
- 全買い目（フォーメーション）ベースの的中判定
- race_results は 'races' キーを使用
- actual着順は ['4-10-1'] 形式
"""

import json
import sys
from pathlib import Path
from datetime import datetime


# ====================================================================
# 的中判定 (v12対応)
# ====================================================================
def check_hit(prediction, result_race):
    """
    v12予想と結果を照合して的中判定
    
    Args:
        prediction (dict): final_predictionsの予想データ
        result_race (dict): race_resultsのレース結果
    
    Returns:
        dict: 的中判定結果
    """
    if not result_race:
        return {
            "hit": False,
            "hit_type": None,
            "payout": 0,
            "reason": "結果データなし"
        }
    
    # actual着順を取得 ['4-10-1'] or '4-10-1'
    actual_raw = result_race.get('actual', [])
    if not actual_raw:
        return {
            "hit": False,
            "hit_type": None,
            "payout": 0,
            "reason": "着順データなし"
        }
    
    actual_str = actual_raw[0] if isinstance(actual_raw, list) else actual_raw
    try:
        parts = [int(x) for x in actual_str.split('-')]
    except (ValueError, AttributeError):
        return {"hit": False, "hit_type": None, "payout": 0, "reason": f"着順フォーマットエラー: {actual_raw}"}
    
    if len(parts) < 3:
        return {"hit": False, "hit_type": None, "payout": 0, "reason": f"着順データ不足: {actual_str}"}
    
    actual_sorted = '-'.join(map(str, sorted(parts[:3])))
    
    # v12: 全買い目ベース判定
    bp = prediction.get('betting_plan', {})
    all_combos = bp.get('全買い目', [])
    if not all_combos:
        axis_nums = [str(h.get('馬番')).strip() for h in bp.get('軸', []) if h.get('馬番') is not None]
        opp_nums = [str(h.get('馬番')).strip() for h in bp.get('相手', []) if h.get('馬番') is not None]
        unique_nums = list(dict.fromkeys(axis_nums + opp_nums))
        if len(unique_nums) >= 3:
            import itertools
            all_combos = [list(combo) for combo in itertools.combinations(unique_nums, 3)]
    
    if all_combos:
        for combo in all_combos:
            try:
                combo_str = '-'.join(str(x) for x in combo) if isinstance(combo, (list, tuple)) else str(combo)
                combo_parts = [int(x) for x in combo_str.split('-')]
                sorted_combo = '-'.join(map(str, sorted(combo_parts)))
                if sorted_combo == actual_sorted:
                    payout = (result_race.get('return', 0)
                              or result_race.get('payout_sanrenpuku') 
                              or result_race.get('payouts', {}).get('三連複', 0) 
                              or 0)
                    return {
                        "hit": True,
                        "hit_type": "三連複",
                        "payout": payout,
                        "reason": f"的中 {actual_str}"
                    }
            except Exception:
                continue
        
        return {
            "hit": False,
            "hit_type": None,
            "payout": 0,
            "reason": f"不的中 (実際: {actual_str}, {len(all_combos)}点中)"
        }
    
    # フォールバック: 旧ロジック（軸3頭）
    axis_horses = bp.get('軸', [])
    if axis_horses and len(axis_horses) >= 3:
        axis_numbers = sorted([h.get('馬番', 0) for h in axis_horses[:3]])
        if axis_numbers == sorted(parts[:3]):
            payout = result_race.get('payout_sanrenpuku', 0) or 0
            return {"hit": True, "hit_type": "三連複", "payout": payout, "reason": f"的中(旧ロジック) {actual_str}"}
    
    return {
        "hit": False,
        "hit_type": None,
        "payout": 0,
        "reason": f"不的中 (実際: {actual_str})"
    }


# ====================================================================
# サマリー生成
# ====================================================================
def generate_summary(results_data, predictions_data):
    ymd = results_data.get('ymd', '')
    # v12: 'races' キー（旧: 'results'）
    result_races = results_data.get('races', results_data.get('results', []))
    predictions = []
    for p in predictions_data.get('selected_predictions', []):
        p2 = dict(p)
        p2['_prediction_type'] = 'recommend'
        predictions.append(p2)
    for p in predictions_data.get('reference_predictions', []):
        p2 = dict(p)
        p2['_prediction_type'] = 'reference'
        predictions.append(p2)
    
    summary_items = []
    total_investment = 0
    total_payout = 0
    hit_count = 0
    
    for prediction in predictions:
        race_id = prediction.get('race_id')
        investment = prediction.get('investment', prediction.get('betting_plan', {}).get('投資額', 0))
        prediction_type = prediction.get('_prediction_type', 'recommend')
        
        result_race = next(
            (r for r in result_races if r.get('race_id') == race_id),
            None
        )
        
        hit_result = check_hit(prediction, result_race)
        
        total_investment += investment
        total_payout += hit_result['payout']
        
        if hit_result['hit']:
            hit_count += 1
        
        # 予想の追加情報
        bp = prediction.get('betting_plan', {})
        combo_count = len(bp.get('全買い目', []))
        if combo_count == 0:
            axis_nums = [str(h.get('馬番')).strip() for h in bp.get('軸', []) if h.get('馬番') is not None]
            opp_nums = [str(h.get('馬番')).strip() for h in bp.get('相手', []) if h.get('馬番') is not None]
            unique_nums = list(dict.fromkeys(axis_nums + opp_nums))
            if len(unique_nums) >= 3:
                import itertools
                combo_count = len(list(itertools.combinations(unique_nums, 3)))
        synthetic_odds = prediction.get('合成オッズ', bp.get('合成オッズ', 0))
        
        summary_items.append({
            "race_id": race_id,
            "race_name": prediction.get('race_name', '不明'),
            "venue": prediction.get('venue', '不明'),
            "prediction_type": prediction_type,
            "investment": investment,
            "combo_count": combo_count,
            "synthetic_odds": synthetic_odds,
            "hit": hit_result['hit'],
            "hit_type": hit_result['hit_type'],
            "payout": hit_result['payout'],
            "profit": hit_result['payout'] - investment,
            "reason": hit_result['reason']
        })
    
    net_profit = total_payout - total_investment
    hit_rate = (hit_count / len(predictions) * 100) if predictions else 0
    recovery_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0
    
    return {
        "ymd": ymd,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "logic_version": "v12",
        "summary": {
            "total_races": len(predictions),
            "hit_count": hit_count,
            "miss_count": len(predictions) - hit_count,
            "hit_rate": round(hit_rate, 1),
            "total_investment": total_investment,
            "total_payout": total_payout,
            "net_profit": net_profit,
            "recovery_rate": round(recovery_rate, 1)
        },
        "details": summary_items
    }


# ====================================================================
# メイン処理
# ====================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_results_summary.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    results_file = f"race_results_{ymd}.json"
    predictions_file = f"final_predictions_{ymd}.json"
    output_file = f"results_summary_{ymd}.json"
    
    if not Path(results_file).exists():
        print(f"[ERROR] {results_file} が見つかりません")
        sys.exit(1)
    
    if not Path(predictions_file).exists():
        print(f"[ERROR] {predictions_file} が見つかりません")
        sys.exit(1)
    
    with open(results_file, "r", encoding="utf-8") as f:
        results_data = json.load(f)
    
    with open(predictions_file, "r", encoding="utf-8") as f:
        predictions_data = json.load(f)
    
    print(f"[INFO] {results_file} を読み込みました")
    print(f"[INFO] {predictions_file} を読み込みました ({len(predictions_data.get('selected_predictions', []))}予想)")
    
    summary = generate_summary(results_data, predictions_data)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    s = summary['summary']
    print(f"[SUCCESS] {output_file} を生成しました")
    print(f"  的中: {s['hit_count']}/{s['total_races']} ({s['hit_rate']}%)")
    print(f"  投資: ¥{s['total_investment']:,}  回収: ¥{s['total_payout']:,}  損益: ¥{s['net_profit']:,}")
    print(f"  ROI: {s['recovery_rate']}%")


if __name__ == "__main__":
    main()
