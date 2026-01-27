#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予想検証スクリプト（新規 v2.0）
- オッズ・人気データとAI評価の乖離をチェック
- 見落としの可能性がある馬を警告
"""

import json
import sys
from typing import Dict, List


def validate_with_odds(race: Dict) -> List[Dict]:
    """
    オッズ・人気データとAI評価を照合して警告を生成
    """
    warnings = []
    horses = race.get('horses', [])
    
    if not horses:
        return warnings
    
    # AI評価の上位3頭
    top3_by_ai = horses[:3]
    
    # オッズ・人気データがある馬をフィルタ
    horses_with_odds = [h for h in horses if h.get('オッズ') and h.get('人気')]
    
    if not horses_with_odds:
        # オッズデータがない場合は警告なし
        return warnings
    
    # 1番人気の馬を特定
    most_popular = min(horses_with_odds, key=lambda h: h.get('人気', 99))
    popular_rank = most_popular.get('人気', 99)
    
    # 警告1: AI本命が不人気（5番人気以下）
    honmei = top3_by_ai[0] if len(top3_by_ai) >= 1 else None
    if honmei and honmei.get('人気'):
        honmei_popular = honmei.get('人気', 99)
        honmei_odds = honmei.get('オッズ', 0)
        
        if honmei_popular >= 5:
            warnings.append({
                'タイプ': 'AI本命が不人気',
                '馬番': honmei.get('馬番'),
                '馬名': honmei.get('馬名'),
                'AIスコア': honmei.get('des_score', {}).get('total', 0),
                '信頼度': honmei.get('des_score', {}).get('信頼度', '不明'),
                '人気': honmei_popular,
                'オッズ': honmei_odds,
                'メッセージ': f'AI本命が{honmei_popular}番人気（オッズ{honmei_odds}倍）',
                '推奨': '市場が低評価している理由を確認してください'
            })
    
    # 警告2: 1番人気がAI予想に含まれていない
    top3_numbers = [h.get('馬番') for h in top3_by_ai]
    
    if popular_rank == 1 and most_popular.get('馬番') not in top3_numbers:
        ai_score = most_popular.get('des_score', {}).get('total', 0)
        ai_confidence = most_popular.get('des_score', {}).get('信頼度', '不明')
        
        # AIがどの程度評価しているか確認
        ai_rank = horses.index(most_popular) + 1 if most_popular in horses else 99
        
        warnings.append({
            'タイプ': '1番人気が予想外',
            '馬番': most_popular.get('馬番'),
            '馬名': most_popular.get('馬名'),
            'AIスコア': ai_score,
            'AI順位': ai_rank,
            '信頼度': ai_confidence,
            '人気': 1,
            'オッズ': most_popular.get('オッズ', 0),
            'メッセージ': f'1番人気（{most_popular.get("オッズ", 0)}倍）がAI評価{ai_rank}位（{ai_score}点）',
            '推奨': 'AIが低評価した理由を分析してください'
        })
        
        # 低評価の理由を分析
        reasons = analyze_low_rating(most_popular)
        if reasons:
            warnings[-1]['低評価の理由'] = reasons
    
    # 警告3: AI上位3頭が全て人気薄（全員5番人気以下）
    top3_popularities = [h.get('人気', 99) for h in top3_by_ai if h.get('人気')]
    
    if len(top3_popularities) >= 3 and all(p >= 5 for p in top3_popularities):
        warnings.append({
            'タイプ': 'AI上位3頭が全て人気薄',
            'メッセージ': f'AI本命◎○▲の人気: {top3_popularities}',
            '推奨': '市場とAI評価が大きく乖離しています。慎重な検討が必要です'
        })
    
    return warnings


def analyze_low_rating(horse: Dict) -> List[str]:
    """
    AIが低評価した理由を分析
    """
    reasons = []
    
    des_score = horse.get('des_score', {})
    
    # 距離適性が低い
    b_score = des_score.get('B_距離馬場適性', 0)
    if b_score < 10:
        reasons.append(f'距離適性が低い（{b_score}点/25点）')
    
    # 展開が向いていない
    d_score = des_score.get('D_展開適性', 0)
    if d_score < 10:
        reasons.append(f'展開適性が低い（{d_score}点/25点）')
        
        # 詳細を確認
        running_style = horse.get('推定脚質', '不明')
        waku = horse.get('枠番', 0)
        if running_style != '不明':
            reasons.append(f'脚質: {running_style}、枠番: {waku}番')
    
    # 過去走データが少ない
    past_races = horse.get('past_races', [])
    if len(past_races) < 2:
        reasons.append(f'過去走データが不足（{len(past_races)}走のみ）')
    
    # 信頼度が低い
    confidence = des_score.get('信頼度', '不明')
    if confidence in ['低', '極低']:
        reasons.append(f'信頼度: {confidence}')
    
    return reasons


def generate_warnings_report(selected_races: List[Dict]) -> str:
    """
    全レースの警告レポートを生成
    """
    report = []
    report.append("# 🚨 人気乖離アラート\n")
    
    has_warnings = False
    
    for i, race in enumerate(selected_races, 1):
        warnings = validate_with_odds(race)
        
        if warnings:
            has_warnings = True
            race_name = race.get('レース名', 'N/A')
            venue = race.get('競馬場', '不明')
            race_num = race.get('レース番号', '?')
            
            report.append(f"## 予想{i}: {venue} R{race_num} {race_name}\n")
            
            for j, warning in enumerate(warnings, 1):
                report.append(f"### ⚠️ 警告{j}: {warning['タイプ']}\n")
                report.append(f"**{warning.get('馬番', '?')}番 {warning.get('馬名', 'N/A')}**\n")
                report.append(f"- {warning['メッセージ']}\n")
                
                if 'AIスコア' in warning:
                    report.append(f"- AIスコア: {warning['AIスコア']}点（信頼度: {warning.get('信頼度', '?')}）\n")
                
                if 'AI順位' in warning:
                    report.append(f"- AI評価順位: {warning['AI順位']}位\n")
                
                if '低評価の理由' in warning:
                    report.append(f"- **AIが低評価した理由:**\n")
                    for reason in warning['低評価の理由']:
                        report.append(f"  - {reason}\n")
                
                report.append(f"- **推奨:** {warning['推奨']}\n")
                report.append("\n")
    
    if not has_warnings:
        report.append("✅ 人気とAI評価の大きな乖離は検出されませんでした。\n")
    
    return ''.join(report)


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_predictions.py <ymd>")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ {input_file} が見つかりません")
        sys.exit(1)
    
    selected_races = data.get('selected_races', [])
    
    if not selected_races:
        print("⚠️ 予想対象レースがありません")
        sys.exit(0)
    
    print(f"🔍 人気乖離チェック開始: {len(selected_races)}レース")
    print("-" * 50)
    
    # 各レースの乖離をチェック
    total_warnings = 0
    
    for i, race in enumerate(selected_races, 1):
        race_name = race.get('レース名', 'N/A')
        warnings = validate_with_odds(race)
        
        print(f"{i}. {race_name}")
        
        if warnings:
            total_warnings += len(warnings)
            for warning in warnings:
                print(f"   ⚠️ {warning['タイプ']}: {warning.get('馬番', '?')}番 {warning.get('馬名', 'N/A')}")
        else:
            print(f"   ✅ 乖離なし")
        
        # レースに警告を追加
        race['人気乖離警告'] = warnings
    
    print("-" * 50)
    print(f"⚠️ 検出された警告: {total_warnings}件")
    
    # 警告レポートを生成
    warnings_report = generate_warnings_report(selected_races)
    
    # データを更新
    data['selected_races'] = selected_races
    data['人気乖離警告数'] = total_warnings
    
    with open(input_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 警告レポートを保存
    report_file = f"warnings_report_{ymd}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(warnings_report)
    
    print(f"💾 警告レポート保存: {report_file}")
    print(f"✅ 完了: {input_file} を更新しました")


if __name__ == '__main__':
    main()
