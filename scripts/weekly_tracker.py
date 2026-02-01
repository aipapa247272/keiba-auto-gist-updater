#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
週間収支管理モジュール
1週間単位での投資・払戻・収支を追跡

機能:
- 週間収支の初期化（月曜日または任意開始日）
- 日次投資・払戻の記録
- 残高チェックとアラート判定
- 週間統計の出力
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

# ========================================
# 定数定義
# ========================================

# アラートレベル
ALERT_LEVEL_OK = 'ok'
ALERT_LEVEL_WARNING = 'warning'  # 残高30%以下
ALERT_LEVEL_CRITICAL = 'critical'  # 残高0円以下

# アラート閾値
WARNING_THRESHOLD = 0.30  # 30%
CRITICAL_THRESHOLD = 0.00  # 0%

# 週間収支データのパス
WEEKLY_TRACKER_PATH = Path(__file__).parent / 'weekly_tracker.json'


# ========================================
# 週間収支管理クラス
# ========================================

class WeeklyTracker:
    """週間収支管理"""
    
    def __init__(self, data_path: Path = WEEKLY_TRACKER_PATH):
        """
        初期化
        
        Args:
            data_path: 週間収支データの保存先パス
        """
        self.data_path = data_path
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """データを読み込み"""
        if self.data_path.exists():
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 初期データ
            return {
                'start_date': None,
                'end_date': None,
                'initial_budget': 0,
                'invested': 0,
                'returns': 0,
                'balance': 0,
                'daily_records': []
            }
    
    def _save_data(self):
        """データを保存"""
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def initialize_week(self, initial_budget: int, start_date: datetime = None):
        """
        週間収支を初期化
        
        Args:
            initial_budget: 初期投資額（円）
            start_date: 開始日（Noneの場合は今日）
        """
        if start_date is None:
            start_date = datetime.now()
        
        # 週の終了日を計算（日曜日）
        days_until_sunday = 6 - start_date.weekday()
        end_date = start_date + timedelta(days=days_until_sunday)
        
        self.data = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'initial_budget': initial_budget,
            'invested': 0,
            'returns': 0,
            'balance': initial_budget,
            'daily_records': []
        }
        
        self._save_data()
        
        print(f"週間収支を初期化しました")
        print(f"  開始日: {self.data['start_date']}")
        print(f"  終了日: {self.data['end_date']}")
        print(f"  初期投資額: ¥{initial_budget:,}")
    
    def add_daily_record(self, date: str, invested: int, returns: int, race_count: int):
        """
        日次記録を追加
        
        Args:
            date: 日付（YYYY-MM-DD）
            invested: 投資額（円）
            returns: 払戻額（円）
            race_count: レース数
        """
        # 累計を更新
        self.data['invested'] += invested
        self.data['returns'] += returns
        self.data['balance'] = self.data['initial_budget'] - self.data['invested'] + self.data['returns']
        
        # 日次記録を追加
        daily_record = {
            'date': date,
            'invested': invested,
            'returns': returns,
            'profit': returns - invested,
            'race_count': race_count,
            'balance': self.data['balance']
        }
        
        self.data['daily_records'].append(daily_record)
        
        self._save_data()
        
        print(f"{date} の記録を追加しました")
        print(f"  投資額: ¥{invested:,}")
        print(f"  払戻額: ¥{returns:,}")
        print(f"  収支: ¥{returns - invested:+,}")
        print(f"  残高: ¥{self.data['balance']:,}")
    
    def check_alert(self) -> Tuple[str, str]:
        """
        アラートレベルをチェック
        
        Returns:
            (アラートレベル, メッセージ)
        """
        if self.data['initial_budget'] == 0:
            return ALERT_LEVEL_OK, ""
        
        balance_ratio = self.data['balance'] / self.data['initial_budget']
        
        if balance_ratio < CRITICAL_THRESHOLD:
            # 🚨 危険レベル
            message = (
                f"🚨 週間予算を超過しました\n"
                f"超過額: ¥{abs(self.data['balance']):,}\n"
                f"→ 今週の予想生成を終了します\n"
                f"→ 次週月曜日に新たな初期投資額を設定してください"
            )
            return ALERT_LEVEL_CRITICAL, message
        
        elif balance_ratio < WARNING_THRESHOLD:
            # ⚠️ 警告レベル
            message = (
                f"⚠️ 警告: 週間予算の残高が{int(WARNING_THRESHOLD * 100)}%を切りました\n"
                f"残予算: ¥{self.data['balance']:,}\n"
                f"→ 今後の投資を控えめに調整します"
            )
            return ALERT_LEVEL_WARNING, message
        
        else:
            return ALERT_LEVEL_OK, ""
    
    def get_investment_ratio(self) -> float:
        """
        投資比率を取得（アラートレベルに応じて調整）
        
        Returns:
            投資比率（1.0=通常、0.5=50%削減、0.0=停止）
        """
        alert_level, _ = self.check_alert()
        
        if alert_level == ALERT_LEVEL_CRITICAL:
            return 0.0  # 投資停止
        elif alert_level == ALERT_LEVEL_WARNING:
            return 0.5  # 50%削減
        else:
            return 1.0  # 通常
    
    def get_summary(self) -> Dict:
        """
        週間統計を取得
        
        Returns:
            統計情報
        """
        profit = self.data['returns'] - self.data['invested']
        roi = (profit / self.data['invested'] * 100) if self.data['invested'] > 0 else 0
        
        return {
            'start_date': self.data['start_date'],
            'end_date': self.data['end_date'],
            'initial_budget': self.data['initial_budget'],
            'invested': self.data['invested'],
            'returns': self.data['returns'],
            'profit': profit,
            'roi': roi,
            'balance': self.data['balance'],
            'daily_count': len(self.data['daily_records'])
        }
    
    def print_summary(self):
        """週間統計を出力"""
        summary = self.get_summary()
        
        print("=" * 60)
        print("週間収支サマリー")
        print("=" * 60)
        print(f"期間: {summary['start_date']} 〜 {summary['end_date']}")
        print(f"初期投資額: ¥{summary['initial_budget']:,}")
        print(f"投資額: ¥{summary['invested']:,}")
        print(f"払戻額: ¥{summary['returns']:,}")
        print(f"収支: ¥{summary['profit']:+,}")
        print(f"回収率: {summary['roi']:+.1f}%")
        print(f"残予算: ¥{summary['balance']:,}")
        print(f"記録日数: {summary['daily_count']}日")
        print("=" * 60)


