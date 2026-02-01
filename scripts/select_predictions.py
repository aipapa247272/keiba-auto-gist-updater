#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予想選定スクリプト（投資額計算統合版 v3.0）
- 波乱度判定ロジック
- 投資額計算（週間予算管理）
- 週間収支チェックとアラート
"""

import json
import sys
import os
from typing import Dict, List
from datetime import datetime
from pathlib import Path

# 投資額計算モジュールをインポート
try:
    from calculate_investment import (
        calculate_daily_budget,
        calculate_race_investments,
        calculate_investment_stats,
        MINIMUM_WEEKLY_BUDGET,
        RECOMMENDED_WEEKLY_BUDGET
    )
    from weekly_tracker import WeeklyTracker, ALERT_LEVEL_CRITICAL, ALERT_LEVEL_WARNING
    INVESTMENT_ENABLED = True
except ImportError:
    print("⚠️ 投資額計算モジュールが見つかりません（投資額計算は無効）")
    INVESTMENT_ENABLED = False


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
        if data_quality < 0.4:
            base_score += 10  # データ不足 → 予測困難
    
    # 6. 信頼度チェック
    top3_confidence = [h.get('des_score', {}).get('信頼度', '極低') for h in top3_horses[:3]]
    low_confidence_count = sum(1 for c in top3_confidence if c in ['低', '極低'])
    
    if low_confidence_count >= 2:
        base_score += 10  # 上位馬の信頼度が低い
    
    # 最終判定
    if base_score < 30:
        return '低'  # 堅い
    elif base_score < 80:
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


def apply_investment_calculation(selected_races: List[Dict], ymd: str):
    """
    選定されたレースに投資額を計算して適用
    """
    if not INVESTMENT_ENABLED:
        print("⚠️ 投資額計算はスキップされました（モジュール未インストール）")
        return
    
    # 環境変数から週間投資額を取得（デフォルト: 30,000円）
    weekly_budget = int(os.environ.get('WEEKLY_BUDGET', RECOMMENDED_WEEKLY_BUDGET))
    
    print(f"\n💰 投資額計算開始")
    print(f"  週間投資額: ¥{weekly_budget:,}")
    
    # 週間収支トラッカーを初期化
    tracker = WeeklyTracker()
    
    # 週間収支が存在しない場合は初期化
    if tracker.data.get('start_date') is None:
        date_obj = datetime.strptime(ymd, '%Y%m%d')
        tracker.initialize_week(weekly_budget, date_obj)
    
    # アラートチェック
    alert_level, alert_message = tracker.check_alert()
    
    if alert_level == ALERT_LEVEL_CRITICAL:
        print(f"\n🚨 {alert_message}")
        print("→ 今日の予想生成を終了します")
        # 予想対象を0件にする
        selected_races.clear()
        return
    
    if alert_level == ALERT_LEVEL_WARNING:
        print(f"\n⚠️ {alert_message}")
    
    # 投資比率を取得（警告時は50%削減）
    investment_ratio = tracker.get_investment_ratio()
    
    # 1日あたりの予算を計算
    date_obj = datetime.strptime(ymd, '%Y%m%d')
    daily_budget = calculate_daily_budget(weekly_budget, date_obj)
    
    # 投資比率を適用
    daily_budget = daily_budget * investment_ratio
    
    print(f"  1日予算: ¥{daily_budget:,.0f}")
    if investment_ratio < 1.0:
        print(f"  （投資比率: {investment_ratio * 100:.0f}% 削減中）")
    
    # 波乱度分布を計算
    turbulence_dist = {'低': 0, '中': 0, '高': 0}
    for race in selected_races:
        turbulence = race.get('波乱度', '中')
        turbulence_dist[turbulence] += 1
    
    print(f"  波乱度分布: 低{turbulence_dist['低']}R / 中{turbulence_dist['中']}R / 高{turbulence_dist['高']}R")
    
    # レース別投資額を計算
    races_dict = {race.get('race_id', str(i)): race for i, race in enumerate(selected_races)}
    investments = calculate_race_investments(races_dict, daily_budget, turbulence_dist)
    
    # 投資額を各レースに適用
    for race in selected_races:
        race_id = race.get('race_id', '')
        investment = investments.get(race_id, 0)
        race['投資額'] = investment
    
    # 統計情報を表示
    stats = calculate_investment_stats(investments)
    print(f"\n📊 投資統計:")
    print(f"  総投資額: ¥{stats['total_investment']:,}")
    print(f"  投資レース数: {stats['race_count']}R")
    print(f"  平均投資額: ¥{stats['avg_investment']:,.0f}/R")


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
    
    # 投資額計算を適用
    apply_investment_calculation(selected_races, ymd)
    
    # 選定結果を表示
    print("\n📋 選定結果:")
    print("-" * 50)
    
    for i, race in enumerate(selected_races, 1):
        race_name = race.get('レース名', 'N/A')
        venue = race.get('競馬場', '不明')
        race_num = race.get('レース番号', '?')
        turbulence = race.get('波乱度', '?')
        quality = race.get('データ品質スコア', 0)
        investment = race.get('投資額', 0)
        
        turb_icon = {'低': '🟢', '中': '🟡', '高': '🔴'}.get(turbulence, '⚪')
        
        print(f"{i}. {venue} R{race_num} {race_name}")
        print(f"   波乱度: {turb_icon} {turbulence} | データ品質: {quality:.1%}")
        if investment > 0:
            print(f"   💰 投資額: ¥{investment:,}")
        
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
    
    # 総投資額を計算
    total_investment = sum(race.get('投資額', 0) for race in selected_races)
    data['総投資額'] = total_investment
    
    with open(input_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("-" * 50)
    print(f"✅ 完了: {input_file} を更新しました")
    print(f"💰 総投資額: ¥{total_investment:,}")


if __name__ == '__main__':
    main()
