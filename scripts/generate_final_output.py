#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_final_output.py - Phase 2-4: 買い目提示の最終調整 (修正版 v10)

修正内容:
- "predictions" → "selected_races" へキー名変更
- アプリで使いやすいシンプルな出力形式
- 不要な複雑なロジックを削除
- 総投資額の計算を修正（各レースの投資額を合計）← v10の修正

機能:
- 選定された3〜5レースの予想を出力
- 競馬場とレース番号を明確に表示
- 各項目を見やすく表示
- Markdown と JSON 両方を出力
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

def get_number_emoji(num: int) -> str:
    """馬番を絵文字に変換"""
    emoji_map = {
        1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
        6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
        11: "1️⃣1️⃣", 12: "1️⃣2️⃣", 13: "1️⃣3️⃣", 14: "1️⃣4️⃣", 15: "1️⃣5️⃣",
        16: "1️⃣6️⃣", 17: "1️⃣7️⃣", 18: "1️⃣8️⃣"
    }
    return emoji_map.get(num, f"{num}")

def format_race_report(race: Dict, index: int) -> str:
    """レースレポートをMarkdown形式で生成"""
    
    # レース基本情報
    venue = race.get('競馬場', '不明')
    race_num = race.get('レース番号', '?')
    race_name = race.get('レース名', 'N/A')
    distance = race.get('距離', 'N/A')
    post_time = race.get('発走時刻', 'N/A')
    turbulence = race.get('波乱度', '中')
    investment = race.get('投資額', 0)  # ← 投資額を取得
    
    # ヘッダー
    report = f"\n🏇 予想 {index}\n\n"
    report += f"📍 {venue} R{race_num} {race_name}\n"
    report += f"📏 {distance}m | ⏰ {post_time}\n"
    
    # 波乱度
    turb_emoji = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(turbulence, "⚪")
    turb_text = {"低": "(本命有利)", "中": "(拮抗)", "高": "(荒れる)"}.get(turbulence, "")
    report += f"🌊 波乱度: {turb_emoji} {turbulence} {turb_text}\n\n"
    
    # 上位3頭の予想
    horses = race.get('horses', [])
    if len(horses) < 3:
        report += "⚠️ データ不足\n\n"
        return report
    
    mark_symbols = ["◎", "○", "▲"]
    mark_names = ["本命", "対抗", "単穴"]
    
    for i, (mark_symbol, mark_name) in enumerate(zip(mark_symbols, mark_names)):
        if i >= len(horses):
            break
        
        horse = horses[i]
        horse_num = horse.get('馬番', 0)
        horse_name = horse.get('馬名', 'N/A')
        des_score = horse.get('des_score', {})
        total_score = des_score.get('total', 0)
        confidence = des_score.get('信頼度', 'N/A')
        
        # DESスコアの内訳
        a_score = des_score.get('A_過去実績', 0)
        b_score = des_score.get('B_距離馬場適性', 0)
        c_score = des_score.get('C_騎手厩舎', 0)
        d_score = des_score.get('D_展開適性', 0)
        
        percentage = int(total_score)
        
        # 馬名を太字で強調
        report += f"**{mark_symbol} {mark_name} {get_number_emoji(horse_num)} {horse_name}**  \n"
        report += f"　📊 総合点: {total_score:.1f} / 100 ({percentage}%)  \n"
        report += f"　📈 過去実績: {a_score:.1f} / 40  \n"
        report += f"　📏 距離適性: {b_score:.1f} / 30  \n"
        report += f"　👤 騎手厩舎: {c_score:.1f} / 20  \n"
        report += f"　⚡ 展開適性: {d_score:.1f} / 20  \n"
        
        conf_emoji = {"高": "🟢", "中": "🟡", "低": "🔴", "極低": "🔴"}.get(confidence, "⚪")
        report += f"　🎯 信頼度: {conf_emoji} {confidence}\n\n"
    
    report += "---\n\n"
    
    # 買い目提案
    report += f"🎯 買い目提案\n\n"
    report += f"**3連複 (軸3頭BOX)**\n\n"
    
    # 軸馬
    report += "【軸馬】\n"
    axis_parts = []
    for i in range(min(3, len(horses))):
        mark = mark_symbols[i]
        num = horses[i].get('馬番', 0)
        axis_parts.append(f"{mark} {get_number_emoji(num)}")
    report += "  ".join(axis_parts) + "\n\n"
    
    # 投資プラン（投資額を表示）
    report += "【投資プラン】\n"
    report += f"💰 投資額: {investment:,}円\n\n"
    
    # 組み合わせ
    if len(horses) >= 3:
        h1 = horses[0].get('馬番', 0)
        h2 = horses[1].get('馬番', 0)
        h3 = horses[2].get('馬番', 0)
        report += "【組み合わせ】\n"
        report += f"{h1}-{h2}-{h3}\n\n"
    
    # 波乱度「高」の警告
    if turbulence == "高":
        report += "⚠️⚠️ **見送り推奨** ⚠️⚠️\n"
        report += "投資ON時は見送り推奨\n\n"
    
    report += "---\n"
    
    return report

