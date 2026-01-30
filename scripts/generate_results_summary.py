#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レース結果サマリー生成スクリプト

race_results_*.json から視覚的に分かりやすいMarkdownを生成
"""

import os
import sys
import json
from datetime import datetime

def format_date(ymd):
    """
    YYYYMMDD → YYYY年MM月DD日
    """
    try:
        dt = datetime.strptime(ymd, '%Y%m%d')
        return dt.strftime('%Y年%m月%d日')
    except:
        return ymd

def generate_summary_markdown(ymd):
    """
    結果サマリーをMarkdown形式で生成
    """
    input_file = f"race_results_{ymd}.json"
    
    if not os.path.exists(input_file):
        print(f"[ERROR] 結果ファイルが見つかりません: {input_file}")
        return False
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    summary = data['summary']
    results = data['results']
    
    # Markdown生成
    md = []
    
    # ヘッダー
    md.append(f"# 📊 本日の結果サマリー\n")
    md.append(f"日付: {format_date(ymd)}\n")
    
    # サマリー情報
    md.append(f"- 総レース数: {summary['total_races']}レース")
    md.append(f"- 予想対象: {summary['total_races']}レース")
    md.append(f"- 的中: {summary['hit_count']}レース")
    md.append(f"- 不的中: {summary['miss_count']}レース")
    md.append(f"- 取得不可: {summary['unavailable_count']}レース\n")
    
    # 成績
    md.append(f"【成績】\n")
    
    # 的中率
    hit_rate = summary['hit_rate']
    if hit_rate >= 30:
        hit_icon = "🟢"
        hit_label = "好調"
    elif hit_rate >= 15:
        hit_icon = "🟡"
        hit_label = "平均的"
    else:
        hit_icon = "🔴"
        hit_label = "要改善"
    
    md.append(f"- {hit_icon} 的中率: {hit_rate}% ({hit_label})")
    
    # 回収率
    recovery = summary['recovery_rate']
    if recovery >= 100:
        rec_icon = "✅"
        rec_label = "プラス収支"
    elif recovery >= 80:
        rec_icon = "⚠️"
        rec_label = "惜しい"
    else:
        rec_icon = "❌"
        rec_label = "マイナス"
    
    md.append(f"- {rec_icon} 回収率: {recovery}% ({rec_label})\n")
    
    # 収支
    profit = summary['total_profit']
    if profit > 0:
        profit_icon = "💰"
        profit_color = "+"
    elif profit == 0:
        profit_icon = "➖"
        profit_color = "±"
    else:
        profit_icon = "📉"
        profit_color = ""
    
    md.append(f"【合計投資額】 💴 {summary['total_investment']}円\n")
    md.append(f"【合計払戻】 💵 {summary['total_return']}円\n")
    md.append(f"【収支】 {profit_icon} {profit_color}{profit}円\n")
    
    md.append("---\n")
    
    # レース結果詳細
    md.append("## 🏇 レース結果詳細\n")
    
    for i, race in enumerate(results, 1):
        status = race['status']
        
        if status == '的中':
            status_icon = "🎯"
        elif status == '不的中':
            status_icon = "❌"
        else:
            status_icon = "⚠️"
        
        md.append(f"### {status_icon} 予想 {i}\n")
        md.append(f"📍 {race['venue']}{race['race_num']}R {race['race_name']}\n")
        
        if status == '結果取得不可':
            md.append(f"- ❗ 結果取得不可\n")
        else:
            pred = '-'.join(race.get('predicted', []))
            actual = '-'.join(race.get('actual', []))
            
            md.append(f"◎ 本命: {pred}")
            md.append(f"🏁 実績: {actual}\n")
            
            if status == '的中':
                md.append(f"- 💰 払戻: {race['payout']}円")
                md.append(f"- 📈 収支: +{race['profit']}円\n")
            else:
                md.append(f"- 💸 投資: {race['investment']}円")
                md.append(f"- 📉 収支: {race['profit']}円\n")
        
        md.append("")
    
    # ファイル保存
    output_file = f"results_summary_{ymd}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    
    print(f"[SUCCESS] 結果サマリーを生成しました: {output_file}")
    
    return True

def main():
    if len(sys.argv) < 2:
        print("[ERROR] 使用方法: python generate_results_summary.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    try:
        datetime.strptime(ymd, '%Y%m%d')
    except ValueError:
        print(f"[ERROR] 無効な日付形式: {ymd}")
        sys.exit(1)
    
    print(f"[INFO] 結果サマリー生成を開始します: {ymd}")
    
    success = generate_summary_markdown(ymd)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
