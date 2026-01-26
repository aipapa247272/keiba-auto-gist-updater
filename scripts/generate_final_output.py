#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_final_output.py - Phase 2-4: 買い目提示の最終調整 (スマホ最適化版)

機能:
- レース選定（1日3〜5レース）
- スマホ向け見やすい最終出力（Markdown + JSON）
- 統合ルールに基づく運用
"""

import json
import sys
from typing import List, Dict, Any
from datetime import datetime

def load_race_data(ymd: str) -> Dict[str, Any]:
    """race_data_{ymd}.json を読み込み"""
    input_file = f"race_data_{ymd}.json"
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[INFO] {input_file} を読み込みました")
        return data
    except FileNotFoundError:
        print(f"[ERROR] {input_file} が見つかりません")
        sys.exit(1)

def calculate_race_priority(pred: Dict) -> tuple[int, float]:
    """
    レースの優先順位を計算
    
    Returns:
        tuple[int, float]: (優先度順位, スコア)
        - 優先度順位: 1=高, 2=中, 3=低
        - スコア: 本命の総合スコア
    """
    if pred["status"] != "予想完了":
        return (9, 0.0)  # データ不足は最低優先度
    
    turbulence = pred.get("turbulence", "不明")
    honmei_score = pred["predictions"]["honmei"]["total_score"]
    
    # 波乱度による優先順位
    if turbulence == "低":
        priority = 1  # 高優先度
    elif turbulence == "中":
        priority = 2  # 中優先度
    elif turbulence == "高":
        priority = 3  # 低優先度（見送り推奨）
    else:
        priority = 9  # 不明
    
    return (priority, honmei_score)

def select_races(predictions: List[Dict], min_races: int = 3, max_races: int = 5) -> List[Dict]:
    """
    レースを選定（1日3〜5レース）
    
    選定基準:
    1. 波乱度「低」を優先
    2. 波乱度「中」を次点
    3. 波乱度「高」は見送り（ただし他に候補がない場合のみ選定）
    4. 本命のスコアが高い順
    """
    # 優先順位でソート
    sorted_predictions = sorted(
        predictions,
        key=lambda p: calculate_race_priority(p)
    )
    
    # 波乱度「低」「中」のレースを優先選定
    selected = []
    for pred in sorted_predictions:
        turbulence = pred.get("turbulence", "不明")
        if turbulence in ["低", "中"] and len(selected) < max_races:
            selected.append(pred)
    
    # 最低3レースに満たない場合、波乱度「高」も含める
    if len(selected) < min_races:
        for pred in sorted_predictions:
            turbulence = pred.get("turbulence", "不明")
            if turbulence == "高" and pred not in selected and len(selected) < max_races:
                selected.append(pred)
                if len(selected) >= min_races:
                    break
    
    return selected

def format_race_report(pred: Dict, index: int) -> str:
    """
    レースレポートをMarkdown形式で生成 (スマホ最適化)
    """
    race_info = pred["race_info"]
    turbulence = pred["turbulence"]
    preds = pred["predictions"]
    betting = pred["betting_suggestions"]
    
    # ヘッダー
    report = f"\n{'━' * 40}\n"
    report += f"# 【予想 {index}】レース\n"
    report += f"`{pred['race_id']}`\n\n"
    
    # レース基本情報 (スマホ向けシンプル表示)
    venue = race_info.get('venue') or '不明'
    race_name = race_info.get('レース名', 'N/A')
    distance = race_info.get('距離', 'N/A')
    post_time = race_info.get('発走時刻', 'N/A')
    
    report += f"📍 **競馬場**: {venue} 🏁 **レース名**: {race_name}\n"
    report += f"📏 **距離**: {distance}\n"
    report += f"⏰ **発走時刻**: {post_time}\n"
    
    # 波乱度 (絵文字で視覚化)
    turb_emoji = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(turbulence, "⚪")
    report += f"🌊 **波乱度**: {turb_emoji} **{turbulence}** ({pred.get('turbulence_reason', '')})\n\n"
    
    if pred["status"] != "予想完了":
        report += f"⚠️ **状態**: {pred['status']}\n"
        report += f"{'━' * 40}\n\n"
        return report
    
    # 予想印 (カード形式)
    report += "## 【予想印】\n\n"
    
    mark_labels = {
        "honmei": ("◎", "本命"),
        "taikou": ("○", "対抗"),
        "ana": ("▲", "単穴")
    }
    
    for mark_key, (mark_symbol, mark_name) in mark_labels.items():
        if mark_key not in preds:
            continue
        
        horse = preds[mark_key]
        report += f"### {mark_symbol} {mark_name}\n"
        report += f"{'─' * 30}\n"
        report += f"**{horse.get('馬番', 'N/A')}番 {horse.get('馬名', 'N/A')}**\n\n"
        report += f"📊 総合点: **{horse.get('total_score', 0):.1f}**\n"
        report += f"├ 📏 距離適性(D): {horse.get('distance_score', 0):.1f}\n"
        report += f"├ 📈 経験値(E): {horse.get('experience_score', 0):.1f}\n"
        report += f"├ ⚡ スピード(S): {horse.get('speed_score', 0):.1f}\n"
        report += f"└ 🎯 信頼度: {horse.get('confidence', 'N/A')}\n\n"
    
    # 穴候補 (コンパクト表示)
    if preds.get("hole_candidates"):
        report += "## 【穴候補】\n\n"
        for hole in preds["hole_candidates"]:
            report += f"△ **{hole.get('馬番')}番 {hole.get('馬名')}** "
            report += f"({hole.get('total_score', 0):.1f}点)\n"
        report += "\n"
    
    # 買い目提案 (スマホ向け)
    main = betting["main"]
    report += "## 【買い目提案】\n\n"
    report += f"🎯 **{main['type']}**\n\n"
    
    # 軸馬
    axis = main.get('axis', [])
    if axis:
        report += "### 軸馬\n"
        axis_parts = []
        if len(axis) > 0:
            axis_parts.append(f"◎{axis[0]}番")
        if len(axis) > 1:
            axis_parts.append(f"○{axis[1]}番")
        if len(axis) > 2:
            axis_parts.append(f"▲{axis[2]}番")
        report += " ".join(axis_parts) + "\n\n"
    
    # 相手
    aite = main.get('aite', [])
    if aite:
        report += "### 相手\n"
        aite_str = " ".join([f"△{h}番" for h in aite])
        report += f"{aite_str}\n\n"
    else:
        report += "### 相手\n"
        report += "なし (軸3頭BOXのみ)\n\n"
    
    # 投資プラン
    points = main.get('points', 0)
    unit = main.get('unit_price', 100)
    total = main.get('total_investment', points * unit)
    
    report += "### 投資プラン\n"
    report += f"💰 **{points}点** × **{unit:,}円** = **{total:,}円**\n\n"
    
    # 組み合わせ
    combinations = main.get('combinations', 'N/A')
    report += "### 組み合わせ\n"
    report += f"{combinations}\n\n"
    
    # 軸3頭の評価
    axis_box = betting.get("axis_box_note", {})
    if axis_box:
        report += "---\n\n"
        report += "### 軸3頭の評価\n"
        if axis_box.get("enabled"):
            report += f"✅ **同格** ({axis_box.get('reason', 'N/A')})\n"
            report += "→ 3連複BOXで手堅く\n\n"
        else:
            report += f"❌ **力差あり** ({axis_box.get('reason', 'N/A')})\n"
            report += "→ 5点以上の差: 荒れる可能性\n\n"
    
    # 波乱度「高」の警告
    if turbulence == "高":
        report += "---\n\n"
        report += "⚠️ **注意**: 波乱度「高」のため、投資ON時は見送り推奨\n"
        report += "(統合ルール §9)\n\n"
    
    report += f"{'━' * 40}\n\n"
    return report

def generate_summary(selected_races: List[Dict], total_races: int, skipped_races: int) -> str:
    """
    最終サマリーを生成 (スマホ最適化)
    """
    summary = "\n" + "="*40 + "\n"
    summary += "# 📊 本日の予想サマリー\n\n"
    summary += f"**日付**: {datetime.now().strftime('%Y年%m月%d日')}\n\n"
    
    summary += f"**総レース数**: {total_races}レース\n"
    summary += f"**データ不足**: {skipped_races}レース\n"
    summary += f"**予想対象**: {len(selected_races)}レース\n\n"
    
    # 波乱度別集計
    low = sum(1 for r in selected_races if r.get("turbulence") == "低")
    mid = sum(1 for r in selected_races if r.get("turbulence") == "中")
    high = sum(1 for r in selected_races if r.get("turbulence") == "高")
    
    summary += "## 【波乱度別内訳】\n\n"
    summary += f"🟢 **低**: {low}レース (本命有利)\n"
    summary += f"🟡 **中**: {mid}レース (拮抗)\n"
    summary += f"🔴 **高**: {high}レース (荒れる可能性)\n\n"
    
    # 合計投資額
    total_investment = sum(r["betting_suggestions"]["total_investment"] for r in selected_races)
    summary += "## 【合計投資額】\n\n"
    summary += f"**{total_investment:,}円**\n"
    summary += "(投資OFFのため実購入なし)\n\n"
    summary += "="*40 + "\n\n"
    return summary

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_final_output.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    # データ読み込み
    data = load_race_data(ymd)
    
    if "predictions" not in data:
        print("[ERROR] predictions が見つかりません。先に select_predictions.py を実行してください。")
        sys.exit(1)
    
    predictions = data["predictions"]
    total_races = len(data["races"])
    skipped_races = total_races - len(predictions)
    
    print(f"[INFO] 予想データ: {len(predictions)}レース")
    
    # レース選定
    selected_races = select_races(predictions, min_races=3, max_races=5)
    
    print(f"[INFO] 選定レース: {len(selected_races)}レース")
    
    # Markdownレポート生成
    report = generate_summary(selected_races, total_races, skipped_races)
    
    for i, race in enumerate(selected_races, 1):
        report += format_race_report(race, i)
    
    # Markdownファイル出力
    md_file = f"predictions_{ymd}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"[SUCCESS] {md_file} を生成しました")
    
    # 最終JSONファイル出力
    final_data = {
        "ymd": ymd,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_races": total_races,
            "skipped_races": skipped_races,
            "selected_races": len(selected_races),
            "turbulence": {
                "低": sum(1 for r in selected_races if r.get("turbulence") == "低"),
                "中": sum(1 for r in selected_races if r.get("turbulence") == "中"),
                "高": sum(1 for r in selected_races if r.get("turbulence") == "高")
            },
            "total_investment": sum(r["betting_suggestions"]["total_investment"] for r in selected_races)
        },
        "selected_predictions": selected_races
    }
    
    json_file = f"final_predictions_{ymd}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"[SUCCESS] {json_file} を生成しました")
    
    # コンソール出力
    print(report)

if __name__ == "__main__":
    main()
