#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新予想ロジック対応: レース選定スクリプト
修正日: 2026/02/16
変更点: 旧DESスコア → 新スコアに変更
"""

import json
import sys
import os
from datetime import datetime

def calculate_turbulence(race):
    """
    波乱度を計算
    新スコアベースで判定
    """
    horses = race.get('horses', [])
    
    if not horses:
        return "中"
    
    # 新スコアを取得
    scores = [h.get('新スコア', 0) for h in horses if h.get('新スコア')]
    
    if not scores or len(scores) < 3:
        return "中"
    
    scores.sort(reverse=True)
    
    # 上位3頭の平均スコア
    top_3_avg = sum(scores[:3]) / 3
    
    # スコア差（1位と3位の差）
    score_diff = scores[0] - scores[2] if len(scores) >= 3 else 0
    
    # 波乱度判定（新スコアは0-100点）
    if top_3_avg >= 70 and score_diff >= 10:
        return "低"  # 本命有利
    elif top_3_avg >= 55 or score_diff >= 5:
        return "中"  # 混戦
    else:
        return "高"  # 大波乱

def generate_betting_plan(race):
    """
    三連複フォーメーションの買い目を生成（新スコア対応）
    
    Args:
        race (dict): レースデータ
    
    Returns:
        dict: 買い目データ
    """
    horses = race.get('horses', [])
    
    # 新スコアでソート
    sorted_horses = sorted(
        horses, 
        key=lambda h: h.get('新スコア', 0), 
        reverse=True
    )
    
    # 上位10頭を選出
    top_10 = sorted_horses[:min(10, len(sorted_horses))]
    
    # 軸: 上位3頭（◎○▲）
    axis_horses = top_10[:3]
    
    # 穴候補: 動的計算（出馬数 ÷ 2 + 1）頭（4位以降から）
    num_horses = len(horses)
    num_opponents = min(num_horses // 2 + 1, len(top_10) - 3)
    opponent_horses = top_10[3:3+num_opponents]
    
    # 買い目: 軸3頭BOX
    betting_plan = {
        "軸": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": ["◎", "○", "▲"][i],
                "スコア": h.get('新スコア', 0),
                "内訳": h.get('新スコア_内訳', {})
            }
            for i, h in enumerate(axis_horses)
        ],
        "相手": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": "△",
                "スコア": h.get('新スコア', 0)
            }
            for h in opponent_horses
        ],
        "買い目タイプ": "三連複フォーメーション（軸3頭BOX）",
        "組み合わせ数": 1  # 3頭BOX = 1通り
    }
    
    return betting_plan

def select_races(race_data, max_races=5):
    """
    予想対象レースを選定
    
    Args:
        race_data (dict): 全レースデータ
        max_races (int): 最大選定レース数
    
    Returns:
        list: 選定されたレースリスト
    """
    races = race_data.get('races', [])
    selected = []
    skipped = []
    
    turbulence_counts = {"低": 0, "中": 0, "高": 0}
    
    for race in races:
        horses = race.get('horses', [])
        
        # 出馬数チェック
        if len(horses) < 8:
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": f"出馬数不足({len(horses)}頭)"
            })
            continue
        
        # 新スコアが計算されているかチェック
        horses_with_score = [h for h in horses if h.get('新スコア')]
        if len(horses_with_score) < len(horses) * 0.8:
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": "新スコアデータ不足"
            })
            continue
        
        # 新スコアの平均を計算
        scores = [h.get('新スコア', 0) for h in horses_with_score]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 評価スコア: 新スコア上位3頭の平均
        top_3_scores = sorted(scores, reverse=True)[:3]
        evaluation_score = sum(top_3_scores) / 3 if len(top_3_scores) >= 3 else avg_score
        
        # データ品質: 新スコアが計算された馬の割合
        data_quality = int((len(horses_with_score) / len(horses)) * 20)
        
        # 波乱度計算
        turbulence = calculate_turbulence(race)
        
        # 買い目生成
        betting_plan = generate_betting_plan(race)
        
        # 選定条件
        # 1. 新スコア上位3頭の平均が50点以上
        # 2. データ品質が10以上
        if evaluation_score >= 50 and data_quality >= 10:
            selected.append({
                "race_id": race.get('race_id'),
                "race_name": race.get('レース名', '不明'),
                "venue": race.get('競馬場', '不明'),
                "distance": race.get('距離'),
                "track": race.get('トラック'),
                "start_time": race.get('発走時刻'),
                "turbulence": turbulence,
                "evaluation_score": round(evaluation_score, 2),
                "top_3_avg": round(sum(top_3_scores) / 3, 2) if len(top_3_scores) >= 3 else 0,
                "data_quality": data_quality,
                "betting_plan": betting_plan,
                "investment": 2400  # 1レースあたりの投資額
            })
            turbulence_counts[turbulence] += 1
        else:
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": f"評価不足(score:{evaluation_score:.1f}, quality:{data_quality})"
            })
    
    # 波乱度のバランスを考慮してレース選定
    # 低: 60%, 中: 40%, 高: 0%
    final_selected = []
    low_races = [r for r in selected if r["turbulence"] == "低"]
    mid_races = [r for r in selected if r["turbulence"] == "中"]
    
    # 低波乱度レースから優先的に選択
    final_selected.extend(sorted(low_races, key=lambda r: r["evaluation_score"], reverse=True)[:3])
    
    # 残り枠を中波乱度レースで埋める
    remaining = max_races - len(final_selected)
    if remaining > 0:
        final_selected.extend(sorted(mid_races, key=lambda r: r["evaluation_score"], reverse=True)[:remaining])
    
    # 高波乱度レースは選定しない
    
    return final_selected[:max_races], skipped, turbulence_counts

def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python select_predictions.py <ymd>")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    output_file = f"final_predictions_{ymd}.json"
    
    try:
        # データ読み込み
        with open(input_file, "r", encoding="utf-8") as f:
            race_data = json.load(f)
        
        print(f"[INFO] {input_file} を読み込みました")
        
        # レース選定
        selected_races, skipped_races, turbulence_counts = select_races(race_data)
        
        # 投資額計算
        total_investment = sum(r["investment"] for r in selected_races)
        
        # 出力データ作成
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
        
        # ファイル保存
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        # latest_predictions.jsonも生成
        with open("latest_predictions.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SUCCESS] final_predictions_{ymd}.json を生成しました")
        print(f"[SUCCESS] latest_predictions.json も生成しました")
        
        # サマリー表示
        print(f"\n{'='*60}")
        print(f"📊 本日の予想サマリー ({ymd[:4]}/{ymd[4:6]}/{ymd[6:]})")
        print(f"{'='*60}")
        print(f"対象レース数: {len(race_data.get('races', []))}R")
        print(f"選定レース数: {len(selected_races)}R")
        print(f"見送りレース: {len(skipped_races)}R")
        print(f"\n波乱度別:")
        print(f"  低: {turbulence_counts['低']}R")
        print(f"  中: {turbulence_counts['中']}R")
        print(f"  高: {turbulence_counts['高']}R")
        print(f"\n総投資額: ¥{total_investment:,}")
        print(f"{'='*60}\n")
        
    except FileNotFoundError:
        print(f"[ERROR] ファイルが見つかりません: {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
