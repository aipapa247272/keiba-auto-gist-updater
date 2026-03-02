#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_final_output.py - Phase 2-4: 買い目提示の最終調整 (修正版 v12)

修正内容 (v12):
- 断層分析・合成オッズ・役割フィールドを JSON/MD 出力に追加
- 旧ロジック比較データを出力
- 資金管理ルール表示を追加
- 合成オッズ色分け表示 (緑≥4, 黄3-4, 赤<3)

機能:
- 選定されたレースの予想を出力
- 競馬場とレース番号を明確に表示
- 断層・合成オッズ・役割バッジを表示
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


def get_synthetic_odds_label(synthetic_odds: float) -> str:
    """合成オッズの評価ラベルを返す"""
    if synthetic_odds >= 5.0:
        return f"🟢 {synthetic_odds}倍 (高期待値)"
    elif synthetic_odds >= 4.0:
        return f"🟢 {synthetic_odds}倍 (良好)"
    elif synthetic_odds >= 3.0:
        return f"🟡 {synthetic_odds}倍 (基準)"
    else:
        return f"🔴 {synthetic_odds}倍 (低期待値)"


def format_race_report(race: Dict, index: int) -> str:
    """レースレポートをMarkdown形式で生成 (v12: 断層・合成オッズ追加)"""

    # レース基本情報
    venue = race.get('venue', race.get('競馬場', '不明'))
    race_id = race.get('race_id', '')
    race_name = race.get('race_name', race.get('レース名', 'N/A'))
    distance = race.get('distance', race.get('距離', 'N/A'))
    post_time = race.get('start_time', race.get('発走時刻', 'N/A'))
    turbulence = race.get('turbulence', race.get('波乱度', '中'))
    investment = race.get('investment', race.get('投資額', 0))

    # 断層分析
    analysis = race.get('断層分析', {})
    synthetic_odds = race.get('合成オッズ', analysis.get('合成オッズ', 0))
    layer_count = analysis.get('断層数', 0)
    race_type = analysis.get('レースタイプ', 'unknown')

    # 旧ロジック比較
    old_logic = race.get('旧ロジック', {})
    old_inv = old_logic.get('旧_投資額', 0)
    old_combos = old_logic.get('旧_組み合わせ数', 0)

    # ヘッダー
    report = f"\n🏇 予想 {index}\n\n"
    report += f"📍 {venue} {race_name}\n"
    report += f"📏 {distance}m | ⏰ {post_time}\n"

    # 波乱度
    turb_emoji = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(turbulence, "⚪")
    turb_text = {"低": "(本命有利)", "中": "(拮抗)", "高": "(荒れる)"}.get(turbulence, "")
    report += f"🌊 波乱度: {turb_emoji} {turbulence} {turb_text}\n"

    # 断層分析サマリー
    type_label = {
        'double_layer': '2断層(軸・対抗・穴)',
        'single_layer': '1断層(軸・穴)',
        'flat': 'フラット混戦',
        'unknown': '不明'
    }.get(race_type, race_type)
    report += f"📊 断層: {layer_count}箇所 [{type_label}]\n"
    report += f"💹 合成オッズ: {get_synthetic_odds_label(synthetic_odds)}\n\n"

    # 買い目情報
    betting_plan = race.get('betting_plan', {})
    axis_horses = betting_plan.get('軸', [])
    rival_horses = betting_plan.get('対抗', [])
    hole_horses = betting_plan.get('穴', [])
    combo_count = betting_plan.get('組み合わせ数', 0)

    # 軸馬
    report += "**【軸馬（1着候補）】**\n"
    for h in axis_horses:
        num = h.get('馬番', 0)
        name = h.get('馬名', 'N/A')
        score = h.get('スコア', 0)
        role = h.get('断層役割', '')
        danger = "⚠️" if h.get('危険フラグ') else ""
        reasons = h.get('危険理由', [])
        danger_str = f" [{', '.join(reasons)}]" if reasons else ""
        report += (f"　◎ {get_number_emoji(num)} {name} "
                   f"[スコア:{score}] {role}{danger}{danger_str}\n")

    # 対抗馬
    if rival_horses:
        report += "\n**【対抗馬】**\n"
        for h in rival_horses:
            num = h.get('馬番', 0)
            name = h.get('馬名', 'N/A')
            score = h.get('スコア', 0)
            role = h.get('断層役割', '')
            report += f"　▲ {get_number_emoji(num)} {name} [スコア:{score}] {role}\n"

    # 穴馬
    if hole_horses:
        report += "\n**【穴馬（高配当候補）】**\n"
        for h in hole_horses:
            num = h.get('馬番', 0)
            name = h.get('馬名', 'N/A')
            score = h.get('スコア', 0)
            role = h.get('断層役割', '')
            report += f"　△ {get_number_emoji(num)} {name} [スコア:{score}] {role}\n"

    report += "\n---\n\n"

    # 投資プラン
    report += "🎯 **買い目提案**\n\n"
    report += f"📝 {betting_plan.get('買い目タイプ', '三連複フォーメーション')}\n\n"
    report += f"**【新ロジック】** 合成オッズ {synthetic_odds}倍\n"
    report += f"💰 投資額: ¥{investment:,} ({combo_count}点)\n"
    report += f"賭け金メモ: {betting_plan.get('賭け金調整', '')}\n\n"

    report += f"**【旧ロジック比較】**\n"
    if old_combos and old_inv:
        reduction = round((1 - investment / max(old_inv, 1)) * 100, 1)
        report += f"旧: {old_combos}点 ¥{old_inv:,} → 新: {combo_count}点 ¥{investment:,} ({reduction}%削減)\n\n"
    else:
        report += "旧データなし\n\n"

    # 全買い目
    all_combos = betting_plan.get('全買い目', [])
    if all_combos:
        report += "**【全買い目】**\n"
        combos_str = " / ".join(all_combos[:10])
        if len(all_combos) > 10:
            combos_str += f" ...他{len(all_combos)-10}点"
        report += f"{combos_str}\n\n"

    # ワイド候補
    wide_candidates = betting_plan.get('ワイド候補', [])
    if wide_candidates:
        report += "**【ワイド候補】**\n"
        for w in wide_candidates:
            wide_odds = w.get('ワイドオッズ', '要確認')
            odds_str = f"{wide_odds}倍" if wide_odds else "要確認(5倍以上推奨)"
            report += (f"　{w['買い目']} "
                       f"[軸:{w['軸']['馬名']} × 穴:{w['穴']['馬名']}] "
                       f"ワイドオッズ{odds_str} ¥{w['投資']}\n")
        report += "\n"

    # 複勝候補
    place_candidates = betting_plan.get('複勝候補', [])
    if place_candidates:
        report += "**【複勝候補】**\n"
        for p in place_candidates:
            h = p['horse']
            num = h.get('馬番', 0)
            name = h.get('馬名', 'N/A')
            odds_min = p.get('place_odds_min', '?')
            odds_max = p.get('place_odds_max', '?')
            report += (f"　{get_number_emoji(num)} {name} "
                       f"複勝オッズ{odds_min}-{odds_max}倍 ¥{p['stake']}\n")
        report += "\n"

    # 波乱度「高」の警告
    if turbulence == "高":
        report += "⚠️⚠️ **見送り推奨** ⚠️⚠️\n"
        report += "投資ON時は見送り推奨\n\n"

    report += "---\n"

    return report


