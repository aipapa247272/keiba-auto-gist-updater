#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投資額計算モジュール
DES 統合ルール準拠の投資額計算ロジック

機能:
- 週間初期投資額から1日あたりの投資額を計算
- 波乱度別の配分比率を適用
- 買い目点数に応じた投資額の調整
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# ========================================
# 定数定義
# ========================================

# 最低週間投資額（円）
MINIMUM_WEEKLY_BUDGET = 10000

# 推奨週間投資額（円）
RECOMMENDED_WEEKLY_BUDGET = 30000

# 波乱度別配分比率（統合ルール準拠）
TURBULENCE_WEIGHTS = {
    '低': 0.60,  # 60%
    '中': 0.40,  # 40%
    '高': 0.00   # 0%（見送り）
}

# 1点あたり最低投資額（円）
MIN_BET_AMOUNT = 100


# ========================================
# 週間予算管理
# ========================================

def get_remaining_days(start_date: datetime = None) -> int:
    """
    週の残り日数を計算
    
    Args:
        start_date: 開始日（Noneの場合は今日）
    
    Returns:
        残り日数（開始日を含む、月曜=7日、日曜=1日）
    """
    if start_date is None:
        start_date = datetime.now()
    
    # 曜日を取得（0=月曜、6=日曜）
    weekday = start_date.weekday()
    
    # 残り日数（開始日を含む）
    remaining_days = 7 - weekday
    
    return remaining_days


def calculate_daily_budget(weekly_budget: int, start_date: datetime = None) -> float:
    """
    1日あたりの予算を計算
    
    Args:
        weekly_budget: 週間初期投資額（円）
        start_date: 開始日（Noneの場合は今日）
    
    Returns:
        1日あたりの予算（円）
    """
    # 最低ラインチェック
    if weekly_budget < MINIMUM_WEEKLY_BUDGET:
        raise ValueError(f"週間投資額は{MINIMUM_WEEKLY_BUDGET:,}円以上に設定してください")
    
    # 残り日数を取得
    remaining_days = get_remaining_days(start_date)
    
    # 1日あたりの予算を計算
    daily_budget = weekly_budget / remaining_days
    
    return daily_budget


# ========================================
# レース別投資額計算
# ========================================

def calculate_race_investments(
    races: Dict,
    daily_budget: float,
    turbulence_dist: Dict[str, int] = None
) -> Dict[str, int]:
    """
    レース別の投資額を計算
    
    Args:
        races: レースデータ（race_id -> race_data）
        daily_budget: 1日あたりの予算（円）
        turbulence_dist: 波乱度分布 {'低': 2, '中': 3, '高': 0}
                        Noneの場合は races から自動計算
    
    Returns:
        レース別投資額 {race_id: 投資額}
    """
    
    # 波乱度分布を自動計算
    if turbulence_dist is None:
        turbulence_dist = {'低': 0, '中': 0, '高': 0}
        for race_data in races.values():
            turbulence = race_data.get('波乱度', '中')
            turbulence_dist[turbulence] = turbulence_dist.get(turbulence, 0) + 1
    
    # 各波乱度の重み付き合計を計算
    total_weighted_races = sum(
        turbulence_dist.get(t, 0) * TURBULENCE_WEIGHTS[t]
        for t in ['低', '中', '高']
    )
    
    # 投資対象がない場合
    if total_weighted_races == 0:
        return {}
    
    # レース別投資額を計算
    investments = {}
    
    for race_id, race_data in races.items():
        turbulence = race_data.get('波乱度', '中')
        
        # 波乱度「高」は見送り
        if turbulence == '高':
            investments[race_id] = 0
            continue
        
        # 買い目点数を取得
        bet_patterns = race_data.get('買い目', [])
        bet_count = len(bet_patterns) if bet_patterns else 24  # デフォルト24通り
        
        # このレースへの配分額
        race_weight = TURBULENCE_WEIGHTS[turbulence]
        race_budget = (daily_budget * race_weight) / turbulence_dist[turbulence]
        
        # 1点あたりの金額を計算（100円単位に調整）
        per_bet_amount = max(MIN_BET_AMOUNT, int(race_budget / bet_count / 100) * 100)
        
        # 最終投資額（1点 × 点数）
        total_investment = per_bet_amount * bet_count
        
        investments[race_id] = total_investment
    
    return investments