# ========================================
# メイン処理（テスト用）
# ========================================

def main():
    """テスト実行"""
    
    print("=" * 60)
    print("週間収支管理モジュール - テスト実行")
    print("=" * 60)
    
    # テストケース1: 週間収支の初期化
    print("\n【テスト1】週間収支の初期化")
    tracker = WeeklyTracker()
    tracker.initialize_week(30000, datetime(2026, 2, 3))  # 2026/02/03（月）
    
    # テストケース2: 日次記録の追加
    print("\n【テスト2】日次記録の追加")
    tracker.add_daily_record('2026-02-03', 9600, 0, 4)  # 月曜: 投資¥9,600、払戻¥0
    tracker.add_daily_record('2026-02-04', 0, 0, 0)      # 火曜: 休催
    tracker.add_daily_record('2026-02-05', 9600, 5400, 4)  # 水曜: 投資¥9,600、払戻¥5,400
    
    # テストケース3: アラートチェック
    print("\n【テスト3】アラートチェック")
    alert_level, message = tracker.check_alert()
    print(f"アラートレベル: {alert_level}")
    if message:
        print(message)
    
    investment_ratio = tracker.get_investment_ratio()
    print(f"投資比率: {investment_ratio * 100:.0f}%")
    
    # テストケース4: 週間統計の出力
    print("\n【テスト4】週間統計の出力")
    tracker.print_summary()
    
    # テストケース5: 予算超過シミュレーション
    print("\n【テスト5】予算超過シミュレーション")
    tracker.add_daily_record('2026-02-06', 9600, 0, 4)  # 木曜
    tracker.add_daily_record('2026-02-07', 9600, 0, 4)  # 金曜
    
    alert_level, message = tracker.check_alert()
    print(f"アラートレベル: {alert_level}")
    if message:
        print(message)
    
    tracker.print_summary()
    
    print("\n" + "=" * 60)
    print("テスト完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
