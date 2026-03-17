# ロジックバージョン: v14.0 (2026-03-11: 軸2頭化+相手ボックス追加)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新予想ロジック対応: レース選定スクリプト
精度改善v3 [2026-03-06]: max_combos 15→20点、穴馬人気6→5人気、col2拡張
修正日: 2026/03/02
変更点 (v12 - 合成オッズ・断層・資金管理対応):
- オッズ断層分析関数を追加 (analyze_odds_layers)
- 危険な1番人気フィルターを追加 (is_dangerous_favorite)
- 役割ベース三連複フォーメーション再設計 (軸×対抗×穴)
- 合成オッズ計算・スキップフィルター (3倍未満除外)
- 資金管理ルール (1000円固定・損切りフラグ)
- 旧ロジックデータを比較用に保持
"""

import json
import sys
import re
import os
from datetime import datetime, timezone, timedelta
from math import comb
from itertools import combinations as iter_combinations

# =============================================
# 資金管理定数 (Fund Management Constants)
# =============================================
FUND_MANAGEMENT = {
    "base_stake_trifecta": 100,    # 三連複: 1点あたり賭け金(100円×点数)
    "base_stake_wide": 500,         # ワイド: 1点あたり
    "base_stake_place": 300,        # 複勝: 1点あたり
    "max_combos_trifecta": 20,      # 三連複: 最大点数 [精度改善v3: 15→20点 2026-03]
    "max_combos_wide": 2,           # ワイド: 最大点数
    "max_combos_place": 3,          # 複勝: 最大点数
    "min_synthetic_odds": 3.5,      # 合成オッズ最低ライン [精度改善v2: 4.0→3.5倍 2026-03]
    "odds_boost_threshold_5": 5.0,  # 合成オッズ5倍以上 → 賭け金2倍(100円→200円) [案B: 100/200の2段階]
    "min_wide_odds": 5.0,           # ワイドオッズ最低ライン
    "min_place_odds": 2.0,          # 複勝オッズ最低ライン
    "place_odds_spread_min": 2.0,   # 複勝オッズ幅の最低値
    "daily_loss_limit": 10000,      # 日次損切りライン
    "weekly_loss_limit": 30000,     # 週次損切りライン
    "consecutive_loss_stop": 3,     # 連敗停止回数
    "odds_layer_threshold": 2.0,    # 断層判定: 変化率がこの値以上
    "max_popularity_place": 5,      # 複勝対象: 最大人気順位
    "hole_horse_min_popularity": 5,  # 穴馬人気閾値 [精度改善v3: 6→5人気 2026-03]
    # --- Phase1: 2段階表示 ---
    "reference_min_odds": 2.0,   # 参考予測の合成オッズ下限（2.0倍以上）
    "reference_max_odds": 3.5,   # 参考予測の合成オッズ上限（推奨閾値未満）
    "reference_stake_ratio": 1.0 # 参考予測の賭け金倍率（100円単位統一 v14.4）
}

# ===================================================
# 低ROI競馬場フィルタ設定 (v13.1 2026-03-06追加)
# ROI実績データに基づく自動除外設定
# ===================================================
LOW_ROI_VENUES = {
    # JRA中央競馬場 - 実績ROIが低い場を除外
    "東京": {"roi_pct": 0.0,  "exclude_level": "select"},  # 推奨から除外
    "中山": {"roi_pct": 8.8,  "exclude_level": "select"},  # 推奨から除外
    # "阪神": {"roi_pct": 45.0, "exclude_level": "none"},  # 除外しない
    # "京都": {"roi_pct": 52.0, "exclude_level": "none"},  # 除外しない
}
# exclude_level:
#   "all"    => 推奨(⭐⭐⭐)と参考(⭐⭐)両方から除外
#   "select" => 推奨(⭐⭐⭐)のみ除外、参考(⭐⭐)は表示
#   "none"   => 除外しない



# =============================================
# コース特徴テーブル (Course Feature Table)
# NAR競馬場の小回り・直線距離・脚質有利不利
# =============================================
COURSE_FEATURES = {
    # NAR 地方競馬場
    "姫路":   {"type": "小回り", "straight": 200,  "front_advantage": True,  "note": "右回り・タイト・差し届きにくい"},
    "笠松":   {"type": "超小回り","straight": 195, "front_advantage": True,  "note": "左回り・超タイト・逃げ先行圧倒有利"},
    "川崎":   {"type": "小回り", "straight": 300,  "front_advantage": True,  "note": "左回り・逃げ先行有利"},
    "大井":   {"type": "標準",   "straight": 386,  "front_advantage": False, "note": "左回り・直線長め・差し届く"},
    "船橋":   {"type": "小回り", "straight": 308,  "front_advantage": True,  "note": "左回り・先行有利"},
    "浦和":   {"type": "超小回り","straight": 220, "front_advantage": True,  "note": "左回り・直線短い・逃げ先行有利"},
    "園田":   {"type": "超小回り","straight": 213, "front_advantage": True,  "note": "右回り・超タイト・逃げ圧倒有利"},
    "名古屋": {"type": "小回り", "straight": 240,  "front_advantage": True,  "note": "左回り・先行有利"},
    "金沢":   {"type": "小回り", "straight": 236,  "front_advantage": True,  "note": "右回り・先行有利"},
    "高知":   {"type": "超小回り","straight": 200, "front_advantage": True,  "note": "右回り・逃げ有利"},
    "佐賀":   {"type": "小回り", "straight": 200,  "front_advantage": True,  "note": "右回り・先行有利"},
    "盛岡":   {"type": "標準",   "straight": 300,  "front_advantage": False, "note": "左回り・芝あり・差し届く"},
    "水沢":   {"type": "超小回り","straight": 197, "front_advantage": True,  "note": "右回り・逃げ先行有利"},
    "門別":   {"type": "標準",   "straight": 330,  "front_advantage": False, "note": "左回り・差し可能"},
    # JRA (参考)
    "東京":   {"type": "大回り", "straight": 526,  "front_advantage": False, "note": "左回り・長直線・差し追込有利"},
    "阪神":   {"type": "標準",   "straight": 359,  "front_advantage": False, "note": "右回り・差し可能"},
    "中山":   {"type": "小回り", "straight": 310,  "front_advantage": True,  "note": "右回り・先行有利"},
    "京都":   {"type": "標準",   "straight": 404,  "front_advantage": False, "note": "右回り・差し届く"},
    "小倉":   {"type": "小回り", "straight": 293,  "front_advantage": True,  "note": "右回り・先行有利"},
    "新潟":   {"type": "大回り", "straight": 658,  "front_advantage": False, "note": "左回り・最長直線・差し追込有利"},
    "中京":   {"type": "標準",   "straight": 410,  "front_advantage": False, "note": "左回り・差し可能"},
    "函館":   {"type": "小回り", "straight": 262,  "front_advantage": True,  "note": "右回り・先行有利"},
    "札幌":   {"type": "小回り", "straight": 264,  "front_advantage": True,  "note": "右回り・先行有利"},
    "福島":   {"type": "小回り", "straight": 292,  "front_advantage": True,  "note": "右回り・先行有利"},
}

def get_course_advantage(venue: str, leg_type: str) -> int:
    """
    競馬場×脚質の有利不利スコア補正
    補正値は「傾向のヒント」であり、実力差を逆転させないよう小幅に設定。
    超小回り: 逃げ+8, 先行+4, 差し-4, 追込-8
    小回り:   逃げ+6, 先行+3, 差し-3, 追込-6
    大回り:   逃げ-3, 先行+0, 差し+3, 追込+5
    標準:     補正なし (±0)
    """
    feature = COURSE_FEATURES.get(venue, {"type": "標準", "front_advantage": False})
    course_type = feature["type"]
    
    if course_type == "超小回り":
        adjustments = {"逃げ": 8, "先行": 4, "差し": -4, "追込": -8}
    elif course_type == "小回り":
        adjustments = {"逃げ": 6, "先行": 3, "差し": -3, "追込": -6}
    elif course_type == "大回り":
        adjustments = {"逃げ": -3, "先行": 0, "差し": 3, "追込": 5}
    else:  # 標準
        adjustments = {"逃げ": 0, "先行": 0, "差し": 0, "追込": 0}
    
    return adjustments.get(leg_type, 0)


# =============================================
# 斤量変化・騎手乗り替わりボーナス
# =============================================
def calculate_jockey_weight_bonus(horse):
    """
    斤量変化と騎手乗り替わりによるボーナス/ペナルティ

    斤量変化:
      -2kg以上の減量  : +10
      -1kgの減量      : +5
      +1kgの増量      : -5
      +2kg以上の増量  : -10

    騎手乗り替わり:
      替わりあり (4番人気以下の穴馬候補) : +5
      替わりあり (一般)              : +2

    Returns:
        bonus: int  (補正後スコアに加算)
        detail: dict  (内訳)
    """
    bonus = 0
    detail = {}
    past_races = horse.get('past_races', [])

    # --- 斤量変化 ---
    current_weight = horse.get('斤量')
    prev_weight = past_races[0].get('斤量') if past_races else None
    if current_weight and prev_weight:
        try:
            diff = float(current_weight) - float(prev_weight)
            detail['斤量差'] = diff
            if diff <= -2:
                bonus += 10
                detail['斤量ボーナス'] = '+10(大幅減量)'
            elif diff <= -1:
                bonus += 5
                detail['斤量ボーナス'] = '+5(減量)'
            elif diff >= 2:
                bonus -= 10
                detail['斤量ボーナス'] = '-10(大幅増量)'
            elif diff >= 1:
                bonus -= 5
                detail['斤量ボーナス'] = '-5(増量)'
        except (ValueError, TypeError):
            pass

    # --- 騎手乗り替わり ---
    current_jockey = horse.get('騎手') or horse.get('jockey')
    prev_jockey = past_races[0].get('騎手') if past_races else None
    if current_jockey and prev_jockey and current_jockey != prev_jockey:
        pop = horse.get('人気') or horse.get('popularity')
        if pop and int(pop) >= 4:  # 人汱4番以下の穴馬候補は騎手替わりが大きなプラス
            bonus += 5
            detail['騎手替わり'] = f'+5(穴馬騎手乗り替わり: {prev_jockey}→{current_jockey})'
        else:
            bonus += 2
            detail['騎手替わり'] = f'+2(騎手乗り替わり: {prev_jockey}→{current_jockey})'

    return bonus, detail


# =============================================
# オッズ断層分析 (Odds Layer Analysis)
# =============================================
def analyze_odds_layers(horses):
    """
    オッズ断層を検出する。
    隣接する人気馬のオッズ変化率が threshold 以上の箇所を断層とする。
    
    Returns:
        layers: [{'position': i, 'change_rate': r, 'boundary_odds': prev_odds}, ...]
        sorted_horses: 人気順にソートされた馬リスト (断層役割付き)
        has_odds_data: 実際のオッズデータが使用できたか
    """
    threshold = FUND_MANAGEMENT["odds_layer_threshold"]
    
    # 単勝オッズ or 人気 フィールドの存在確認
    odds_field = None
    for candidate in ['単勝オッズ', 'win_odds', 'odds']:
        if any(h.get(candidate) for h in horses):
            odds_field = candidate
            break
    
    pop_field = None
    for candidate in ['人気', 'popularity', '人気順']:
        if any(h.get(candidate) for h in horses):
            pop_field = candidate
            break
    
    has_odds_data = (odds_field is not None) and (pop_field is not None)
    
    if has_odds_data:
        # 実際のオッズデータで断層検出
        sorted_horses = sorted(
            [h for h in horses if h.get(pop_field) and h.get(odds_field)],
            key=lambda h: int(h.get(pop_field, 99))
        )
        
        layers = []
        for i in range(1, len(sorted_horses)):
            prev_odds = float(sorted_horses[i-1].get(odds_field, 1))
            curr_odds = float(sorted_horses[i].get(odds_field, 1))
            if prev_odds > 0:
                change_rate = curr_odds / prev_odds
                if change_rate >= threshold:
                    layers.append({
                        'position': i,
                        'change_rate': round(change_rate, 2),
                        'boundary_odds': prev_odds,
                        'from_horse': sorted_horses[i-1].get('馬名', ''),
                        'to_horse': sorted_horses[i].get('馬名', '')
                    })
    elif pop_field:
        # ========== 人気フィールドあり、実オッズなし ==========
        # 人気順にソートして固定ティアで断層を定義する
        # 統計的知見: 1-3番人気が3着以内に入る確率約93%
        # 断層定義:
        #   層１: 人気3番 → 4番 の間 (本命グループ vs その他)
        #   層２: 人気5番 → 6番 の間 (対抗馬 vs 穴馬)
        sorted_horses = sorted(
            [h for h in horses if h.get(pop_field)],
            key=lambda h: int(h.get(pop_field, 99))
        )
        # 推定オッズを一時付与
        POP_TO_ODDS = {
            1: 4.0, 2: 7.0, 3: 11.0, 4: 16.0, 5: 24.0,
            6: 35.0, 7: 52.0, 8: 75.0, 9: 100.0, 10: 140.0,
        }
        for h in sorted_horses:
            try:
                pop_rank = int(h.get(pop_field, 99))
                h['_est_odds'] = POP_TO_ODDS.get(pop_rank, min(150.0, pop_rank * 12.0))
            except (ValueError, TypeError):
                h['_est_odds'] = 50.0

        # 固定位置に断層を定義
        layers = []
        pop_sorted_ranks = [int(h.get(pop_field, 99)) for h in sorted_horses]

        # 断層１: 人気3から4の間に定義
        if len(sorted_horses) > 3 and 3 in pop_sorted_ranks and 4 in pop_sorted_ranks:
            idx_4 = pop_sorted_ranks.index(4)
            if idx_4 > 0:
                layers.append({
                    'position': idx_4,
                    'change_rate': round(POP_TO_ODDS.get(4, 14) / POP_TO_ODDS.get(3, 9), 2),
                    'boundary_odds': POP_TO_ODDS.get(3, 9),
                    'from_horse': sorted_horses[idx_4 - 1].get('馬名', ''),
                    'to_horse': sorted_horses[idx_4].get('馬名', ''),
                    'estimated': True,
                    'method': 'popularity_tier'
                })

        # 断層２: 人気5から6の間に定義
        if len(sorted_horses) > 5 and 5 in pop_sorted_ranks and 6 in pop_sorted_ranks:
            idx_6 = pop_sorted_ranks.index(6)
            if idx_6 > 0:
                layers.append({
                    'position': idx_6,
                    'change_rate': round(POP_TO_ODDS.get(6, 30) / POP_TO_ODDS.get(5, 20), 2),
                    'boundary_odds': POP_TO_ODDS.get(5, 20),
                    'from_horse': sorted_horses[idx_6 - 1].get('馬名', ''),
                    'to_horse': sorted_horses[idx_6].get('馬名', ''),
                    'estimated': True,
                    'method': 'popularity_tier'
                })

        # 断層が1つも検出できなかった場合: スコア差で補完
        if not layers:
            score_sorted = sorted(horses, key=lambda h: h.get('新スコア', 0), reverse=True)
            scores = [h.get('新スコア', 0) for h in score_sorted]
            score_range = max(scores) - min(scores) if scores else 0
            relative_threshold = score_range * 0.3
            for i in range(1, len(score_sorted)):
                s_prev = score_sorted[i - 1].get('新スコア', 0)
                s_curr = score_sorted[i].get('新スコア', 0)
                if (s_prev - s_curr) >= max(relative_threshold, 10):
                    layers.append({
                        'position': i,
                        'change_rate': round(s_prev / max(s_curr, 1), 2),
                        'boundary_odds': None,
                        'from_horse': score_sorted[i - 1].get('馬名', ''),
                        'to_horse': score_sorted[i].get('馬名', ''),
                        'estimated': True,
                        'method': 'score_diff'
                    })
                    if len(layers) >= 2:
                        break
            if layers:
                sorted_horses = score_sorted  # スコアソートに切り替え
    else:
        # ========== 人気・オッズどちらもない場合 ==========
        sorted_horses = sorted(horses, key=lambda h: h.get('新スコア', 0), reverse=True)
        scores = [h.get('新スコア', 0) for h in sorted_horses]
        score_range = max(scores) - min(scores) if scores else 0
        relative_threshold = score_range * 0.3
        layers = []
        for i in range(1, len(sorted_horses)):
            s_prev = sorted_horses[i - 1].get('新スコア', 0)
            s_curr = sorted_horses[i].get('新スコア', 0)
            if (s_prev - s_curr) >= max(relative_threshold, 10):
                layers.append({
                    'position': i,
                    'change_rate': round(s_prev / max(s_curr, 1), 2),
                    'boundary_odds': None,
                    'from_horse': sorted_horses[i - 1].get('馬名', ''),
                    'to_horse': sorted_horses[i].get('馬名', ''),
                    'estimated': True,
                    'method': 'score_diff'
                })
                if len(layers) >= 2:
                    break

    return layers, sorted_horses, has_odds_data


def assign_roles_by_layers(sorted_horses, layers):
    """
    断層に基づいて各馬に役割を割り当てる。
    
    役割:
      軸馬 (断層1より上): 1着候補
      対抗馬 (断層1〜断層2の間): 相手候補
      穴馬 (断層2より下): 高配当候補
      未分類 (断層なし): フラット混戦
    
    Returns:
        horses_with_roles: 役割フィールド付き馬リスト
        race_type: 'double_layer' | 'single_layer' | 'flat' | 'no_data'
    """
    horses_with_roles = [h.copy() for h in sorted_horses]
    
    if not layers:
        # フラット混戦 - 全馬に未分類
        for h in horses_with_roles:
            h['断層役割'] = '未分類'
            h['断層役割_en'] = 'flat'
        return horses_with_roles, 'flat'
    
    if len(layers) >= 2:
        race_type = 'double_layer'
        l1_pos = layers[0]['position']
        l2_pos = layers[1]['position']
        for i, h in enumerate(horses_with_roles):
            if i < l1_pos:
                h['断層役割'] = '軸馬候補'
                h['断層役割_en'] = 'axis'
            elif i < l2_pos:
                h['断層役割'] = '対抗馬候補'
                h['断層役割_en'] = 'rival'
            else:
                h['断層役割'] = '穴馬候補'
                h['断層役割_en'] = 'hole'
    else:
        race_type = 'single_layer'
        l1_pos = layers[0]['position']
        for i, h in enumerate(horses_with_roles):
            if i < l1_pos:
                h['断層役割'] = '軸馬候補'
                h['断層役割_en'] = 'axis'
            else:
                h['断層役割'] = '穴馬候補'
                h['断層役割_en'] = 'hole'
    
    return horses_with_roles, race_type


# =============================================
# 危険な1番人気フィルター
# =============================================
def is_dangerous_favorite(horse, race_distance=None):
    """
    危険な1番人気を判定する。
    
    4つの危険条件:
    1. 人気1位 かつ 単勝オッズ >= 4.0 (混戦オッズ)
    2. 前走人気 >= 6 かつ 前走着順 == 2 (まぐれ人気)
    3. G1叩き台出走 (race_nameにG1・テスト記載)
    4. 前走距離 < 今走距離 (距離延長)
    
    Returns:
        is_dangerous: bool
        danger_reasons: list of str
    """
    danger_reasons = []
    
    # 人気フィールドを取得
    pop = horse.get('人気') or horse.get('popularity')
    win_odds = horse.get('単勝オッズ') or horse.get('win_odds')
    
    # 条件①: 混戦オッズ (人気1位なのにオッズが高い)
    if pop and int(pop) == 1 and win_odds:
        if float(win_odds) >= 4.0:
            danger_reasons.append(f"混戦オッズ({win_odds}倍)")
    
    # 条件②: まぐれ人気 (前走低人気で2着)
    prev_pop = horse.get('前走人気') or horse.get('prev_popularity')
    prev_rank = horse.get('前走着順') or horse.get('prev_rank')
    if prev_pop and prev_rank:
        try:
            if int(prev_pop) >= 6 and int(prev_rank) == 2:
                danger_reasons.append(f"まぐれ人気(前走{prev_pop}番人気2着)")
        except (ValueError, TypeError):
            pass
    
    # 条件③: G1叩き台 (レース名から推測)
    race_goal = horse.get('出走目的', '')
    if 'G1' in str(race_goal) or '叩き台' in str(race_goal) or 'テスト' in str(race_goal):
        danger_reasons.append("G1叩き台出走")
    
    # 条件④: 距離延長
    prev_dist = horse.get('前走距離') or horse.get('prev_distance')
    if prev_dist and race_distance:
        try:
            if int(prev_dist) < int(race_distance):
                danger_reasons.append(f"距離延長({prev_dist}m→{race_distance}m)")
        except (ValueError, TypeError):
            pass
    
    return len(danger_reasons) > 0, danger_reasons


# =============================================
# 合成オッズ計算
# =============================================
def calculate_synthetic_odds(horse_list, odds_field='単勝オッズ'):
    """
    合成オッズを計算する。
    formula: 1 / Σ(1/odds_i)
    
    オッズデータがない場合はスコアから推定。
    
    Returns:
        synthetic_odds: float
        method: 'actual' | 'estimated'
    """
    odds_values = []
    for h in horse_list:
        odds = h.get(odds_field) or h.get('win_odds') or h.get('odds')
        if odds:
            try:
                odds_values.append(float(odds))
            except (ValueError, TypeError):
                pass
    
    if odds_values and len(odds_values) == len(horse_list):
        # 実際のオッズを使用
        denominator = sum(1.0 / o for o in odds_values)
        if denominator > 0:
            return round(1.0 / denominator, 2), 'actual'

    # フォールバック1: _est_odds (人気ティア推定値) を優先使用
    est_odds_values = [h.get('_est_odds') for h in horse_list if h.get('_est_odds')]
    if est_odds_values and len(est_odds_values) == len(horse_list):
        denominator = sum(1.0 / o for o in est_odds_values if o > 0)
        if denominator > 0:
            return round(1.0 / denominator, 2), 'popularity_estimated'
    
    # フォールバック: DESスコアから推定
    # スコアが低い = オッズが高い という逆関係を利用
    # 推定オッズ = (100 / score) * 3 (概算)
    scores = [h.get('新スコア', 50) for h in horse_list]
    if scores:
        estimated_odds = [(100.0 / max(s, 1)) * 3 for s in scores]
        denominator = sum(1.0 / o for o in estimated_odds if o > 0)
        if denominator > 0:
            return round(1.0 / denominator, 2), 'estimated'
    
    return 1.0, 'estimated'


# =============================================
# 複勝候補チェック
# =============================================
def check_place_candidates(horses_with_roles, race_distance=None):
    """
    複勝購入候補を選定する。
    
    ルール:
    - 8頭以上のレース（select_races側でチェック済み）
    - 5番人気以内
    - 複勝オッズ 最低2.0倍以上
    - オッズ幅が2.0倍以上
    - 1〜3点
    """
    candidates = []
    
    for h in horses_with_roles:
        pop = h.get('人気') or h.get('popularity')
        place_odds_min = h.get('複勝オッズ_min') or h.get('place_odds_min') or h.get('複勝オッズ')
        place_odds_max = h.get('複勝オッズ_max') or h.get('place_odds_max')
        
        # 人気チェック
        if pop:
            try:
                if int(pop) > FUND_MANAGEMENT["max_popularity_place"]:
                    continue
            except (ValueError, TypeError):
                pass
        
        # 複勝オッズチェック
        if place_odds_min:
            try:
                odds_min = float(place_odds_min)
                if odds_min < FUND_MANAGEMENT["min_place_odds"]:
                    continue
                
                # オッズ幅チェック
                if place_odds_max:
                    odds_max = float(place_odds_max)
                    if (odds_max - odds_min) < FUND_MANAGEMENT["place_odds_spread_min"]:
                        continue
                
                candidates.append({
                    'horse': h,
                    'place_odds_min': odds_min,
                    'place_odds_max': float(place_odds_max) if place_odds_max else odds_min,
                    'stake': FUND_MANAGEMENT["base_stake_place"]
                })
            except (ValueError, TypeError):
                pass
    
    return candidates[:FUND_MANAGEMENT["max_combos_place"]]


# =============================================
# ワイド候補チェック
# =============================================
def check_wide_candidates(horses_with_roles):
    """
    ワイド購入候補を選定する。
    
    ルール:
    - 軸馬(断層上) × 穴馬(断層下)
    - ワイドオッズ 5.0倍以上
    - 1〜2点
    """
    axis_horses = [h for h in horses_with_roles
                   if h.get('断層役割_en') in ('axis',)]
    hole_horses = [h for h in horses_with_roles
                   if h.get('断層役割_en') in ('hole',)]
    
    if not axis_horses or not hole_horses:
        return []
    
    wide_bets = []
    for a in axis_horses[:2]:
        for ho in hole_horses[:3]:
            # ワイドオッズが取得できる場合はチェック
            wide_odds = None
            # wide_odds フィールドが存在する場合
            for key in ['ワイドオッズ', 'wide_odds']:
                v = ho.get(key) or a.get(key)
                if v:
                    wide_odds = float(v)
                    break
            
            if wide_odds is not None and wide_odds < FUND_MANAGEMENT["min_wide_odds"]:
                continue
            
            wide_bets.append({
                '軸': {'馬番': a.get('馬番'), '馬名': a.get('馬名'),
                       'スコア': a.get('新スコア', 0), '役割': '軸馬候補'},
                '穴': {'馬番': ho.get('馬番'), '馬名': ho.get('馬名'),
                       'スコア': ho.get('新スコア', 0), '役割': '穴馬候補'},
                'ワイドオッズ': wide_odds,
                '買い目': f"{a.get('馬番')}-{ho.get('馬番')}",
                '投資': FUND_MANAGEMENT["base_stake_wide"]
            })
    
    return wide_bets[:FUND_MANAGEMENT["max_combos_wide"]]


# =============================================
# 予想根拠生成
# =============================================
def generate_reason(horse_data):
    """予想根拠を生成"""
    reasons = []
    breakdown = horse_data.get('新スコア_内訳', {})
    
    if breakdown.get('当日人気', breakdown.get('前走人気', 0)) >= 90:
        reasons.append("前走1-2位人気")
    elif breakdown.get('当日人気', breakdown.get('前走人気', 0)) >= 70:
        reasons.append("前走3-5位人気")
    
    if breakdown.get('馬体重増減', 0) >= 80:
        reasons.append("体重減で好調")
    elif breakdown.get('馬体重増減', 0) <= 30:
        reasons.append("体重増で不安")
    
    if breakdown.get('経験値', 0) >= 80:
        reasons.append("実績豊富")
    
    if breakdown.get('騎手厩舎', 0) >= 90:
        reasons.append("好騎手")
    
    if breakdown.get('距離馬場適性', 0) >= 90:
        reasons.append("適性抜群")
    
    if breakdown.get('脚質', 0) >= 90:
        reasons.append("展開有利")
    
    # 断層役割を追記
    role = horse_data.get('断層役割', '')
    if role and role != '未分類':
        reasons.append(role)
    
    # 危険フラグ
    if horse_data.get('危険フラグ'):
        reasons.append("⚠️危険1番人気")
    
    if not reasons:
        score = horse_data.get('新スコア', 0)
        reasons.append("総合力高い" if score >= 80 else "堅実な評価" if score >= 60 else "穴候補")
    
    return "、".join(reasons)


# =============================================
# 波乱度計算
# =============================================
def calculate_turbulence(race):
    """波乱度を計算"""
    horses = race.get('horses', [])
    if not horses:
        return "中"
    
    scores = [h.get('新スコア', 0) for h in horses if h.get('新スコア')]
    if not scores or len(scores) < 3:
        return "中"
    
    scores.sort(reverse=True)
    top_3_avg = sum(scores[:3]) / 3
    score_diff = scores[0] - scores[2]
    
    if top_3_avg >= 70 and score_diff >= 10:
        return "低"
    elif top_3_avg >= 55 or score_diff >= 5:
        return "中"
    else:
        return "高"




# =============================================
# 波乱度スコア計算（アプローチA: 穴ボックス発動判定用）
# =============================================
def _calculate_upset_score(race, axis_candidates, hole_candidates):
    """
    波乱度スコア(0〜100+)を算出し、穴馬ボックス発動の判定に使用する。
    スコア >= 60 で穴ボックス自動追加が発動。

    採点基準:
      +30: calculate_turbulence が "高"
      +10: calculate_turbulence が "中"
      +20: ダートかつ距離 >= 2000m
      +25: 軸馬の最高補正後スコア < 55
      +25: 穴馬の最高補正後スコア > 軸馬の最高補正後スコア
    """
    score = 0
    reasons = []

    # 1. 既存の波乱度
    turb = calculate_turbulence(race)
    if turb == "高":
        score += 30
        reasons.append("波乱度:高(+30)")
    elif turb == "中":
        score += 10
        reasons.append("波乱度:中(+10)")

    # 2. ダート長距離（2000m以上）
    race_distance = race.get('距離', 0)
    track_str = str(race.get('トラック', race.get('track', race.get('track_condition', ''))))
    try:
        dist_int = int(str(race_distance).replace('m', '').strip())
    except (ValueError, TypeError):
        dist_int = 0
    if dist_int >= 2000 and 'ダート' in track_str:
        score += 20
        reasons.append(f"ダート長距離{dist_int}m(+20)")

    # 3. 軸馬の補正後スコアが低い（55未満）
    axis_scores = [h.get('補正後スコア', h.get('新スコア', 0)) for h in axis_candidates]
    axis_max = max(axis_scores) if axis_scores else 0
    if axis_max < 55:
        score += 25
        reasons.append(f"軸スコア低({axis_max:.1f}<55, +25)")

    # 4. 穴馬がスコアで軸を上回る
    hole_scores = [h.get('補正後スコア', h.get('新スコア', 0)) for h in hole_candidates]
    hole_max = max(hole_scores) if hole_scores else 0
    if hole_max > axis_max:
        score += 25
        reasons.append(f"穴馬スコア>軸({hole_max:.1f}>{axis_max:.1f}, +25)")

    return score, reasons

# =============================================
# 旧ロジックの買い目生成 (比較用)
# =============================================
def generate_old_betting_plan(horses):
    """
    旧ロジック: スコア順上位で三連複フォーメーション
    (21〜27通貫)
    比較用として保持。
    """
    sorted_horses = sorted(horses, key=lambda h: h.get('新スコア', 0), reverse=True)
    num_horses = len(horses)
    total_predicted = (num_horses // 2) + 1
    top_candidates = sorted_horses[:min(total_predicted, len(sorted_horses))]
    axis_horses = top_candidates[:3]
    opponent_horses = top_candidates[3:]
    
    num_axis = len(axis_horses)
    num_opponents = len(opponent_horses)
    old_combinations = comb(num_axis + num_opponents, 3) - comb(num_opponents, 3)
    old_investment = old_combinations * 100
    
    return {
        "旧_軸頭数": num_axis,
        "旧_相手頭数": num_opponents,
        "旧_組み合わせ数": old_combinations,
        "旧_投資額": old_investment,
        "旧_買い目タイプ": "三連複フォーメーション(スコア順)"
    }


# =============================================
# 新ロジックの買い目生成 (メイン)
# =============================================

# ============================================================
# 推定三連複オッズ計算 (スコアランクベース)
# ============================================================
# スコア順位から単勝推定オッズへの変換テーブル
_SCORE_RANK_TO_ODDS = [1.8, 3.2, 5.0, 7.5, 11.0, 16.0, 23.0, 32.0, 45.0, 65.0, 90.0]

def _estimate_single_odds(score_rank: int) -> float:
    """スコア順位(1始まり)から推定単勝オッズを返す"""
    idx = max(0, min(score_rank - 1, len(_SCORE_RANK_TO_ODDS) - 1))
    return _SCORE_RANK_TO_ODDS[idx]

def _estimate_trifecta_expected_return(ranks: list, min_return: float = 1.5) -> bool:
    """3頭のスコア順位から推定三連複期待配当倍率を計算し閾値以上かどうか返す
    min_return: 最低限の配当倍率 (1点100円投資で100×min_return円以上の期待配当)
    """
    if len(ranks) != 3:
        return True
    o1, o2, o3 = [_estimate_single_odds(r) for r in ranks]
    # 各馬が3着以内に来る確率の近似
    p1, p2, p3 = 1.0/o1, 1.0/o2, 1.0/o3
    hit_prob = p1 * p2 * p3 * 6  # 順不問なので×6
    if hit_prob <= 0:
        return True
    # JRA三連複払戻率75%で推定配当倍率を計算
    estimated_return = 0.75 / hit_prob
    return estimated_return >= min_return

def generate_betting_plan(race):
    """
    新ロジック: オッズ断層ベースの三連複フォーメーション
    
    設計:
    - 1列目 (軸): 断層上 × DESスコア上位 × 危険1番人気でない
    - 2列目 (対抗): 断層中間 (対抗馬候補)
    - 3列目 (穴): 断層下 (穴馬候補, 必ず1頭含む)
    - 合成オッズ3倍未満はスキップ
    - 最大15点、投資額1,000円固定
    
    Returns:
        betting_plan: dict
        investment: int
        skip_reason: str or None (スキップ理由)
        analysis: dict (断層分析結果)
    """
    horses = race.get('horses', [])
    race_distance = race.get('距離')
    
    # --- 旧ロジック計算 (比較用) ---
    old_logic = generate_old_betting_plan(horses)
    
    # --- 断層分析 ---
    layers, sorted_horses, has_odds_data = analyze_odds_layers(horses)
    horses_with_roles, race_type = assign_roles_by_layers(sorted_horses, layers)
    
    # 断層分析結果をまとめる
    analysis = {
        "断層数": len(layers),
        "断層詳細": layers,
        "レースタイプ": race_type,
        "実オッズ使用": has_odds_data
    }
    
    # --- フラット混戦チェック ---
    if race_type == 'flat':
        analysis["スキップ理由"] = "フラット混戦（断層なし）"
        return None, 0, "フラット混戦（断層なし）- 見送り推奨", analysis, old_logic
    
    # --- 危険な1番人気チェック ---
    for h in horses_with_roles:
        is_danger, danger_reasons = is_dangerous_favorite(h, race_distance)
        h['危険フラグ'] = is_danger
        h['危険理由'] = danger_reasons
    
    # --- 役割別に馬を分類 ---
    axis_candidates = [h for h in horses_with_roles
                       if h.get('断層役割_en') == 'axis'
                       and not h.get('危険フラグ')]
    rival_candidates = [h for h in horses_with_roles
                        if h.get('断層役割_en') in ('rival', 'axis')]
    hole_candidates = [h for h in horses_with_roles
                       if h.get('断層役割_en') == 'hole']
    
    # フォールバック: 断層役割が不明な場合はスコア順で代替
    if not axis_candidates:
        score_sorted = sorted(horses_with_roles,
                              key=lambda h: h.get('新スコア', 0), reverse=True)
        axis_candidates = score_sorted[:2]
    if not hole_candidates:
        score_sorted = sorted(horses_with_roles,
                              key=lambda h: h.get('新スコア', 0))
        hole_candidates = score_sorted[:2]
    
    # スコア降順でソート
    axis_candidates = sorted(axis_candidates,
                             key=lambda h: h.get('新スコア', 0), reverse=True)
    rival_candidates = sorted(rival_candidates,
                              key=lambda h: h.get('新スコア', 0), reverse=True)
    hole_candidates = sorted(hole_candidates,
                             key=lambda h: h.get('新スコア', 0), reverse=True)
    
    # ============================================================
    # 三連複フォーメーション組み立て (2-4-7型)
    # ブラッシュアップ修正: 2026-03 コース特徴×脚質補正・◎○▲保証・穴馬必須
    # ============================================================
    # 競馬場のコース特徴を取得
    venue = race.get('競馬場', race.get('venue', ''))

    # 低ROI競馬場フィルタ (v13.1追加)
    venue_info = LOW_ROI_VENUES.get(venue, {})
    exclude_level = venue_info.get("exclude_level", "none")
    if exclude_level == "all":
        skip_reason = f"低ROI競馬場除外({venue} ROI:{venue_info.get('roi_pct')}%)"
        return None, 0, skip_reason, {"スキップ理由": skip_reason}, old_logic
    # "select"の場合は low_roi_venue フラグを立てる（後続でresult定義後に付与）
    _low_roi_venue_flag = (exclude_level == "select")

    
    # コース特徴×脚質スコア補正 + 斤量・騎手ボーナスを各馬に適用
    for h in horses_with_roles:
        leg_type = h.get('推定脚質', '')
        course_adj = get_course_advantage(venue, leg_type)
        jw_bonus, jw_detail = calculate_jockey_weight_bonus(h)
        h['コース補正'] = course_adj
        h['斤量騎手ボーナス'] = jw_bonus
        h['斤量騎手詳細'] = jw_detail
        # 補正後スコア（ソート用、元スコアは変えない）
        # = 新スコア + コース補正 (斤量・騎手ボーナスは穴馬専用)
        h['補正後スコア'] = h.get('新スコア', 0) + course_adj
        # 穴馬強化スコア = 補正後スコア + 斤量騎手ボーナス (穴馬候補のソート専用)
        h['穴馬専用スコア'] = h.get('補正後スコア', 0) + jw_bonus
    
    # 補正後スコアで再ソート
    axis_candidates = sorted(axis_candidates,
                             key=lambda h: h.get('補正後スコア', 0), reverse=True)
    rival_candidates = sorted(rival_candidates,
                              key=lambda h: h.get('補正後スコア', 0), reverse=True)
    hole_candidates = sorted(hole_candidates,
                             key=lambda h: h.get('補正後スコア', 0), reverse=True)
    
    # --- 1列目 (col1): 軸馬 ---
    # 基本: ◎1頭+○1頭 (2頭)
    # スコア差がAXIS_SCORE_GAP(8点)以内のときのみ3頭に拡張
    # ※3頭以上になると◎-◎-◎のガミリスクが発生するため抑制
    _ax1_score = axis_candidates[0].get('補正後スコア', 0) if len(axis_candidates) >= 1 else 0
    _ax2_score = axis_candidates[1].get('補正後スコア', 0) if len(axis_candidates) >= 2 else 0
    _ax3_score = axis_candidates[2].get('補正後スコア', 0) if len(axis_candidates) >= 3 else 0
    _AXIS_SCORE_GAP = 8  # 1位との差がこれ以下なら軸に追加
    _take3 = (len(axis_candidates) >= 3
              and _ax1_score > 0
              and (_ax1_score - _ax3_score) <= _AXIS_SCORE_GAP)
    col1 = axis_candidates[:3] if _take3 else axis_candidates[:2]
    # Bug Fix ②: 馬番をstr型に統一（int/strの型混在による重複除外漏れを防ぐ）
    col1_nums_set = {str(h.get('馬番')) for h in col1 if h.get('馬番') is not None}

    # =============================================
    # 改善①(v14.0): 軸1頭時の強制2頭化
    # 軸が1頭しかいない場合、rival/93法則候補からスコア最高の馬を軸に昇格
    # 理由: 軸1頭は的中率が著しく低い（1点でも外れると全滅）
    # =============================================
    # ★93%法則v2: 人気1-3を全員col2に強制追加（統計的に93%が3着以内）
    # 但し、危険フラグあり馬は除外、既にcol1/col2にある馬は重複しない
    # Bug Fix (v14.0): top3_pop_horsesをcol1強制2頭化より前に定義（UnboundLocalError修正）
    top3_pop_horses = sorted(
        [h for h in horses_with_roles if h.get('人気') and int(h.get('人気', 99)) <= 3
         and not h.get('危険フラグ')],
        key=lambda h: h.get('補正後スコア', 0), reverse=True
    )

    # =============================================
    # 改善①(v14.0): 軸1頭時の強制2頭化
    # =============================================
    if len(col1) < 2:
        # rival_candidates + 人気1-3からスコア最高の馬を軸に昇格
        _upgrade_pool = sorted(
            [h for h in rival_candidates + top3_pop_horses
             if str(h.get('馬番')) not in col1_nums_set and h.get('馬番')],
            key=lambda h: h.get('補正後スコア', 0), reverse=True
        )
        if not _upgrade_pool:
            _upgrade_pool = sorted(
                [h for h in horses_with_roles
                 if str(h.get('馬番')) not in col1_nums_set and h.get('馬番')],
                key=lambda h: h.get('補正後スコア', 0), reverse=True
            )
        if _upgrade_pool:
            _promoted = _upgrade_pool[0]
            col1.append(_promoted)
            col1_nums_set.add(str(_promoted.get('馬番')))
            print(f"[v14改善①] 軸1頭→2頭化: {_promoted.get('馬番')}番昇格"
                  f"(スコア:{_promoted.get('補正後スコア',0):.1f})")
    
    # --- 2列目 (col2): 4頭 = col1(2頭) + ▲2頭 ---
    col2_set = set(col1_nums_set)  # str型で統一
    col2 = list(col1)  # ◎○を先頭に含める

    # col2 に 93%法則: top3_pop_horses を強制追加
    for forced_horse in top3_pop_horses:
        # Bug Fix ②: 馬番をstr型に統一して重複チェック
        fnum = str(forced_horse.get('馬番')) if forced_horse.get('馬番') is not None else None
        if fnum and fnum not in col2_set:
            col2_set.add(fnum)
            col2.append(forced_horse)
    
    for h in rival_candidates:
        # Bug Fix ②: 馬番をstr型に統一
        key = str(h.get('馬番')) if h.get('馬番') is not None else None
        if key and key not in col2_set:
            col2_set.add(key)
            col2.append(h)
        if len(col2) >= 4:  # 合計4頭まで
            break
    # 対抗馬が足りない場合はスコア上位から補充
    if len(col2) < 3:
        for h in sorted(horses_with_roles, key=lambda h: h.get('補正後スコア', 0), reverse=True):
            key = str(h.get('馬番')) if h.get('馬番') is not None else None
            if key and key not in col2_set:
                col2_set.add(key)
                col2.append(h)
            if len(col2) >= 4:
                break
    
    # --- 3列目 (col3): 7頭 = col2(4頭) + 穴馬3頭 ---
    # col2の全馬を含め、穴馬3頭を追加（6番人気以下を必ず1頭含む）
    # Bug Fix ②: col3_setもstr型で統一
    col3_set = {str(n) for n in col2_set}
    col3 = list(col2)  # col2の全馬を先頭に含める（重要: 必ず含める）
    
    # 6番人気以下の穴馬を特定（93%法則対応）
    min_pop = FUND_MANAGEMENT["hole_horse_min_popularity"]  # 6番人気以下
    dark_horses = [h for h in hole_candidates
                   if h.get('人気', 999) >= min_pop
                   and str(h.get('馬番')) not in col3_set]
    # 穴馬は「穴馬専用スコア」(補正後スコア+斤量騎手ボーナス)で優先順位付け
    dark_horses_sorted = sorted(dark_horses,
                                key=lambda h: h.get('穴馬専用スコア', h.get('補正後スコア', 0)), reverse=True)
    
    # 6番人気以下を必ず1頭追加（なければ最低人気馬を追加）
    added_dark = False
    for h in dark_horses_sorted:
        # Bug Fix ②: 馬番をstr型に統一
        key = str(h.get('馬番')) if h.get('馬番') is not None else None
        if key and key not in col3_set:
            col3_set.add(key)
            col3.append(h)
            added_dark = True
            break
    if not added_dark:
        # 6番人気以下がいない場合は最低スコア馬を追加
        for h in sorted(horses_with_roles, key=lambda h: h.get('補正後スコア', 0)):
            key = str(h.get('馬番')) if h.get('馬番') is not None else None
            if key and key not in col3_set:
                col3_set.add(key)
                col3.append(h)
                break
    
    # 残り2頭の穴馬をスコア順で追加（合計3頭の穴馬枠）
    remaining_holes = [h for h in hole_candidates if str(h.get('馬番')) not in col3_set]
    for h in remaining_holes:
        key = str(h.get('馬番')) if h.get('馬番') is not None else None
        if key and key not in col3_set:
            col3_set.add(key)
            col3.append(h)
        if len(col3) >= 7:
            break
    # まだ足りない場合は全体スコア下位から補充
    if len(col3) < 5:
        for h in sorted(horses_with_roles, key=lambda h: h.get('補正後スコア', 0)):
            key = h.get('馬番')
            if key and key not in col3_set:
                col3_set.add(key)
                col3.append(h)
            if len(col3) >= 7:
                break
    
    # --- 2-4-7型フォーメーション 全組み合わせ生成 ---
    # ルール: n1 ∈ col1_nums, n2 ∈ col2_nums, n3 ∈ col3_nums
    # ◎○が必ず含まれる設計 → ◎-○-▲が必ず買い目に存在する
    col1_nums = [h.get('馬番') for h in col1 if h.get('馬番')]
    col2_nums = [h.get('馬番') for h in col2 if h.get('馬番')]
    col3_nums = [h.get('馬番') for h in col3 if h.get('馬番')]
    
    combos_set = set()
    all_combos = []
    for n1 in col1_nums:
        for n2 in col2_nums:
            for n3 in col3_nums:
                nums = tuple(sorted([int(n1), int(n2), int(n3)]))
                if len(set(nums)) == 3 and nums not in combos_set:
                    combos_set.add(nums)
                    all_combos.append(nums)
    
    # ガミ組み合わせ削除: 1・2・3番人気のみの3連複を排除
    top3_pops = set()
    for h in horses_with_roles:
        if h.get('人気', 999) <= 3:
            num = h.get('馬番')
            if num:
                top3_pops.add(int(num))
    
    filtered_combos = []
    for combo in all_combos:
        combo_set = set(combo)
        # 上位3番人気のみで構成される組み合わせはガミ候補として排除
        if combo_set.issubset(top3_pops) and len(top3_pops) >= 3:
            continue  # ガミ候補を除外
        filtered_combos.append(combo)
    
    all_combos = filtered_combos if filtered_combos else all_combos
    
    # --- マイナス期待値買い目フィルター ---
    # 各組み合わせの推定三連複期待配当倍率を計算し、MIN_COMBO_RETURN未満を排除
    # スコア順位マップ: 補正後スコア降順に1位付け
    score_sorted_nums = [h.get('馬番') for h in sorted(
        horses_with_roles, key=lambda h: h.get('補正後スコア', 0), reverse=True
    ) if h.get('馬番')]
    score_rank_map = {int(num): rank+1 for rank, num in enumerate(score_sorted_nums)}
    _MIN_COMBO_RETURN = 1.5  # 1点100円投資で150円以上の期待配当が見込める組み合わせのみ残す
    profitable_combos = [
        combo for combo in all_combos
        if _estimate_trifecta_expected_return(
            [score_rank_map.get(int(n), 9) for n in combo],
            min_return=_MIN_COMBO_RETURN
        )
    ]
    # フィルター後に1点も残らない場合は元のリストを使用
    if profitable_combos:
        all_combos = profitable_combos
    
    # 最大点数制限（10点以内）
    max_c = FUND_MANAGEMENT["max_combos_trifecta"]
    if len(all_combos) > max_c:
        all_combos = all_combos[:max_c]
    
    combo_count = len(all_combos)
    
    # --- 合成オッズ計算 ---
    # 三連複フォーメーション用合成オッズ:
    # フォーメーション全体ではなく「軸馬 + 穴馬」のコアペアで計算する。
    # 理由: 三連複の配当は軸×穴の組み合わせに引っ張られるため、
    #        全選択馬の平均よりコアペアの期待値が実態に近い。
    #        基準: コアペア合成オッズ >= 3.0倍
    #              全体合成オッズ >= 2.0倍 (トリガミ回避最低ライン)
    core_horses = col1[:1] + col3[:1]   # 最強軸 + 最良穴
    all_selected = list({h.get('馬番'): h
                         for h in col1 + col2 + col3
                         if h.get('馬番')}.values())
    
    core_synthetic_odds, so_method = calculate_synthetic_odds(core_horses)
    full_synthetic_odds, _ = calculate_synthetic_odds(all_selected)
    
    # 表示用はコア合成オッズを採用
    synthetic_odds = core_synthetic_odds
    
    # --- 合成オッズフィルター ---
    # コアペア (1軸馬+1穴馬) の合成オッズ >= min_synthetic_odds (3.0倍)
    # 理由: 三連複の配当は軸×穴の組み合わせに大きく依存するため、
    #        コアペアの期待値で判断するのが実態に近い。
    min_so   = FUND_MANAGEMENT["min_synthetic_odds"]
    ref_min  = FUND_MANAGEMENT.get("reference_min_odds", 2.0)
    ref_max  = FUND_MANAGEMENT.get("reference_max_odds", 3.5)
    ref_ratio= FUND_MANAGEMENT.get("reference_stake_ratio", 0.5)

    # ── オッズデータ有無の確認（参考用ログのみ・閾値は変更しない） ──
    # v14.3修正: 推定オッズでも3.5倍基準を維持し、2.0〜3.5倍は参考枠へ正しく分類する。
    # 旧v14.2では閾値を2.0倍に緩和していたが、推奨/参考の分類が崩れるため廃止。
    has_odds_data = any(
        h.get('単勝オッズ') or h.get('オッズ') or h.get('win_odds') or h.get('人気')
        for h in horses_with_roles
    )
    if not has_odds_data:
        # [v14.3] 閾値緩和を廃止: 推定値でも min_so=3.5, ref_min=2.0 をそのまま使用
        # 推定合成オッズ 2.0〜3.5倍 → 参考予測(⭐⭐) として表示
        # 推定合成オッズ ≥ 3.5倍   → 推奨予測(⭐⭐⭐) として表示
        print(f"[v14.3] 推定オッズ使用（閾値維持: min_so={min_so}, ref_min={ref_min}）")

    if core_synthetic_odds < min_so:
        analysis["合成オッズ"] = core_synthetic_odds
        analysis["合成オッズ_全体"] = full_synthetic_odds
        analysis["合成オッズ_方法"] = so_method

        # --- Phase1: 参考予測枠 ---
        # 合成オッズが ref_min 以上 min_so 未満 かつ 断層あり → 参考扱い
        if ref_min <= core_synthetic_odds < ref_max:
            skip_msg = (
                f"合成オッズ不足(参考枠へ)"
                f"(コア:{core_synthetic_odds}倍 < {min_so}倍)"
            )
            analysis["スキップ理由"] = skip_msg
            analysis["参考予測"] = True
            analysis["参考_合成オッズ"] = core_synthetic_odds
            # v14.3.1: 参考枠でも軸馬・相手馬・穴馬情報をanalysisに保存（フロントエンド表示用）
            analysis["軸馬候補"] = [
                {"馬番": h.get("馬番"), "馬名": h.get("馬名"), "人気": h.get("人気"),
                 "補正後スコア": h.get("補正後スコア", 0)}
                for h in col1
            ]
            analysis["相手馬候補"] = [
                {"馬番": h.get("馬番"), "馬名": h.get("馬名"), "人気": h.get("人気")}
                for h in col2
            ]
            analysis["穴馬候補"] = [
                {"馬番": h.get("馬番"), "馬名": h.get("馬名"), "人気": h.get("人気")}
                for h in col3
            ]
            return None, 0, skip_msg, analysis, old_logic
        # --- 完全スキップ ---
        skip_msg = (
            f"合成オッズ不足"
            f"(コア:{core_synthetic_odds}倍 < {min_so}倍)"
            f"({'実オッズ' if so_method=='actual' else '推定'})"
        )
        analysis["スキップ理由"] = skip_msg
        return None, 0, skip_msg, analysis, old_logic
    
    # --- 賭け金計算: 1点100円 × 点数 (案A) ---
    # オッズ水準に応じて1点あたりの金額を調整
    # 案B: 100円 or 200円の2段階（150円廃止・JRA100円単位に統一）
    per_combo_stake = FUND_MANAGEMENT["base_stake_trifecta"]  # 基本100円/点
    if core_synthetic_odds >= FUND_MANAGEMENT["odds_boost_threshold_5"]:
        per_combo_stake = int(per_combo_stake * 2)   # 5倍以上→200円/点
        stake_reason = f"コア合成オッズ{core_synthetic_odds}倍(5倍以上→200円/点)"
    else:
        stake_reason = f"コア合成オッズ{core_synthetic_odds}倍(基本100円/点)"
    
    # 投資額 = 1点あたり賭け金 × 点数（JRA最低100円/点に対応）
    investment = per_combo_stake * combo_count

    # =============================================
    # アプローチA: 波乱度高時 穴馬ボックス自動追加
    # =============================================
    _UPSET_BOX_THRESHOLD = 60   # 発動閾値 (0〜100+)
    _UPSET_BOX_MAX_HORSES = 4   # ボックス対象最大頭数 → C(4,3)=4点まで

    upset_score, upset_reasons = _calculate_upset_score(race, axis_candidates, hole_candidates)
    hole_box_combos = []  # 穴ボックス専用組み合わせリスト

    if upset_score >= _UPSET_BOX_THRESHOLD:
        # 穴馬候補（断層下のhole_candidates）上位4頭を選定
        # dark_horses_sorted が利用可能なのでそちらを優先
        _box_pool = []
        _seen_box = set()
        for _h in dark_horses_sorted:
            _num = _h.get('馬番')
            if _num and str(_num) not in _seen_box and len(_box_pool) < _UPSET_BOX_MAX_HORSES:
                _box_pool.append(_h)
                _seen_box.add(str(_num))
        # 足りない場合は hole_candidates から補充
        for _h in hole_candidates:
            _num = _h.get('馬番')
            if _num and str(_num) not in _seen_box and len(_box_pool) < _UPSET_BOX_MAX_HORSES:
                _box_pool.append(_h)
                _seen_box.add(str(_num))

        if len(_box_pool) >= 3:
            _box_nums = [_h.get('馬番') for _h in _box_pool if _h.get('馬番')]
            for _combo in iter_combinations(_box_nums, 3):
                _nums = tuple(sorted([int(_n) for _n in _combo]))
                if _nums not in combos_set:      # 既存フォーメーションと重複しない
                    hole_box_combos.append(_nums)
                    combos_set.add(_nums)

        # 投資額に穴ボックス分を追加（同一単価）
        if hole_box_combos:
            investment += per_combo_stake * len(hole_box_combos)
            print(f"[穴ボックス] 発動! upset_score={upset_score} / "
                  f"追加{len(hole_box_combos)}点 / 理由:{upset_reasons}")
    else:
        print(f"[穴ボックス] 非発動 upset_score={upset_score} (<{_UPSET_BOX_THRESHOLD})")

    # =============================================
    # 改善②(v14.0): 相手スコア上位3頭ボックス（常時追加・最大3点）
    # 軸が外れても相手3頭が来れば的中できる救済買い目
    # 「全買い目に軸が必須」という構造の弱点を補完
    # =============================================
    # col2+col3から軸を除いた馬をスコア降順で取得
    _rival_pool = sorted(
        [h for h in col2 + col3
         if str(h.get('馬番')) not in col1_nums_set and h.get('馬番')],
        key=lambda h: h.get('補正後スコア', 0), reverse=True
    )
    # 重複除去（馬番で一意化）
    _seen_rival = set()
    _rival_unique = []
    for _h in _rival_pool:
        _n = str(_h.get('馬番'))
        if _n not in _seen_rival:
            _seen_rival.add(_n)
            _rival_unique.append(_h)

    rival_box_combos = []
    if len(_rival_unique) >= 3:
        _rbox_nums = [_h.get('馬番') for _h in _rival_unique[:4] if _h.get('馬番')]
        for _combo in iter_combinations(_rbox_nums, 3):
            _nums = tuple(sorted([int(_n) for _n in _combo]))
            if _nums not in combos_set:
                rival_box_combos.append(_nums)
                combos_set.add(_nums)
                if len(rival_box_combos) >= 3:   # 最大3点まで
                    break
        if rival_box_combos:
            investment += per_combo_stake * len(rival_box_combos)
            _rbox_str = ['-'.join(str(n) for n in c) for c in rival_box_combos]
            print(f"[相手ボックス] {len(rival_box_combos)}点追加: {_rbox_str}")
    else:
        rival_box_combos = []

    # --- ワイド候補 ---
    wide_candidates = check_wide_candidates(horses_with_roles)
    
    # --- 複勝候補 ---
    place_candidates = check_place_candidates(horses_with_roles, race_distance)
    
    # --- betting_plan 構築 ---
    betting_plan = {
        # 新ロジック
        "軸": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "人気": h.get('人気'),
                "評価": "◎" if i == 0 else "○",
                "スコア": h.get('新スコア', 0),
                "補正後スコア": h.get('補正後スコア', h.get('新スコア', 0)),
                "内訳": h.get('新スコア_内訳', {}),
                "根拠": generate_reason(h),
                "断層役割": h.get('断層役割', '未分類'),
                "危険フラグ": h.get('危険フラグ', False),
                "危険理由": h.get('危険理由', [])
            }
            for i, h in enumerate(col1)
        ],
        "対抗": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "人気": h.get('人気'),
                "評価": "▲",
                "スコア": h.get('新スコア', 0),
                "補正後スコア": h.get('補正後スコア', h.get('新スコア', 0)),
                "根拠": generate_reason(h),
                "断層役割": h.get('断層役割', '未分類'),
                "斤量騎手ボーナス": h.get('斤量騎手ボーナス', 0),
                "斤量騎手詳細": h.get('斤量騎手詳細', {})
            }
            for h in col2 if h.get('馬番') not in [x.get('馬番') for x in col1]
        ],
        "穴": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "人気": h.get('人気'),
                "評価": "△",
                "スコア": h.get('新スコア', 0),
                "補正後スコア": h.get('補正後スコア', h.get('新スコア', 0)),
                "根拠": generate_reason(h),
                "断層役割": h.get('断層役割', '未分類'),
                "斤量騎手ボーナス": h.get('斤量騎手ボーナス', 0),
                "斤量騎手詳細": h.get('斤量騎手詳細', {})
            }
            # Bug Fix ②: col3からcol2に含まれる馬を除外して穴馬のみを表示
            for h in col3 if str(h.get('馬番')) not in col2_set
        ],
        # 後方互換: 旧フォーマット用
        # Bug Fix ②-追加: 「相手」フィールドの重複除去
        # col2=list(col1)+追加, col3=list(col2)+穴 のため同じ馬が複数回出現する問題を修正
        "相手": list({str(h.get('馬番')): {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": "△",
                "スコア": h.get('新スコア', 0),
                "根拠": generate_reason(h)
            }
            for h in (col2 + col3)
            if str(h.get('馬番')) not in {str(x.get('馬番')) for x in col1}
        }.values()),
        "買い目タイプ": "三連複フォーメーション(断層役割ベース・精度改善v3)",
        "組み合わせ数": combo_count + len(hole_box_combos) + len(rival_box_combos),
        "合成オッズ": core_synthetic_odds,
        "合成オッズ_全体": full_synthetic_odds,
        "合成オッズ_方法": so_method,
        "賭け金調整": stake_reason,
        "全買い目": [
            '-'.join(str(n) for n in combo)
            for combo in (all_combos + hole_box_combos + rival_box_combos)
        ],
        "穴ボックス発動": len(hole_box_combos) > 0,
        "穴ボックス_upset_score": upset_score,
        "穴ボックス_upset_理由": upset_reasons,
        "穴ボックス_買い目": [
            '-'.join(str(n) for n in c) for c in hole_box_combos
        ],
        "穴ボックス_追加点数": len(hole_box_combos),
        "相手ボックス_買い目": [
            '-'.join(str(n) for n in c) for c in rival_box_combos
        ],
        "相手ボックス_追加点数": len(rival_box_combos),
        "ワイド候補": wide_candidates,
        "複勝候補": place_candidates,
        # 旧ロジック比較
        "旧ロジック": old_logic
    }
    
    # --- 分析情報を更新 ---
    analysis["合成オッズ"] = core_synthetic_odds
    analysis["合成オッズ_全体"] = full_synthetic_odds
    analysis["合成オッズ_方法"] = so_method
    analysis["レースタイプ"] = race_type
    analysis["断層数"] = len(layers)
    analysis["軸馬数"] = len(col1)
    analysis["対抗馬数"] = len(col2) - len(col1)
    analysis["穴馬数"] = len(col3)
    analysis["組み合わせ数_新"] = combo_count + len(hole_box_combos)
    analysis["穴ボックス発動"] = len(hole_box_combos) > 0
    analysis["穴ボックス_upset_score"] = upset_score
    analysis["相手ボックス_追加点数"] = len(rival_box_combos)
    analysis["組み合わせ数_新"] = combo_count + len(hole_box_combos) + len(rival_box_combos)
    analysis["組み合わせ数_旧"] = old_logic["旧_組み合わせ数"]
    analysis["投資額削減率"] = round(
        (1 - investment / max(old_logic["旧_投資額"], 1)) * 100, 1
    )
    
    # [v14.1] 全馬断層役割サマリー追加（デバッグ・分析用）
    # 各馬の断層役割・スコア・col1/col2選定状況を一覧化
    analysis["全馬断層役割サマリー"] = [
        {
            "馬番": h.get('馬番'),
            "馬名": h.get('馬名'),
            "人気": h.get('人気'),
            "断層役割": h.get('断層役割', '未分類'),
            "断層役割_en": h.get('断層役割_en', 'flat'),
            "新スコア": h.get('新スコア', 0),
            "補正後スコア": h.get('補正後スコア', 0),
            "軸選定": str(h.get('馬番')) in col1_nums_set,
            "相手選定": str(h.get('馬番')) in col2_set,
        }
        for h in sorted(horses_with_roles, key=lambda x: x.get('人気', 99))
    ]
    print(f"[v14.1 断層役割サマリー] " + ", ".join(
        f"{h['馬番']}番({h['人気']!r}人気)={h['断層役割'][:2]}/{'軸' if h['軸選定'] else ('相手' if h['相手選定'] else '-')}"
        for h in analysis['全馬断層役割サマリー']
    ))
    
    return betting_plan, investment, None, analysis, old_logic


# =============================================
# レース選定
# =============================================
def select_races(race_data, max_races=9999):
    """予想対象レースを選定"""
    races = race_data.get('races', [])
    selected  = []
    skipped   = []
    reference = []  # Phase1: 参考予測リスト（合成オッズ2.0〜3.5倍）
    turbulence_counts = {"低": 0, "中": 0, "高": 0}
    
    for race in races:
        horses = race.get('horses', [])
        
        # 基本フィルター: 若馬限定戦スキップ（3歳/2歳戦は予測精度が低いため除外）
        race_name_str = race.get('レース名', '')
        if re.search(r'(3歳|2歳|新馬|未勝利)', race_name_str):
            # 若馬戦はスコアと実力の乖離が大きいためスキップ
            skipped.append({
                "race_id": race.get('race_id'),
                "race_name": race.get('レース名', race.get('race_name', '')),
                "venue": race.get('競馬場', race.get('venue', '')),
                "reason": "若馬限定戦（3歳/2歳/新馬）",
                "skip_type": "若馬戦"
            })
            continue
        
        # 基本フィルター: 出馬数
        if len(horses) < 8:
            skipped.append({
                "race_id": race.get('race_id'),
                "race_name": race.get('レース名', race.get('race_name', '')),
                "venue": race.get('競馬場', race.get('venue', '')),
                "reason": f"出馬数不足({len(horses)}頭)",
                "skip_type": "出馬数不足"
            })
            continue
        
        # 基本フィルター: スコアデータ
        horses_with_score = [h for h in horses if h.get('新スコア')]
        if len(horses_with_score) < len(horses) * 0.8:
            skipped.append({
                "race_id": race.get('race_id'),
                "race_name": race.get('レース名', race.get('race_name', '')),
                "venue": race.get('競馬場', race.get('venue', '')),
                "reason": "新スコアデータ不足",
                "skip_type": "データ不足"
            })
            continue
        
        # 評価スコア計算
        scores = [h.get('新スコア', 0) for h in horses_with_score]
        top_3_scores = sorted(scores, reverse=True)[:3]
        evaluation_score = sum(top_3_scores) / 3 if len(top_3_scores) >= 3 else 0
        data_quality = int((len(horses_with_score) / len(horses)) * 20)
        
        # オッズ・人気データがない場合は閾値を緩和（前日データのため）
        has_odds = any(h.get('単勝オッズ') or h.get('オッズ') or h.get('人気') for h in horses)
        eval_threshold = 50 if has_odds else 30
        if evaluation_score < eval_threshold or data_quality < 10:
            skipped.append({
                "race_id": race.get('race_id'),
                "race_name": race.get('レース名', race.get('race_name', '')),
                "venue": race.get('競馬場', race.get('venue', '')),
                "reason": f"評価不足(score:{round(evaluation_score,1)}/quality:{data_quality}/threshold:{eval_threshold})",
                "skip_type": "評価不足"
            })
            continue
        
        turbulence = calculate_turbulence(race)
        
        # 新ロジック: 買い目生成
        betting_plan, investment, skip_reason, analysis, old_logic = generate_betting_plan(race)
        
        # 断層フラット・合成オッズ不足によるスキップ
        if skip_reason:
            is_reference = analysis.get("参考予測", False)
            skip_type = "断層なし" if "フラット" in skip_reason else "合成オッズ不足"

            if is_reference:
                # --- Phase1: 参考予測として別リストへ ---
                ref_stake_ratio = FUND_MANAGEMENT.get("reference_stake_ratio", 0.5)
                ref_combos = max(1, int(analysis.get("組み合わせ数", 1)))
                # v14.3.1修正①: 100円単位に統一（50円→100円）
                ref_per_combo = max(100, int(FUND_MANAGEMENT["base_stake_trifecta"] * ref_stake_ratio))
                ref_per_combo = (ref_per_combo // 100) * 100  # 100円単位切り捨て
                ref_inv = ref_per_combo * ref_combos
                # v14.3.1修正②: 簡易betting_plan構築（軸馬・相手馬情報を表示可能に）
                ref_betting_plan = {
                    "軸":         analysis.get("軸馬候補", []),
                    "相手":       analysis.get("相手馬候補", []),
                    "穴":         analysis.get("穴馬候補", []),
                    "合成オッズ": analysis.get("参考_合成オッズ", 0),
                    "組み合わせ数": 0,
                    "全買い目":   [],
                    "投資額":     ref_inv,
                }
                reference.append({
                    "race_id":        race.get('race_id'),
                    "race_name":      race.get('レース名', race.get('race_name', '不明')),
                    "venue":          race.get('競馬場', race.get('venue', '不明')),
                    "distance":       race.get('距離', race.get('distance', '')),
                    "track":          race.get('トラック', race.get('track_condition', '')),
                    "start_time":     race.get('発走時刻', ''),
                    "grade":          race.get('grade', ''),
                    "ref_rank":       "⭐⭐",
                    "ref_label":      "参考",
                    "synthetic_odds": analysis.get("参考_合成オッズ", 0),
                    "investment":     ref_inv,
                    "note":           "合成オッズが推奨基準未満。自己判断でご参考ください。",
                    "断層分析":       analysis,
                    "betting_plan":   ref_betting_plan,
                })
            else:
                skipped.append({
                    "race_id":  race.get('race_id'),
                    "reason":   skip_reason,
                    "skip_type": skip_type,
                    "analysis": analysis
                })
            continue
        
        # スコア帯分類
        if evaluation_score >= 90:
            score_tier = "S"
        elif evaluation_score >= 80:
            score_tier = "A"
        elif evaluation_score >= 70:
            score_tier = "B"
        else:
            score_tier = "C"
        
        # 仮想買い目プラン (後方互換)
        axis_list = betting_plan.get("軸", [])
        axis_nums = [str(h.get("馬番")) for h in axis_list if h.get("馬番") is not None]
        virtual_bets_plan = {}
        if len(axis_nums) >= 1:
            virtual_bets_plan["複勝_軸1"] = {
                "type": "複勝", "馬番": axis_nums[0], "投資": 300
            }
        if len(axis_nums) >= 2:
            virtual_bets_plan["複勝_軸2"] = {
                "type": "複勝", "馬番": axis_nums[1], "投資": 300
            }
            virtual_bets_plan["ワイド_軸1-2"] = {
                "type": "ワイド",
                "組み合わせ": f"{min(axis_nums[0], axis_nums[1], key=int)}-{max(axis_nums[0], axis_nums[1], key=int)}",
                "投資": 500
            }
            virtual_bets_plan["馬連_軸1-2"] = {
                "type": "馬連",
                "組み合わせ": f"{min(axis_nums[0], axis_nums[1], key=int)}-{max(axis_nums[0], axis_nums[1], key=int)}",
                "投資": 500
            }
        
        # 低ROI競馬場フィルタ: 推奨 → 参考に降格 (v13.1追加)
        race_venue = race.get('競馬場', race.get('venue', ''))
        venue_cfg = LOW_ROI_VENUES.get(race_venue, {})
        if venue_cfg.get("exclude_level") == "select":
            # 推奨(⭐⭐⭐)には選定せず、参考(⭐⭐)として追加
            ref_stake_ratio = FUND_MANAGEMENT.get("reference_stake_ratio", 0.5)
            ref_inv = int(FUND_MANAGEMENT["base_stake_trifecta"] * ref_stake_ratio)
            reference.append({
                "race_id":        race.get('race_id'),
                "race_name":      race.get('レース名', '不明'),
                "venue":          race_venue,
                "distance":       race.get('距離'),
                "track":          race.get('トラック'),
                "grade":          race.get('grade', ''),
                "ref_rank":       "⭐⭐",
                "ref_label":      "参考(低ROI場)",
                "synthetic_odds": betting_plan.get("合成オッズ", 0),
                "investment":     ref_inv,
                "note":           f"低ROI競馬場({race_venue} ROI:{venue_cfg.get('roi_pct')}%)のため参考扱い。自己判断でご参考ください。",
                "断層分析":       analysis,
            })
            turbulence_counts[turbulence] += 1
            continue

        selected.append({
            "race_id": race.get('race_id'),
            "race_name": race.get('レース名', '不明'),
            "venue": race.get('競馬場', '不明'),
            "distance": race.get('距離'),
            "track": race.get('トラック'),
            "start_time": race.get('発走時刻'),
            "turbulence": turbulence,
            "evaluation_score": round(evaluation_score, 2),
            "score_tier": score_tier,
            "top_3_avg": round(sum(top_3_scores) / 3, 2),
            "data_quality": data_quality,
            "betting_plan": betting_plan,
            "investment": investment,
            "virtual_bets_plan": virtual_bets_plan,
            # 新規追加フィールド
            "断層分析": analysis,
            "合成オッズ": betting_plan.get("合成オッズ", 0),
            "旧ロジック": old_logic,
            "資金管理ルール": {
                "賭け金": investment,
                "最大点数": FUND_MANAGEMENT["max_combos_trifecta"],
                "損切り_日次": FUND_MANAGEMENT["daily_loss_limit"],
                "損切り_週次": FUND_MANAGEMENT["weekly_loss_limit"],
                "連敗停止": FUND_MANAGEMENT["consecutive_loss_stop"]
            }
        })
        turbulence_counts[turbulence] += 1
    
    # evaluation_score 降順でソート
    final_selected = sorted(
        selected, key=lambda r: r["evaluation_score"], reverse=True
    )[:max_races]
    
    return final_selected, skipped, reference, turbulence_counts


# =============================================
# メイン処理
# =============================================
def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python select_predictions.py <ymd>")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    output_file = f"final_predictions_{ymd}.json"
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            race_data = json.load(f)
        
        print(f"[INFO] {input_file} を読み込みました")
        
        selected_races, skipped_races, reference_races, turbulence_counts = select_races(race_data)
        total_investment = sum(r["investment"] for r in selected_races)
        
        # [v14.1] 日次投資上限チェック: 上限超過時は低合成オッズのレースを除外
        daily_limit = FUND_MANAGEMENT.get("daily_loss_limit", 10000)
        if total_investment > daily_limit:
            print(f"[⚠️ 日次上限] ¥{total_investment:,} > 上限¥{daily_limit:,} → 低オッズレースを除外します")
            # 合成オッズ降順（高オッズ=高期待値を優先して残す）
            selected_races = sorted(
                selected_races,
                key=lambda r: r.get("analysis", {}).get("合成オッズ", 0),
                reverse=True
            )
            trimmed, running_total = [], 0
            for r in selected_races:
                if running_total + r["investment"] <= daily_limit:
                    trimmed.append(r)
                    running_total += r["investment"]
                else:
                    venue = r.get("venue", r.get("競馬場", "?"))
                    rname = r.get("race_name", r.get("レース名", "?"))
                    print(f"  [除外] {venue} {rname} ¥{r['investment']:,} (合成オッズ:{r.get('analysis',{}).get('合成オッズ',0):.1f}倍)")
            selected_races = trimmed
            total_investment = running_total
            print(f"  [調整後] 選定レース数:{len(selected_races)} 総投資額:¥{total_investment:,}")
        
        old_total_investment = sum(
            r.get("旧ロジック", {}).get("旧_投資額", 0)
            for r in selected_races
        )
        
        # スキップ内訳
        skip_flat  = sum(1 for s in skipped_races if s.get('skip_type') == '断層なし')
        skip_odds  = sum(1 for s in skipped_races if s.get('skip_type') == '合成オッズ不足')
        skip_other = len(skipped_races) - skip_flat - skip_odds
        
        output_data = {
            "ymd": ymd,
            "logic_version": "v14.3.1_参考レース投資額100円統一・軸馬情報表示修正",
            "generated_at": datetime.now(timezone(timedelta(hours=9))).strftime(
                "%Y-%m-%d %H:%M:%S (JST)"
            ),
            "total_races": len(race_data.get('races', [])),
            "selected_races": len(selected_races),
            "skipped_races": len(skipped_races),
            "summary": {
                "turbulence": turbulence_counts,
                "total_investment": total_investment,
                "old_total_investment": old_total_investment,
                "investment_reduction": f"{round((1 - total_investment / max(old_total_investment, 1)) * 100, 1)}%削減",
                "skip_breakdown": {
                    "断層なし(フラット)": skip_flat,
                    "合成オッズ不足": skip_odds,
                    "その他": skip_other
                },
                "reference_count": len(reference_races)
            },
            "fund_management": FUND_MANAGEMENT,
            "selected_predictions": selected_races,
            "reference_predictions": reference_races,  # Phase1: 参考予測（⭐⭐）
            "reference_count": len(reference_races)
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        with open("latest_predictions.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SUCCESS] final_predictions_{ymd}.json を生成しました")
        print(f"[SUCCESS] latest_predictions.json も生成しました")
        print(f"\n{'='*60}")
        print(f"📊 本日の予想サマリー ({ymd[:4]}/{ymd[4:6]}/{ymd[6:]})")
        print(f"{'='*60}")
        print(f"対象レース数    : {len(race_data.get('races', []))}R")
        print(f"選定レース数    : {len(selected_races)}R")
        print(f"スキップ(断層なし): {skip_flat}R")
        print(f"スキップ(合成オッズ): {skip_odds}R")
        print(f"--- 投資額比較 ---")
        print(f"新ロジック総投資: ¥{total_investment:,}")
        print(f"旧ロジック総投資: ¥{old_total_investment:,}")
        if old_total_investment > 0:
            reduction = (1 - total_investment / old_total_investment) * 100
            print(f"削減率          : {reduction:.1f}%")
        print(f"{'='*60}\n")
        
        print("【選定レース詳細】")
        for i, race in enumerate(selected_races, 1):
            bp = race['betting_plan']
            synthetic = race.get('合成オッズ', 0)
            old_inv = race.get('旧ロジック', {}).get('旧_投資額', 0)
            print(
                f"レース{i}: {race['venue']} "
                f"(軸{len(bp['軸'])}頭+対抗+穴) "
                f"{bp['組み合わせ数']}点 "
                f"新:¥{race['investment']:,} / "
                f"旧:¥{old_inv:,} | "
                f"合成オッズ{synthetic}倍"
            )
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