def generate_summary(selected_races: List[Dict], total_races: int) -> str:
    """最終サマリーを生成"""
    summary = "# 📊 本日の予想サマリー\n\n"
    summary += f"**日付**: {datetime.now().strftime('%Y年%m月%d日')}\n\n"
    
    summary += f"- **総レース数**: {total_races}レース\n"
    summary += f"- **予想対象**: {len(selected_races)}レース\n"
    summary += f"- **見送り**: {total_races - len(selected_races)}レース\n\n"
    
    # 波乱度別集計
    low = sum(1 for r in selected_races if r.get("波乱度") == "低")
    mid = sum(1 for r in selected_races if r.get("波乱度") == "中")
    high = sum(1 for r in selected_races if r.get("波乱度") == "高")
    
    summary += "【波乱度別内訳】\n"
    summary += f"- 🟢 低: {low}レース (本命有利)\n"
    summary += f"- 🟡 中: {mid}レース (拮抗)\n"
    summary += f"- 🔴 高: {high}レース (荒れる可能性)\n\n"
    
    # 合計投資額（各レースの投資額を合計）
    total_investment = sum(race.get("投資額", 0) for race in selected_races)
    summary += "【合計投資額】\n"
    summary += f"💰 **{total_investment:,}円** (投資OFFのため実購入なし)\n\n"
    summary += "---\n"
    return summary

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_final_output.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    # データ読み込み
    data = load_race_data(ymd)
    
    # ★ 修正: "predictions" → "selected_races" へ変更
    if "selected_races" not in data:
        print("[ERROR] selected_races が見つかりません。先に select_predictions.py を実行してください。")
        sys.exit(1)
    
    selected_races = data["selected_races"]
    total_races = len(data.get("races", []))
    
    print(f"[INFO] 予想データ: {len(selected_races)}レース")
    
    # Markdownレポート生成
    report = generate_summary(selected_races, total_races)
    
    for i, race in enumerate(selected_races, 1):
        report += format_race_report(race, i)
    
    # Markdownファイル出力
    md_file = f"predictions_{ymd}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"[SUCCESS] {md_file} を生成しました")
    
    # ★ 修正: 総投資額の計算（各レースの投資額を合計）
    total_investment = sum(race.get("投資額", 0) for race in selected_races)
    
    # 最終JSONファイル出力（アプリ用）
    final_data = {
        "ymd": ymd,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_races": total_races,
            "selected_races": len(selected_races),
            "skipped_races": total_races - len(selected_races),
            "turbulence": {
                "低": sum(1 for r in selected_races if r.get("波乱度") == "低"),
                "中": sum(1 for r in selected_races if r.get("波乱度") == "中"),
                "高": sum(1 for r in selected_races if r.get("波乱度") == "高")
            },
            "total_investment": total_investment  # ← 修正！
        },
        "selected_predictions": selected_races,
        "総投資額": total_investment  # ← 追加！フロントエンド用
    }
    
    json_file = f"final_predictions_{ymd}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"[SUCCESS] {json_file} を生成しました")
    
    # コンソール出力
    print(report)

if __name__ == "__main__":
    main()
