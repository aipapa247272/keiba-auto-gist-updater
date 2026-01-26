#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_final_output.py - Phase 2-4: 買い目提示の最終調整 (超見やすいスマホ最適化版)

機能:
- レース選定（1日3〜5レース）
- 超見やすい最終出力（Markdown + JSON）
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
    """レースの優先順位を計算"""
    if pred["status"] != "予想完了":
        return (9, 0.0)
    
    turbulence = pred.get("turbulence", "不明")
    honmei_score = pred["predictions"]["honmei"]["total_score"]
    
    if turbulence == "低":
        priority = 1
    elif turbulence == "中":
        priority = 2
    elif turbulence == "高":
        priority = 3
    else:
        priority = 9
    
    return (priority, honmei_score)

def select_races(predictions: List[Dict], min_races: int = 3, max_races: int = 5) -> List[Dict]:
    """レースを選定（1日3〜5レース）"""
    sorted_predictions = sorted(
        predictions,
        key=lambda p: calculate_race_priority(p)
    )
    
    selected = []
    for pred in sorted_predictions:
        turbulence = pred.get("turbulence", "不明")
        if turbulence in ["低", "中"] and len(selected) < max_races:
            selected.append(pred)
    
    if len(selected) < min_races:
        for pred in sorted_predictions:
            turbulence = pred.get("turbulence", "不明")
            if turbulence == "高" and pred not in selected and len(selected) < max_races:
                selected.append(pred)
                if len(selected) >= min_races:
                    break
    
    return selected

