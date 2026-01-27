#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予想選定スクリプト（改善版 v2.0）
- 波乱度判定ロジックの改善
- 頭数・重量条件・脚質構成を考慮
"""

import json
import sys
from typing import Dict, List


def calculate_turbulence_level(race: Dict, top3_horses: List[Dict]) -> str:
    """
    波乱度を判定（低・中・高）
    
    判定要素:
    1. 頭数（少頭数=堅い、多頭数=荒れる）
    2. 重量条件（別定=堅い、ハンデ=荒れる）
    3. 上位3頭のスコア差（大きい=堅い、小さい=荒れる）
    4. 脚質構成（逃げ馬3頭以上=荒れる）
    5. データ品質（欠損多い=荒れる）
    """
    base_score = 50  # 中立スコア
    
    # 1. 頭数による補正
    head_count = race.get('取得頭数', 8)
    if head_count <= 8:
        base_score -= 10  # 少頭数 → 堅くなる
    elif head_count >= 14:
        base_score += 10  # 多頭数 → 荒れやすい
    
    # 2. 重量条件
    weight_condition = race.get('重量条件', '不明')
    if weight_condition in ['別定', '定量']:
        base_score -= 15  # 実力差が出やすい
    elif weight_condition == 'ハンデ':
        base_score += 15  # 実力が均衡
    
    # 3. 上位3頭のスコア差
    if len(top3_horses) >= 3:
        score1 = top3_horses[0].get('des_score', {}).get('total', 0)
        score3 = top3_horses[2].get('des_score', {}).get('total', 0)
        score_diff = score1 - score3
        
        if score_diff >= 20:
            base_score -= 10  # 本命が抜けている
        elif score_diff <= 5:
            base_score += 10  # 大混戦
    
    # 4. 脚質構成
    race_analysis = race.get('レース分析', {})
    style_count = race_analysis.get('脚質構成', {})
    
    nige_count = style_count.get('逃げ', 0)
    if nige_count >= 3:
        base_score += 5  # 逃げ争い → ハイペース消耗戦
    elif nige_count == 0:
        base_score += 5  # 逃げ不在 → スローペース瞬発力勝負
    
    # 5. データ品質
    horses = race.get('horses', [])
    total_horses = len(horses)
    horses_with_data = sum(1 for h in horses if len(h.get('past_races', [])) >= 2)
    
    if total_horses > 0:
        data_quality = horses_with_data / total_horses
        if data_quality < 0.7:
            base_score += 20  # データ不足 → 予測困難
    
    # 6. 信頼度チェック
    top3_confidence = [h.get('des_score', {}).get('信頼度', '極低') for h in top3_horses[:3]]
    low_confidence_count = sum(1 for c in top3_confidence if c in ['低', '極低'])
    
    if low_confidence_count >= 2:
        base_score += 10  # 上位馬の信頼度が低い
    
    # 最終判定
    if base_score < 30:
        return '低'  # 堅い
    elif base_score < 70:
        return '中'
    else:
        return '高'  # 荒れる


def select_predictions(races: List[Dict], max_races: int = 5) -> List[Dict]:
    """
    1日のレースから予想対象を選定
    
    選定基準:
    - 基本: 3レース
    - 例外: 同格（データ品質が良い）レースが多い場合は最大5レース
    - 優先順位: 波乱度「低」「中」> 「高」
    - 波乱度「高」は原則見送り
    """
    # データ品質でフィルタリング
    valid_races = []
    
    for race in races:
        horses = race.get('horses', [])
        if len(horses) < 5:
            continue  # 馬が少なすぎるレースは除外
        
        # 上位3頭のスコアを確認
        top3 = horses[:3]
        if not all(h.get('des_score') for h in top3):
            continue  # スコアがない馬がいる場合は除外
        
        # 波乱度を計算
        turbulence = calculate_turbulence_level(race, top3)
        race['波乱度'] = turbulence
        
        # データ品質スコアを計算
        horses_with_good_data = sum(
            1 for h in horses 
            if len(h.get('past_races', [])) >= 2 
            and h.get('des_score', {}).get('total', 0) >= 30
        )
        data_quality_score = horses_with_good_data / len(horses) if horses else 0
        race['データ品質スコア'] = data_quality_score
        
        valid_races.append(race)
    
    # 波乱度と データ品質で優先順位付け
    def race_priority(race):
        turbulence = race.get('波乱度', '高')
        quality = race.get('データ品質スコア', 0)
        
        # 優先度スコア（高いほど優先）
        if turbulence == '低':
            turb_score = 100
        elif turbulence == '中':
            turb_score = 50
        else:  # 高
            turb_score = 0
        
        return turb_score + (quality * 20)
    
    valid_races.sort(key=race_priority, reverse=True)
    
    # 波乱度「高」は原則除外（データ品質が極めて高い場合のみ例外）
    filtered_races = []
    for race in valid_races:
        if race.get('波乱度') == '高' and race.get('データ品質スコア', 0) < 0.8:
            continue  # 見送り（ただしログには残す）
        filtered_races.append(race)
    
    # 最大5レースまで
    selected = filtered_races[:max_races]
    
    return selected


def main():
    if len(sys.argv) < 2:
        print("Usage: python select_predictions.py <ymd>")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ {input_file} が見つかりません")
        sys.exit(1)
    
    races = data.get('races', [])
    
    print(f"📊 予想選定開始: {len(races)}レース")
    print("-" * 50)
    
    # 予想対象レースを選定
    selected_races = select_predictions(races, max_races=5)
    
    print(f"✅ 予想対象: {len(selected_races)}レース")
    print()
    
    # 選定結果を表示
    for i, race in enumerate(selected_races, 1):
        race_name = race.get('レース名', 'N/A')
        venue = race.get('競馬場', '不明')
        race_num = race.get('レース番号', '?')
        turbulence = race.get('波乱度', '?')
        quality = race.get('データ品質スコア', 0)
        
        turb_icon = {'低': '🟢', '中': '🟡', '高': '🔴'}.get(turbulence, '⚪')
        
        print(f"{i}. {venue} R{race_num} {race_name}")
        print(f"   波乱度: {turb_icon} {turbulence} | データ品質: {quality:.1%}")
        
        # 本命・対抗・単穴
        horses = race.get('horses', [])
        if len(horses) >= 3:
            for j, mark in enumerate(['◎', '○', '▲']):
                horse = horses[j]
                score = horse.get('des_score', {})
                print(f"   {mark} {horse.get('馬番', '?')}番 {horse.get('馬名', 'N/A')} "
                      f"{score.get('total', 0)}点 ({score.get('信頼度', '?')})")
        print()
    
    # 見送りレースの集計
    skipped_races = [r for r in races if r not in selected_races and r.get('波乱度') == '高']
    if skipped_races:
        print(f"⚠️ 見送りレース: {len(skipped_races)}レース（波乱度「高」のため）")
        for race in skipped_races[:3]:  # 最大3件表示
            print(f"  - {race.get('競馬場', '?')} R{race.get('レース番号', '?')} "
                  f"{race.get('レース名', 'N/A')}")
    
    # 選定結果を保存
    data['selected_races'] = selected_races
    data['総レース数'] = len(races)
    data['予想対象数'] = len(selected_races)
    data['見送り数'] = len(races) - len(selected_races)
    
    with open(input_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("-" * 50)
    print(f"✅ 完了: {input_file} を更新しました")


if __name__ == '__main__':
    main()
