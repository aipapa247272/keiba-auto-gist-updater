#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新予想ロジック: スコア計算スクリプト
作成日: 2026/02/16
更新日: 2026/02/26 Phase2バグ修正
目的: 実データに基づいた入賞要因を数値化し、予想精度を向上させる

【Phase1変更点】
  馬体重増減: 0.30 → 0.10 (-20%) ※過剰評価を是正
  前走人気:   0.25 → 0.30 (+5%)  ※人気は信頼度高
  経験値:     0.15 → 0.05 (-10%) ※経験値より実力重視
  騎手厩舎:   0.15 → 0.25 (+10%) ※騎手・厩舎の影響大
  距離馬場適性:0.10 → 0.20 (+10%) ※適性は重要指標
  脚質:       0.05 → 0.10 (+5%)  ※展開影響を強化

【Phase2バグ修正】
  ① 当日人気を優先使用: horse["人気"] を前走人気より優先（fetch_shutuba.py が当日人気を格納済み）
  ② 騎手厩舎スコア正規化修正: C_騎手厩舎の最大値は20点なので *10 → *5 に変更
     （旧コードでは *10 していたためほぼ全馬100点になりスコア差がつかなかった）
"""

import json
import sys
from typing import Dict, Any

def calculate_weight_change_score(weight_change: float) -> int:
    """
    馬体重増減スコア計算（10%の重み ← Phase1: 30%→10%）
    入賞馬は平均-0.47kg、不入賞馬は+1.66kg
    """
    if weight_change is None:
        return 50  # データなしはニュートラル
    
    if weight_change <= -10:
        return 100
    elif -10 < weight_change <= -5:
        return 80
    elif -5 < weight_change <= 0:
        return 60
    elif 0 < weight_change <= 5:
        return 40
    else:
        return 20

def calculate_popularity_score(last_popularity: str) -> int:
    """
    前走人気スコア計算（30%の重み ← Phase1: 25%→30%）
    入賞馬の40%が前走1-2番人気
    """
    if not last_popularity:
        return 50  # データなしはニュートラル
    
    try:
        pop = int(last_popularity)
        if pop == 1:
            return 100
        elif pop == 2:
            return 90
        elif 3 <= pop <= 5:
            return 70
        elif 6 <= pop <= 10:
            return 50
        else:
            return 30
    except (ValueError, TypeError):
        return 50

def calculate_experience_score(past_races_count: int) -> int:
    """
    経験値スコア計算（5%の重み ← Phase1: 15%→5%）
    入賞馬は平均3.6レース、不入賞馬は2.65レース
    """
    if past_races_count >= 5:
        return 100
    elif past_races_count >= 3:
        return 80
    elif past_races_count == 2:
        return 60
    elif past_races_count == 1:
        return 40
    else:
        return 20

def calculate_jockey_stable_score(des_jockey_stable: float) -> int:
    """
    騎手厩舎スコア計算（25%の重み ← Phase1: 15%→25%）
    旧DESスコアを正規化（0-20点 → 0-100点）
    ※ Phase2修正: C_騎手厩舎の実際の最大値は20点（騎手10点+厩舎10点）なので *5 が正しい
       旧コードは *10 していたためほぼ全馬100点に張り付いてスコア差がつかなかった
    """
    if des_jockey_stable is None:
        return 50
    
    # 0-20点を0-100点に変換（Phase2修正: *10 → *5）
    normalized = min(100, des_jockey_stable * 5)
    return int(normalized)

def calculate_aptitude_score(des_aptitude: float) -> int:
    """
    距離馬場適性スコア計算（20%の重み ← Phase1: 10%→20%）
    旧DESスコアを正規化（0-25点 → 0-100点）
    """
    if des_aptitude is None:
        return 50
    
    # 0-25点を0-100点に変換
    normalized = min(100, des_aptitude * 4)
    return int(normalized)

def calculate_leg_type_score(leg_type: str) -> int:
    """
    脚質スコア計算（10%の重み ← Phase1: 5%→10%）
    逃げ33.3% > 先行26.7% > 差し40.0%（逃げ・先行が有利）
    """
    leg_scores = {
        "逃げ": 100,
        "先行": 85,
        "差し": 70,
        "追込": 50,
    }
    return leg_scores.get(leg_type, 60)  # 不明は60点

def calculate_new_score(horse: Dict[str, Any]) -> tuple[float, Dict[str, int]]:
    """
    新スコア計算のメイン関数
    
    Args:
        horse: 馬のデータ（DESスコア、past_races、推定脚質などを含む）
    
    Returns:
        (新スコア, スコア内訳の辞書)
    """
    # 前走データから馬体重増減を取得
    past_races = horse.get("past_races", [])
    weight_change = None
    last_popularity = None
    
    if past_races:
        last_race = past_races[0]
        weight_str = last_race.get("馬体重", "")
        
        # 馬体重増減の抽出（例: "478(+6)" → +6）
        if weight_str and "(" in weight_str:
            try:
                change_str = weight_str.split("(")[1].replace(")", "")
                weight_change = int(change_str)
            except (IndexError, ValueError):
                pass
        
        # 人気の取得（Phase2修正: 当日人気を優先、なければ前走人気を使用）
        # fetch_shutuba.py が horse["人気"] に当日の人気を格納しているため優先使用
        last_popularity = horse.get("人気") or last_race.get("人気")
    
    # 各要素のスコア計算
    score_components = {
        "馬体重増減": calculate_weight_change_score(weight_change),
        "当日人気": calculate_popularity_score(last_popularity),  # Phase2修正: 当日人気優先
        "経験値": calculate_experience_score(len(past_races)),
        "騎手厩舎": calculate_jockey_stable_score(
            horse.get("des_score", {}).get("C_騎手厩舎", 0)
        ),
        "距離馬場適性": calculate_aptitude_score(
            horse.get("des_score", {}).get("B_距離馬場適性", 0)
        ),
        "脚質": calculate_leg_type_score(horse.get("推定脚質", "")),
    }
    
    # ===== Phase1重み =====
    # 前走人気:    0.30 (+5%)
    # 騎手厩舎:    0.25 (+10%)
    # 距離馬場適性: 0.20 (+10%)
    # 脚質:        0.10 (+5%)
    # 馬体重増減:  0.10 (-20%)
    # 経験値:      0.05 (-10%)
    # 合計:        1.00
    total_score = (
        score_components["当日人気"]     * 0.30 +  # Phase2修正: 当日人気優先
        score_components["騎手厩舎"]     * 0.25 +
        score_components["距離馬場適性"] * 0.20 +
        score_components["脚質"]         * 0.10 +
        score_components["馬体重増減"]   * 0.10 +
        score_components["経験値"]       * 0.05
    )
    
    return round(total_score, 2), score_components

def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python calculate_new_score.py <race_data_ymd>.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    try:
        # データ読み込み
        with open(input_file, "r", encoding="utf-8") as f:
            race_data = json.load(f)
        
        print(f"[INFO] {input_file} を読み込みました")
        
        # 各レースの各馬に新スコアを計算
        total_horses = 0
        for race in race_data.get("races", []):
            for horse in race.get("horses", []):
                new_score, score_components = calculate_new_score(horse)
                
                # 新スコアを追加
                horse["新スコア"] = new_score
                horse["新スコア_内訳"] = score_components
                
                total_horses += 1
        
        # 結果を上書き保存
        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(race_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SUCCESS] 新スコアを計算しました: {total_horses}頭")
        print(f"[SUCCESS] {input_file} に保存しました")
        
    except FileNotFoundError:
        print(f"[ERROR] ファイルが見つかりません: {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析エラー: {e}\"")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 予期しないエラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
