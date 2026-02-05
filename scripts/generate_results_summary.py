#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_results_summary.py - 結果サマリー生成スクリプト

race_results_{ymd}.json から的中状況と収支を集計し、
results_summary_{ymd}.json を生成する
"""

import json
import sys
from pathlib import Path
from datetime import datetime


# ====================================================================
# 的中判定
# ====================================================================
def check_hit(prediction, result):
    """
    予想と結果を照合して的中判定
    
    Args:
        prediction (dict): 予想データ
        result (dict): 結果データ
    
    Returns:
        dict: 的中判定結果
    """
    if not result or not result.get('着順'):
        return {
            "hit": False,
            "hit_type": None,
            "payout": 0,
            "reason": "結果データなし"
        }
    
    # 着順を取得
    rankings = result.get('着順', {})
    
    # 予想馬番を取得
    betting_plan = prediction.get('betting_plan', {})
    axis_horses = betting_plan.get('軸', [])
    
    if not axis_horses or len(axis_horses) < 3:
        return {
            "hit": False,
            "hit_type": None,
            "payout": 0,
            "reason": "予想データ不正"
        }
    
    # 軸馬の馬番
    axis_numbers = [h['馬番'] for h in axis_horses]
    
    # 1～3着を取得
    rank_1 = rankings.get('1', 0)
    rank_2 = rankings.get('2', 0)
    rank_3 = rankings.get('3', 0)
    
    # 3連複の的中判定（軸3頭が1～3着に入っているか）
    actual_top3 = sorted([rank_1, rank_2, rank_3])
    predicted_top3 = sorted(axis_numbers)
    
    if actual_top3 == predicted_top3:
        # 的中
        payout_info = result.get('払戻', {})
        sanrenpuku_payout = payout_info.get('三連複', 0)
        
        return {
            "hit": True,
            "hit_type": "三連複",
            "payout": sanrenpuku_payout,
            "reason": f"的中 {rank_1}-{rank_2}-{rank_3}"
        }
    else:
        return {
            "hit": False,
            "hit_type": None,
            "payout": 0,
            "reason": f"不的中 (実際: {rank_1}-{rank_2}-{rank_3}, 予想: {'-'.join(map(str, axis_numbers))})"
        }


# ====================================================================
# サマリー生成
# ====================================================================
def generate_summary(results_data, predictions_data):
    """
    結果サマリーを生成
    
    Args:
        results_data (dict): 結果データ
        predictions_data (dict): 予想データ
    
    Returns:
        dict: サマリーデータ
    """
    ymd = results_data.get('ymd', '')
    results = results_data.get('results', [])
    predictions = predictions_data.get('selected_predictions', [])
    
    # 照合
    summary_items = []
    total_investment = 0
    total_payout = 0
    hit_count = 0
    
    for prediction in predictions:
        race_id = prediction['race_id']
        investment = prediction.get('investment', 0)
        
        # 対応する結果を検索
        result = next(
            (r for r in results if r['race_id'] == race_id),
            None
        )
        
        # 的中判定
        hit_result = check_hit(prediction, result)
        
        total_investment += investment
        total_payout += hit_result['payout']
        
        if hit_result['hit']:
            hit_count += 1
        
        summary_items.append({
            "race_id": race_id,
            "race_name": prediction.get('race_name', '不明'),
            "venue": prediction.get('venue', '不明'),
            "investment": investment,
            "hit": hit_result['hit'],
            "hit_type": hit_result['hit_type'],
            "payout": hit_result['payout'],
            "profit": hit_result['payout'] - investment,
            "reason": hit_result['reason']
        })
    
    # 収支計算
    net_profit = total_payout - total_investment
    hit_rate = (hit_count / len(predictions) * 100) if predictions else 0
    recovery_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0
    
    return {
        "ymd": ymd,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    
    # ファイル存在チェック
    if not Path(results_file).exists():
        print(f"[ERROR] {results_file} が見つかりません")
        sys.exit(1)
    
    if not Path(predictions_file).exists():
        print(f"[ERROR] {predictions_file} が見つかりません")
        sys.exit(1)
    
    # データ読み込み
    with open(results_file, "r", encoding="utf-8") as f:
        results_data = json.load(f)
    
    with open(predictions_file, "r", encoding="utf-8") as f:
        predictions_data = json.load(f)
    
    print(f"[INFO] {results_file} を読み込みました")
    print(f"[INFO] {predictions_file} を読み込みました")
    
    # サマリー生成
    summary = generate_summary(results_data, predictions_data)
    
    # 保存
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] {output_file} を生成しました")
    
    # サマリー表示
    print(f"\n# 📊 結果サマリー")
    print(f"")
    print(f"**日付**: {ymd[:4]}/{ymd[4:6]}/{ymd[6:8]}")
    print(f"")
    print(f"## 📈 成績")
    print(f"")
    print(f"- **対象レース数**: {summary['summary']['total_races']}レース")
    print(f"- **的中**: {summary['summary']['hit_count']}レース")
    print(f"- **不的中**: {summary['summary']['miss_count']}レース")
    print(f"- **的中率**: {summary['summary']['hit_rate']}%")
    print(f"")
    print(f"## 💰 収支")
    print(f"")
    print(f"- **総投資額**: ¥{summary['summary']['total_investment']:,}円")
    print(f"- **総払戻額**: ¥{summary['summary']['total_payout']:,}円")
    print(f"- **純損益**: {'🟢' if summary['summary']['net_profit'] >= 0 else '🔴'} **¥{summary['summary']['net_profit']:,}円**")
    print(f"- **回収率**: {summary['summary']['recovery_rate']}%")
    print(f"")
    print(f"## 📋 詳細")
    print(f"")
    
    for i, detail in enumerate(summary['details'], 1):
        status = "✅" if detail['hit'] else "❌"
        print(f"### {status} レース {i}")
        print(f"")
        print(f"- **レース**: {detail['venue']} {detail['race_name']}")
        print(f"- **投資額**: ¥{detail['investment']:,}円")
        
        if detail['hit']:
            print(f"- **的中**: {detail['hit_type']}")
            print(f"- **払戻**: ¥{detail['payout']:,}円")
            print(f"- **収支**: 🟢 +¥{detail['profit']:,}円")
        else:
            print(f"- **結果**: {detail['reason']}")
            print(f"- **収支**: 🔴 -¥{detail['investment']:,}円")
        
        print(f"")
    
    print(f"---")
    print(f"\n✅ 完了")


if __name__ == "__main__":
    main()
