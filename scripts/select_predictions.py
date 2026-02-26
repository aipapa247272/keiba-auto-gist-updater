#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新予想ロジック対応: レース選定スクリプト
修正日: 2026/02/22
変更点: 
- 穴候補の計算式を修正: 予想対象総頭数 = (出馬数 ÷ 2) + 1
- 穴候補 = 予想対象総頭数 - 軸3頭
- 三連複フォーメーションの組み合わせ数を正確に計算
"""

import json
import sys
import os
from datetime import datetime
from math import comb
from itertools import combinations as iter_combinations

def generate_reason(horse_data):
    """予想根拠を生成"""
    reasons = []
    breakdown = horse_data.get('新スコア_内訳', {})
    
    if breakdown.get('前走人気', 0) >= 90:
        reasons.append("前走1-2位人気")
    elif breakdown.get('前走人気', 0) >= 70:
        reasons.append("前走3-5位人気")
    
    if breakdown.get('馬体重増減', 0) >= 80:
        reasons.append("体重減で好調")
    elif breakdown.get('馬体重増減', 0) <= 30:
        reasons.append("体重増で不安")
    
    if breakdown.get('経験値', 0) >= 80:
        reasons.append("実績豊富")
    
    if breakdown.get('騎手厩舎', 0) >= 90:
        reasons.append("好騎手")
    
    if breakdown.get('距離馬場適性', 0) >= 90:
        reasons.append("適性抜群")
    
    if breakdown.get('脚質', 0) >= 90:
        reasons.append("展開有利")
    
    if not reasons:
        score = horse_data.get('新スコア', 0)
        reasons.append("総合力高い" if score >= 80 else "堅実な評価" if score >= 60 else "穴候補")
    
    return "、".join(reasons)

def calculate_turbulence(race):
    """波乱度を計算"""
    horses = race.get('horses', [])
    if not horses:
        return "中"
    
    scores = [h.get('新スコア', 0) for h in horses if h.get('新スコア')]
    if not scores or len(scores) < 3:
        return "中"
    
    scores.sort(reverse=True)
    top_3_avg = sum(scores[:3]) / 3
    score_diff = scores[0] - scores[2]
    
    if top_3_avg >= 70 and score_diff >= 10:
        return "低"
    elif top_3_avg >= 55 or score_diff >= 5:
        return "中"
    else:
        return "高"

def generate_betting_plan(race):
    """三連複フォーメーションの買い目を生成（修正版）"""
    horses = race.get('horses', [])
    sorted_horses = sorted(horses, key=lambda h: h.get('新スコア', 0), reverse=True)
    
    # 出馬数
    num_horses = len(horses)
    
    # 予想対象の総頭数: (出馬数 ÷ 2) + 1
    total_predicted = (num_horses // 2) + 1
    
    # 予想対象馬を選出
    top_candidates = sorted_horses[:min(total_predicted, len(sorted_horses))]
    
    # 軸: 上位3頭
    axis_horses = top_candidates[:3]
    
    # 穴候補: 4位以降
    opponent_horses = top_candidates[3:]
    
    # 組み合わせ数: C(軸数+相手数, 3) - C(相手数, 3) ← 軸1頭以上含む全組み合わせ
    num_axis = len(axis_horses)
    num_opponents = len(opponent_horses)
    combinations = comb(num_axis + num_opponents, 3) - comb(num_opponents, 3)
    investment = combinations * 100
    
    betting_plan = {
        "軸": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": ["◎", "○", "▲"][i],
                "スコア": h.get('新スコア', 0),
                "内訳": h.get('新スコア_内訳', {}),
                "根拠": generate_reason(h)
            }
            for i, h in enumerate(axis_horses)
        ],
        "相手": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": "△",
                "スコア": h.get('新スコア', 0),
                "根拠": generate_reason(h)
            }
            for h in opponent_horses
        ],
        "買い目タイプ": "三連複フォーメーション（軸1-2頭流し）",
        "組み合わせ数": combinations,
        "全買い目": [
            '-'.join(sorted(str(n) for n in combo))
            for combo in iter_combinations(
                [h.get('馬番') for h in axis_horses] +
                [h.get('馬番') for h in opponent_horses],
                3
            )
            if any(str(h.get('馬番')) in [str(x) for x in combo] for h in axis_horses)
        ]
    }
    
    return betting_plan, investment

def select_races(race_data, max_races=9999):  # テスト運用: 上限撤廃
    """予想対象レースを選定"""
    races = race_data.get('races', [])
    selected = []
    skipped = []
    turbulence_counts = {"低": 0, "中": 0, "高": 0}
    
    for race in races:
        horses = race.get('horses', [])
        
        if len(horses) < 8:
            skipped.append({"race_id": race.get('race_id'), "reason": f"出馬数不足({len(horses)}頭)"})
            continue
        
        horses_with_score = [h for h in horses if h.get('新スコア')]
        if len(horses_with_score) < len(horses) * 0.8:
            skipped.append({"race_id": race.get('race_id'), "reason": "新スコアデータ不足"})
            continue
        
        scores = [h.get('新スコア', 0) for h in horses_with_score]
        top_3_scores = sorted(scores, reverse=True)[:3]
        evaluation_score = sum(top_3_scores) / 3 if len(top_3_scores) >= 3 else 0
        data_quality = int((len(horses_with_score) / len(horses)) * 20)
        
        turbulence = calculate_turbulence(race)
        betting_plan, investment = generate_betting_plan(race)
        
        if evaluation_score >= 50 and data_quality >= 10:
            # スコア帯分類
            if evaluation_score >= 90:
                score_tier = "S"
            elif evaluation_score >= 80:
                score_tier = "A"
            elif evaluation_score >= 70:
                score_tier = "B"
            else:
                score_tier = "C"

            # 仮想買い目プラン（複勝・ワイド・馬連）
            axis_list = betting_plan.get("軸", [])
            axis_nums = [str(h.get("馬番")) for h in axis_list if h.get("馬番") is not None]
            virtual_bets_plan = {}
            if len(axis_nums) >= 1:
                virtual_bets_plan["複勝_軸1"] = {
                    "type": "複勝", "馬番": axis_nums[0], "投資": 100
                }
            if len(axis_nums) >= 2:
                virtual_bets_plan["複勝_軸2"] = {
                    "type": "複勝", "馬番": axis_nums[1], "投資": 100
                }
                virtual_bets_plan["ワイド_軸1-2"] = {
                    "type": "ワイド",
                    "組み合わせ": f"{min(axis_nums[0],axis_nums[1],key=int)}-{max(axis_nums[0],axis_nums[1],key=int)}",
                    "投資": 100
                }
                virtual_bets_plan["馬連_軸1-2"] = {
                    "type": "馬連",
                    "組み合わせ": f"{min(axis_nums[0],axis_nums[1],key=int)}-{max(axis_nums[0],axis_nums[1],key=int)}",
                    "投資": 100
                }

            selected.append({
                "race_id": race.get('race_id'),
                "race_name": race.get('レース名', '不明'),
                "venue": race.get('競馬場', '不明'),
                "distance": race.get('距離'),
                "track": race.get('トラック'),
                "start_time": race.get('発走時刻'),
                "turbulence": turbulence,
                "evaluation_score": round(evaluation_score, 2),
                "score_tier": score_tier,
                "top_3_avg": round(sum(top_3_scores) / 3, 2),
                "data_quality": data_quality,
                "betting_plan": betting_plan,
                "investment": investment,
                "virtual_bets_plan": virtual_bets_plan
            })
            turbulence_counts[turbulence] += 1
        else:
            skipped.append({"race_id": race.get('race_id'), "reason": f"評価不足"})
    
    # テスト運用: 全波乱帯を evaluation_score 降順で全選定（上限 max_races まで）
    final_selected = sorted(selected, key=lambda r: r["evaluation_score"], reverse=True)[:max_races]
    
    return final_selected, skipped, turbulence_counts

def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python select_predictions.py <ymd>")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    output_file = f"final_predictions_{ymd}.json"
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            race_data = json.load(f)
        
        print(f"[INFO] {input_file} を読み込みました")
        
        selected_races, skipped_races, turbulence_counts = select_races(race_data)
        total_investment = sum(r["investment"] for r in selected_races)
        
        output_data = {
            "ymd": ymd,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_races": len(race_data.get('races', [])),
            "selected_races": len(selected_races),
            "skipped_races": len(skipped_races),
            "summary": {
                "turbulence": turbulence_counts,
                "total_investment": total_investment
            },
            "selected_predictions": selected_races
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        with open("latest_predictions.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SUCCESS] final_predictions_{ymd}.json を生成しました")
        print(f"[SUCCESS] latest_predictions.json も生成しました")
        print(f"\n{'='*60}")
        print(f"📊 本日の予想サマリー ({ymd[:4]}/{ymd[4:6]}/{ymd[6:]})")
        print(f"{'='*60}")
        print(f"対象レース数: {len(race_data.get('races', []))}R")
        print(f"選定レース数: {len(selected_races)}R")
        print(f"総投資額: ¥{total_investment:,}")
        print(f"{'='*60}\n")
        
        print("【選定レース詳細】")
        for i, race in enumerate(selected_races, 1):
            num_horses = len(race['betting_plan']['軸']) + len(race['betting_plan']['相手'])
            print(f"レース{i}: {race['venue']} (軸{len(race['betting_plan']['軸'])}頭+相手{len(race['betting_plan']['相手'])}頭={num_horses}頭) {race['betting_plan']['組み合わせ数']}点 ¥{race['investment']:,}")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