# ========================================
# 統計情報の計算
# ========================================

def calculate_investment_stats(investments: Dict[str, int]) -> Dict:
    """
    投資額の統計情報を計算
    
    Args:
        investments: レース別投資額 {race_id: 投資額}
    
    Returns:
        統計情報
    """
    total_investment = sum(investments.values())
    race_count = len([v for v in investments.values() if v > 0])
    avg_investment = total_investment / race_count if race_count > 0 else 0
    
    return {
        'total_investment': total_investment,
        'race_count': race_count,
        'avg_investment': avg_investment
    }


# ========================================
# メイン処理（テスト用）
# ========================================

def main():
    """テスト実行"""
    
    print("=" * 60)
    print("投資額計算モジュール - テスト実行")
    print("=" * 60)
    
    # テストケース1: 月曜日開始
    print("\n【テスト1】月曜日開始（推奨額30,000円）")
    weekly_budget = 30000
    start_date = datetime(2026, 2, 3)  # 2026/02/03（月）
    
    remaining_days = get_remaining_days(start_date)
    daily_budget = calculate_daily_budget(weekly_budget, start_date)
    
    print(f"週間投資額: ¥{weekly_budget:,}")
    print(f"開始日: {start_date.strftime('%Y/%m/%d')}（月）")
    print(f"残り日数: {remaining_days}日")
    print(f"1日あたり予算: ¥{daily_budget:,.0f}")
    
    # テストケース2: 水曜日開始
    print("\n【テスト2】水曜日開始（推奨額30,000円）")
    start_date = datetime(2026, 2, 5)  # 2026/02/05（水）
    
    remaining_days = get_remaining_days(start_date)
    daily_budget = calculate_daily_budget(weekly_budget, start_date)
    
    print(f"週間投資額: ¥{weekly_budget:,}")
    print(f"開始日: {start_date.strftime('%Y/%m/%d')}（水）")
    print(f"残り日数: {remaining_days}日")
    print(f"1日あたり予算: ¥{daily_budget:,.0f}")
    
    # テストケース3: レース別投資額計算
    print("\n【テスト3】レース別投資額計算（5レース想定）")
    
    # ダミーレースデータ
    dummy_races = {
        '202605010201': {
            '波乱度': '低',
            '買い目': ['1-2-3'] * 24  # 24通り
        },
        '202605010208': {
            '波乱度': '中',
            '買い目': ['1-2-3'] * 24
        },
        '202605010209': {
            '波乱度': '中',
            '買い目': ['1-2-3'] * 24
        },
        '202608010201': {
            '波乱度': '中',
            '買い目': ['1-2-3'] * 24
        },
        '202608010203': {
            '波乱度': '高',  # 見送り
            '買い目': ['1-2-3'] * 24
        }
    }
    
    turbulence_dist = {'低': 1, '中': 3, '高': 1}
    daily_budget = 4286  # 月曜開始の場合
    
    investments = calculate_race_investments(dummy_races, daily_budget, turbulence_dist)
    stats = calculate_investment_stats(investments)
    
    print(f"波乱度分布: 低{turbulence_dist['低']}R / 中{turbulence_dist['中']}R / 高{turbulence_dist['高']}R")
    print(f"1日予算: ¥{daily_budget:,.0f}")
    print(f"\nレース別投資額:")
    
    for race_id, amount in investments.items():
        turbulence = dummy_races[race_id]['波乱度']
        if amount > 0:
            print(f"  {race_id}: ¥{amount:,} ({turbulence})")
        else:
            print(f"  {race_id}: 見送り ({turbulence})")
    
    print(f"\n投資統計:")
    print(f"  総投資額: ¥{stats['total_investment']:,}")
    print(f"  投資レース数: {stats['race_count']}R")
    print(f"  平均投資額: ¥{stats['avg_investment']:,.0f}/R")
    
    print("\n" + "=" * 60)
    print("テスト完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