def score_to_bar(score: float, max_score: float = 30.0) -> str:
    """スコアをプログレスバー風に変換"""
    ratio = min(score / max_score, 1.0)
    filled = int(ratio * 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty

def get_number_emoji(num: int) -> str:
    """馬番を絵文字に変換"""
    emoji_map = {
        1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
        6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
        11: "1️⃣1️⃣", 12: "1️⃣2️⃣", 13: "1️⃣3️⃣", 14: "1️⃣4️⃣", 15: "1️⃣5️⃣",
        16: "1️⃣6️⃣", 17: "1️⃣7️⃣", 18: "1️⃣8️⃣"
    }
    return emoji_map.get(num, f"{num}番")

def format_race_report(pred: Dict, index: int) -> str:
    """レースレポートをMarkdown形式で生成 (超見やすいスマホ最適化)"""
    race_info = pred["race_info"]
    turbulence = pred["turbulence"]
    preds = pred["predictions"]
    betting = pred["betting_suggestions"]
    
    # ヘッダー (ボックス化)
    venue = race_info.get('venue') or '不明'
    race_name = race_info.get('レース名', 'N/A')
    
    report = f"\n╔{'═' * 35}╗\n"
    report += f"║   🏇 予想 {index}   {venue} {race_name}{'  ' * (25 - len(venue) - len(race_name))}║\n"
    report += f"╚{'═' * 35}╝\n\n"
    
    # レース基本情報 (1行にまとめる)
    distance = race_info.get('距離', 'N/A')
    post_time = race_info.get('発走時刻', 'N/A')
    
    report += f"📍 {venue}  📏 {distance}  ⏰ {post_time}\n"
    
    # 波乱度 (絵文字強調)
    turb_emoji = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(turbulence, "⚪")
    turb_text = {"低": "(本命有利)", "中": "(拮抗)", "高": "(荒れる)"}.get(turbulence, "")
    report += f"🌊 波乱度: {turb_emoji} **{turbulence}** {turb_text}\n\n"
    
    if pred["status"] != "予想完了":
        report += f"⚠️ **状態**: {pred['status']}\n\n"
        return report
    
    report += f"{'━' * 40}\n\n"
    
    # 予想印 (プログレスバー付きカード)
    mark_labels = {
        "honmei": ("◎", "本命"),
        "taikou": ("○", "対抗"),
        "ana": ("▲", "単穴")
    }
    
    for mark_key, (mark_symbol, mark_name) in mark_labels.items():
        if mark_key not in preds:
            continue
        
        horse = preds[mark_key]
        horse_num = horse.get('馬番', 0)
        horse_name = horse.get('馬名', 'N/A')
        total_score = horse.get('total_score', 0)
        
        # ヘッダー
        report += f"**{mark_symbol} {mark_name}**  {get_number_emoji(horse_num)}  **{horse_name}**\n\n"
        
        # 総合点 (ボックス + プログレスバー)
        report += f"┏{'━' * 30}┓\n"
        report += f"┃  📊 総合点: **{total_score:.1f}** / 100  ┃\n"
        report += f"┃  {score_to_bar(total_score, 100)}  ┃\n"
        report += f"┗{'━' * 30}┛\n\n"
        
        # 各スコア (コンパクト表示 + ミニバー)
        d_score = horse.get('distance_score', 0)
        e_score = horse.get('experience_score', 0)
        s_score = horse.get('speed_score', 0)
        confidence = horse.get('confidence', 'N/A')
        
        report += f"📏 距離  {d_score:>5.1f}  {score_to_bar(d_score)}\n"
        report += f"📈 経験  {e_score:>5.1f}  {score_to_bar(e_score)}\n"
        report += f"⚡ 速度  {s_score:>5.1f}  {score_to_bar(s_score)}\n"
        
        # 信頼度を絵文字で
        conf_emoji = {"高": "🟢", "中": "🟡", "低": "🔴", "極低": "🔴"}.get(confidence, "⚪")
        report += f"🎯 信頼度: {conf_emoji} **{confidence}**\n\n"
        
        report += f"{'━' * 40}\n\n"
    
    # 穴候補 (簡潔に)
    if preds.get("hole_candidates"):
        report += "**【穴候補】**\n\n"
        for hole in preds["hole_candidates"]:
            horse_num = hole.get('馬番', 0)
            horse_name = hole.get('馬名', 'N/A')
            hole_score = hole.get('total_score', 0)
            report += f"△ {get_number_emoji(horse_num)} {horse_name} ({hole_score:.1f})\n"
        report += "\n"
        report += f"{'━' * 40}\n\n"
    
    # 買い目提案 (ボックス化)
    main = betting["main"]
    report += "**🎯 買い目提案**\n\n"
    
    report += f"┌{'─' * 32}┐\n"
    report += f"│  {main['type']:<28}  │\n"
    report += f"└{'─' * 32}┘\n\n"
    
    # 軸馬 (絵文字で表示)
    axis = main.get('axis', [])
    if axis:
        report += "**【軸馬】**\n"
        axis_parts = []
        marks = ["◎", "○", "▲"]
        for i, num in enumerate(axis[:3]):
            mark = marks[i] if i < len(marks) else "△"
            axis_parts.append(f"{mark} {get_number_emoji(int(num))}")
        report += "  ".join(axis_parts) + "\n\n"
    
    # 相手
    aite = main.get('aite', [])
    if aite:
        report += "**【相手】**\n"
        aite_parts = [f"△ {get_number_emoji(int(h))}" for h in aite]
        report += "  ".join(aite_parts) + "\n\n"
    else:
        report += "**【相手】**\n"
        report += "なし (軸3頭BOXのみ)\n\n"
    
    # 投資プラン (強調)
    points = main.get('points', 0)
    unit = main.get('unit_price', 100)
    total = main.get('total_investment', points * unit)
    
    report += "**💰 投資プラン**\n"
    report += f"**{points}点** × **{unit:,}円** = **{total:,}円**\n\n"
    
    # 組み合わせ
    combinations = main.get('combinations', 'N/A')
    report += "**📋 組み合わせ**\n"
    report += f"{combinations}\n\n"
    
    # 軸3頭の評価 (警告ボックス)
    axis_box = betting.get("axis_box_note", {})
    if axis_box:
        report += "**⚠️ 軸3頭の評価**\n"
        if axis_box.get("enabled"):
            report += f"✅ **同格** ({axis_box.get('reason', 'N/A')})\n"
            report += "   → 3連複BOXで手堅く\n\n"
        else:
            reason = axis_box.get('reason', 'N/A')
            report += f"❌ **力差大** ({reason})\n"
            report += "   → 荒れる可能性あり\n\n"
    
    # 波乱度「高」の警告
    if turbulence == "高":
        report += "┏━━━━━━━━━━━━━━━━━━┓\n"
        report += "┃ ⚠️  見送り推奨  ⚠️    ┃\n"
        report += "┗━━━━━━━━━━━━━━━━━━┛\n"
        report += "投資ON時は見送り推奨\n"
        report += "(統合ルール §9)\n\n"
    
    report += f"{'━' * 40}\n\n"
    return report

def generate_summary(selected_races: List[Dict], total_races: int, skipped_races: int) -> str:
    """最終サマリーを生成 (スマホ最適化)"""
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