def generate_summary(selected_races: List[Dict], total_races: int, ymd: str,
                     skipped_races: List[Dict] = None) -> str:
    """最終サマリーを生成 (v12: 断層・合成オッズ統計追加)"""
    date_obj = datetime.strptime(ymd, '%Y%m%d')

    summary = "# 📊 本日の予想サマリー\n\n"
    summary += f"**日付**: {date_obj.strftime('%Y年%m月%d日')}\n"
    summary += f"**ロジックバージョン**: v12 (断層・合成オッズ対応)\n\n"

    summary += f"- **総レース数**: {total_races}レース\n"
    summary += f"- **予想対象**: {len(selected_races)}レース\n"
    summary += f"- **見送り**: {total_races - len(selected_races)}レース\n\n"

    # スキップ内訳
    if skipped_races:
        skip_flat = sum(1 for s in skipped_races if 'フラット' in str(s.get('reason', '')))
        skip_odds = sum(1 for s in skipped_races if '合成オッズ' in str(s.get('reason', '')))
        skip_other = len(skipped_races) - skip_flat - skip_odds
        summary += "【見送り内訳】\n"
        summary += f"- 🔲 断層なし(フラット混戦): {skip_flat}レース\n"
        summary += f"- 🔲 合成オッズ不足(<3倍): {skip_odds}レース\n"
        summary += f"- 🔲 その他: {skip_other}レース\n\n"

    # 波乱度別集計
    low = sum(1 for r in selected_races if r.get("turbulence") == "低")
    mid = sum(1 for r in selected_races if r.get("turbulence") == "中")
    high = sum(1 for r in selected_races if r.get("turbulence") == "高")

    summary += "【波乱度別内訳】\n"
    summary += f"- 🟢 低: {low}レース (本命有利)\n"
    summary += f"- 🟡 中: {mid}レース (拮抗)\n"
    summary += f"- 🔴 高: {high}レース (荒れる可能性)\n\n"

    # 合成オッズ統計
    syn_odds_list = [r.get('合成オッズ', 0) for r in selected_races if r.get('合成オッズ', 0) > 0]
    if syn_odds_list:
        avg_syn = sum(syn_odds_list) / len(syn_odds_list)
        summary += "【合成オッズ統計】\n"
        summary += f"- 平均合成オッズ: {avg_syn:.2f}倍\n"
        summary += f"- 4倍以上(良好): {sum(1 for o in syn_odds_list if o >= 4)}レース\n"
        summary += f"- 3〜4倍(基準): {sum(1 for o in syn_odds_list if 3 <= o < 4)}レース\n\n"

    # 投資額比較
    total_investment = sum(race.get("investment", 0) for race in selected_races)
    old_total = sum(race.get("旧ロジック", {}).get("旧_投資額", 0) for race in selected_races)
    summary += "【合計投資額】\n"
    summary += f"💰 **新ロジック: ¥{total_investment:,}** (投資OFFのため実購入なし)\n"
    if old_total > 0:
        reduction = (1 - total_investment / old_total) * 100
        summary += f"📉 旧ロジック: ¥{old_total:,} → {reduction:.1f}%削減\n"
    summary += "\n"

    # 資金管理ルール表示
    summary += "【資金管理ルール (v12)】\n"
    summary += "- 1レース固定: ¥1,000 (合成オッズ4倍超→¥1,500 / 5倍超→¥2,000)\n"
    summary += "- 最大点数: 15点 (旧: 21〜27点)\n"
    summary += "- 日次損切り: ¥10,000 / 週次: ¥30,000\n"
    summary += "- 3連続外れ → 当日終了\n\n"
    summary += "---\n"
    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_final_output.py YYYYMMDD")
        sys.exit(1)

    ymd = sys.argv[1]

    # データ読み込み
    data = load_race_data(ymd)

    if "selected_races" not in data:
        print("[ERROR] selected_races が見つかりません。先に select_predictions.py を実行してください。")
        sys.exit(1)

    selected_races = data["selected_races"]
    total_races = len(data.get("races", []))
    skipped_races = data.get("skipped_races_detail", [])

    print(f"[INFO] 予想データ: {len(selected_races)}レース")

    # Markdownレポート生成
    report = generate_summary(selected_races, total_races, ymd, skipped_races)

    for i, race in enumerate(selected_races, 1):
        report += format_race_report(race, i)

    # Markdownファイル出力
    md_file = f"predictions_{ymd}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[SUCCESS] {md_file} を生成しました")

    # JSON用データ構築
    date_obj = datetime.strptime(ymd, '%Y%m%d')
    date_str = date_obj.strftime('%Y/%m/%d')

    total_investment = sum(race.get("investment", 0) for race in selected_races)
    old_total_investment = sum(
        race.get("旧ロジック", {}).get("旧_投資額", 0) for race in selected_races
    )

    # サマリー用合成オッズ統計
    syn_odds_list = [r.get('合成オッズ', 0) for r in selected_races if r.get('合成オッズ', 0) > 0]
    avg_syn_odds = round(sum(syn_odds_list) / len(syn_odds_list), 2) if syn_odds_list else 0

    # スキップ内訳 (select_predictions.py が summary.skip_breakdown を持つ場合)
    skip_breakdown = data.get("summary", {}).get("skip_breakdown", {})

    final_data = {
        "date": date_str,
        "ymd": ymd,
        "logic_version": "v12_断層・合成オッズ対応",
        "generated_at": date_obj.strftime('%Y-%m-%d %H:%M:%S'),
        "summary": {
            "total_races": total_races,
            "selected_races": len(selected_races),
            "skipped_races": total_races - len(selected_races),
            "turbulence": {
                "低": sum(1 for r in selected_races if r.get("turbulence") == "低"),
                "中": sum(1 for r in selected_races if r.get("turbulence") == "中"),
                "高": sum(1 for r in selected_races if r.get("turbulence") == "高")
            },
            "total_investment": total_investment,
            "old_total_investment": old_total_investment,
            "investment_reduction_pct": round(
                (1 - total_investment / max(old_total_investment, 1)) * 100, 1
            ),
            "avg_synthetic_odds": avg_syn_odds,
            "skip_breakdown": skip_breakdown
        },
        "selected_predictions": selected_races,
        "総投資額": total_investment,
        "旧総投資額": old_total_investment
    }

    json_file = f"final_predictions_{ymd}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] {json_file} を生成しました")

    # コンソール出力
    print(report)


if __name__ == "__main__":
    main()
