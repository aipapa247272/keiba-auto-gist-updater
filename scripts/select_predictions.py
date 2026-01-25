#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
select_predictions.py - Phase 2-3: 本命・対抗選定 + 買い目提案

統合ルール（/競馬予想AI/1_AI予想ルール/統合ルール.md）に準拠：
- 主：三連複フォーメーション（軸◎○▲、相手△6〜7頭）
- オプション：軸3頭BOX（スコア差5点以内）
- 波乱度判定（スコア拮抗度）
- 投資OFF運用（買い目は構造として提示、実購入はしない）
- データ不足レースは自動除外
"""

import json
import sys
from typing import List, Dict, Any

def load_race_data(ymd: str) -> Dict[str, Any]:
    """race_data_{ymd}.json を読み込み"""
    input_file = f"race_data_{ymd}.json"
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[INFO] {input_file} を読み込みました（{len(data['races'])} レース）")
        return data
    except FileNotFoundError:
        print(f"[ERROR] {input_file} が見つかりません")
        sys.exit(1)

def calculate_turbulence(scores: List[Dict]) -> tuple[str, str]:
    """
    波乱度を判定（統合ルール §9）
    - オッズを使わず、スコアの拮抗度で判定
    - 低：1位が圧倒的（1位と2位の差が10点以上）
    - 中：上位が拮抗（1位と2位の差が5〜10点）
    - 高：団子状態（1位と3位の差が5点以内）
    
    Returns:
        tuple[str, str]: (波乱度, 理由)
    """
    if len(scores) < 3:
        return "低", "出走頭数不足"
    
    top1 = scores[0]["total_score"]
    top2 = scores[1]["total_score"]
    top3 = scores[2]["total_score"]
    
    diff_1_2 = top1 - top2
    diff_1_3 = top1 - top3
    
    if diff_1_3 <= 5:
        reason = f"1位と3位の差が{diff_1_3:.1f}点（5点以内）で団子状態"
        return "高", reason
    elif diff_1_2 >= 10:
        reason = f"1位が{diff_1_2:.1f}点差で圧倒的"
        return "低", reason
    else:
        reason = f"1位と2位の差が{diff_1_2:.1f}点（5〜10点）で拮抗"
        return "中", reason

def select_hole_candidates(scores: List[Dict], top3_ids: List[str]) -> List[Dict]:
    """
    穴候補（△）を選定
    - 4〜10位でスコア45点以上の馬
    - 最大7頭まで選定
    """
    candidates = []
    for horse in scores:
        if horse["horse_id"] in top3_ids:
            continue  # 軸（◎○▲）は除外
        if horse["total_score"] >= 45:
            candidates.append(horse)
        if len(candidates) >= 7:
            break
    return candidates

def generate_sanrenpuku_formation(
    honmei: Dict,
    taikou: Dict,
    ana: Dict,
    hole_candidates: List[Dict]
) -> Dict[str, Any]:
    """
    三連複フォーメーションの買い目を生成
    - 軸：◎○▲（3頭）
    - 相手：△候補（6〜7頭）
    """
    axis = [honmei["馬番"], taikou["馬番"], ana["馬番"]]
    aite = [h["馬番"] for h in hole_candidates]
    
    # 点数計算（軸3頭ボックス + 軸3頭×相手）
    axis_box = 1  # ◎-○-▲
    axis_aite = len(aite) * 3 if aite else 0  # 軸各1頭×相手
    total_points = axis_box + axis_aite
    
    # 投資額（1点100円）
    unit_price = 100
    total_investment = total_points * unit_price
    
    return {
        "type": "三連複フォーメーション",
        "axis": axis,
        "aite": aite,
        "points": total_points,
        "unit_price": unit_price,
        "total_investment": total_investment,
        "combinations": f"◎-○-▲ BOX + (◎○▲ × △{len(aite)}頭)" if aite else "◎-○-▲ BOX のみ"
    }

def check_axis_box_option(honmei: Dict, taikou: Dict, ana: Dict) -> Dict[str, Any]:
    """
    軸3頭BOXオプションの採用可否を判定
    - 条件：◎○▲のスコア差が5点以内
    """
    scores = [
        honmei["total_score"],
        taikou["total_score"],
        ana["total_score"]
    ]
    max_score = max(scores)
    min_score = min(scores)
    score_diff = max_score - min_score
    
    if score_diff <= 5:
        return {
            "enabled": True,
            "reason": f"スコア差 {score_diff:.1f}点（5点以内）",
            "note": "軸3頭BOXは三連複フォーメーションに含まれています"
        }
    else:
        return {
            "enabled": False,
            "reason": f"スコア差 {score_diff:.1f}点（5点超）",
            "note": "スコア差が大きいため、軸3頭は同格扱いしません"
        }

def assign_prediction_marks(race_id: str, race_info: Dict, scores: List[Dict]) -> Dict[str, Any]:
    """
    予想印を付与し、買い目を生成
    """
    if not scores:
        return {
            "race_id": race_id,
            "race_info": race_info,
            "turbulence": "不明",
            "turbulence_reason": "データなし",
            "status": "スコアなし",
            "predictions": {},
            "betting_suggestions": {}
        }
    
    # 上位3頭を選定
    top3 = scores[:3]
    honmei = top3[0] if len(top3) > 0 else None
    taikou = top3[1] if len(top3) > 1 else None
    ana = top3[2] if len(top3) > 2 else None
    
    if not all([honmei, taikou, ana]):
        return {
            "race_id": race_id,
            "race_info": race_info,
            "turbulence": "不明",
            "turbulence_reason": "データ不足",
            "status": "データ不足（3頭未満）",
            "predictions": {},
            "betting_suggestions": {}
        }
    
    # 予想印を付与
    honmei["mark"] = "◎"
    taikou["mark"] = "○"
    ana["mark"] = "▲"
    
    # 信頼度を設定
    honmei["confidence"] = "高" if honmei["total_score"] >= 70 else "中"
    taikou["confidence"] = "中" if taikou["total_score"] >= 60 else "低"
    ana["confidence"] = "低" if ana["total_score"] >= 50 else "極低"
    
    # 波乱度判定
    turbulence, turbulence_reason = calculate_turbulence(scores)
    
    # 穴候補（△）選定
    top3_ids = [honmei["horse_id"], taikou["horse_id"], ana["horse_id"]]
    hole_candidates = select_hole_candidates(scores, top3_ids)
    
    # 穴候補に印を付与
    for horse in hole_candidates:
        horse["mark"] = "△"
        horse["confidence"] = "穴"
    
    # 買い目生成（三連複フォーメーション）
    betting = generate_sanrenpuku_formation(honmei, taikou, ana, hole_candidates)
    
    # 軸3頭BOXオプション
    axis_box = check_axis_box_option(honmei, taikou, ana)
    
    # 合計投資額（三連複フォーメーションに軸3頭BOXは含まれている）
    total_investment = betting["total_investment"]
    
    return {
        "race_id": race_id,
        "race_info": race_info,
        "turbulence": turbulence,
        "turbulence_reason": turbulence_reason,
        "status": "予想完了",
        "predictions": {
            "honmei": honmei,
            "taikou": taikou,
            "ana": ana,
            "hole_candidates": hole_candidates
        },
        "betting_suggestions": {
            "main": betting,
            "axis_box_note": axis_box,
            "total_investment": total_investment
        }
    }

def print_race_summary(pred: Dict):
    """レースサマリーを表示"""
    race_info = pred["race_info"]
    turbulence = pred["turbulence"]
    
    print("\n" + "="*80)
    print(f"【レース {pred['race_id']}】")
    print(f"  レース名: {race_info.get('レース名', 'N/A')}")
    print(f"  距離: {race_info.get('距離', 'N/A')}")
    print(f"  発走時刻: {race_info.get('発走時刻', 'N/A')}")
    print(f"  競馬場: {race_info.get('venue', 'N/A')}")
    print(f"  波乱度: {turbulence} ({pred.get('turbulence_reason', '')})")
    
    if pred["status"] != "予想完了":
        print(f"  状態: {pred['status']}")
        print("="*80)
        return
    
    preds = pred["predictions"]
    
    print("\n【予想印】")
    for mark_key, label in [("honmei", "◎ 本命"), ("taikou", "○ 対抗"), ("ana", "▲ 穴")]:
        horse = preds[mark_key]
        print(f"  {label}: {horse['馬番']}番 {horse['馬名']} "
              f"({horse['total_score']:.1f}点 - D:{horse['distance_score']:.1f} "
              f"E:{horse['experience_score']:.1f} S:{horse['speed_score']:.1f}) "
              f"[信頼度: {horse['confidence']}]")
    
    if preds["hole_candidates"]:
        print(f"\n【穴候補 △】（{len(preds['hole_candidates'])}頭）")
        for horse in preds["hole_candidates"]:
            print(f"  △ {horse['馬番']}番 {horse['馬名']} ({horse['total_score']:.1f}点)")
    else:
        print(f"\n【穴候補 △】: なし（スコア45点以上の馬がいません）")
    
    betting = pred["betting_suggestions"]
    main = betting["main"]
    axis_box_note = betting["axis_box_note"]
    
    print("\n【買い目提案】")
    print(f"  ■ {main['type']}")
    print(f"    軸: {main['axis']} (◎○▲)")
    if main['aite']:
        print(f"    相手: {main['aite']} (△)")
    else:
        print(f"    相手: なし")
    print(f"    組み合わせ: {main['combinations']}")
    print(f"    点数: {main['points']}点")
    print(f"    投資額: {main['total_investment']:,}円 ({main['unit_price']}円×{main['points']}点)")
    
    print(f"\n  □ 軸3頭の評価")
    if axis_box_note["enabled"]:
        print(f"    判定: ✅ 同格 ({axis_box_note['reason']})")
    else:
        print(f"    判定: ❌ 力差あり ({axis_box_note['reason']})")
    print(f"    備考: {axis_box_note['note']}")
    
    print(f"\n  【合計投資額】: {betting['total_investment']:,}円")
    
    # 波乱度「高」の場合は警告
    if turbulence == "高":
        print("\n  ⚠️  波乱度「高」のため、投資ON時は見送り推奨（統合ルール §9）")
    
    print("="*80)

def main():
    if len(sys.argv) < 2:
        print("Usage: python select_predictions.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    # データ読み込み
    data = load_race_data(ymd)
    
    # 各レースの予想を生成
    predictions = []
    skipped_count = 0
    
    for race in data["races"]:
        race_id = race["race_id"]
        race_info = race["race_info"]
        
        # des_scoresが存在するか確認
        if "des_scores" not in race or not race["des_scores"]:
            print(f"[SKIP] レース {race_id}: データ不足（des_scoresなし）")
            skipped_count += 1
            continue
        
        scores = race["des_scores"]
        
        # スコアでソート（降順）
        scores_sorted = sorted(scores, key=lambda x: x["total_score"], reverse=True)
        
        # 予想生成
        pred = assign_prediction_marks(race_id, race_info, scores_sorted)
        predictions.append(pred)
        
        # サマリー表示
        print_race_summary(pred)
    
    # predictions を元のデータに追加
    data["predictions"] = predictions
    
    # 出力ファイル名
    output_file = f"race_data_{ymd}.json"
    
    # 保存
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] {output_file} に予想データを追加しました")
    
    # 統計表示
    total = len(predictions)
    low = sum(1 for p in predictions if p.get("turbulence") == "低")
    mid = sum(1 for p in predictions if p.get("turbulence") == "中")
    high = sum(1 for p in predictions if p.get("turbulence") == "高")
    
    print(f"\n【予想統計】")
    print(f"  総レース数: {len(data['races'])}")
    print(f"  予想対象: {total}レース")
    print(f"  スキップ: {skipped_count}レース（データ不足）")
    print(f"  波乱度 低: {low}レース")
    print(f"  波乱度 中: {mid}レース")
    print(f"  波乱度 高: {high}レース（投資ON時は見送り推奨）")

if __name__ == "__main__":
    main()
