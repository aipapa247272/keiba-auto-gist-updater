#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新予想ロジック対応: レース選定スクリプト
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
import os
from datetime import datetime, timezone, timedelta
from math import comb
from itertools import combinations as iter_combinations

# =============================================
# 資金管理定数 (Fund Management Constants)
# =============================================
FUND_MANAGEMENT = {
    "base_stake_trifecta": 1000,   # 三連複: 1レース固定賭け金
    "base_stake_wide": 500,         # ワイド: 1点あたり
    "base_stake_place": 300,        # 複勝: 1点あたり
    "max_combos_trifecta": 15,      # 三連複: 最大点数
    "max_combos_wide": 2,           # ワイド: 最大点数
    "max_combos_place": 3,          # 複勝: 最大点数
    "min_synthetic_odds": 3.0,      # 合成オッズ最低ライン (これ未満はスキップ)
    "odds_boost_threshold_4": 4.0,  # 合成オッズ4倍以上 → 賭け金1.5倍
    "odds_boost_threshold_5": 5.0,  # 合成オッズ5倍以上 → 賭け金2倍
    "min_wide_odds": 5.0,           # ワイドオッズ最低ライン
    "min_place_odds": 2.0,          # 複勝オッズ最低ライン
    "place_odds_spread_min": 2.0,   # 複勝オッズ幅の最低値
    "daily_loss_limit": 10000,      # 日次損切りライン
    "weekly_loss_limit": 30000,     # 週次損切りライン
    "consecutive_loss_stop": 3,     # 連敗停止回数
    "odds_layer_threshold": 2.0,    # 断層判定: 変化率がこの値以上
    "max_popularity_place": 5,      # 複勝対象: 最大人気順位
    "hole_horse_min_popularity": 6, # 穴馬: 6番人気以下
}

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
    else:
        # フォールバック: DESスコア逆順をオッズの代理指標として使用
        sorted_horses = sorted(horses, key=lambda h: h.get('新スコア', 0), reverse=True)
        # スコア差が大きい箇所を擬似断層として検出
        layers = []
        for i in range(1, len(sorted_horses)):
            s_prev = sorted_horses[i-1].get('新スコア', 0)
            s_curr = sorted_horses[i].get('新スコア', 0)
            if s_prev > 0 and s_curr > 0:
                # スコアが20点以上急落 → 擬似断層
                if (s_prev - s_curr) >= 20:
                    layers.append({
                        'position': i,
                        'change_rate': round(s_prev / max(s_curr, 1), 2),
                        'boundary_odds': None,
                        'from_horse': sorted_horses[i-1].get('馬名', ''),
                        'to_horse': sorted_horses[i].get('馬名', ''),
                        'estimated': True
                    })
    
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
    
    # --- 三連複フォーメーション組み立て ---
    # 1列目: 軸馬 1〜2頭
    col1 = axis_candidates[:2]
    # 2列目: 対抗馬 1〜2頭 (軸馬を含む)
    col2_set = set()
    col2 = []
    for h in (rival_candidates + col1):
        key = h.get('馬番')
        if key and key not in col2_set:
            col2_set.add(key)
            col2.append(h)
        if len(col2) >= 3:
            break
    # 3列目: 穴馬 必ず1〜2頭 (col1, col2 と重複しない)
    used_nums = set(h.get('馬番') for h in col1 + col2)
    col3 = []
    for h in hole_candidates:
        if h.get('馬番') not in used_nums:
            col3.append(h)
        if len(col3) >= 2:
            break
    # col3が空の場合はスコア下位から補充
    if not col3:
        score_sorted_asc = sorted(horses_with_roles,
                                   key=lambda h: h.get('新スコア', 0))
        for h in score_sorted_asc:
            if h.get('馬番') not in used_nums:
                col3.append(h)
            if len(col3) >= 2:
                break
    
    # --- フォーメーションの全組み合わせ生成 ---
    col1_nums = [h.get('馬番') for h in col1 if h.get('馬番')]
    col2_nums = [h.get('馬番') for h in col2 if h.get('馬番')]
    col3_nums = [h.get('馬番') for h in col3 if h.get('馬番')]
    
    # 重複を排除した全買い目
    combos_set = set()
    all_combos = []
    for n1 in col1_nums:
        for n2 in col2_nums:
            for n3 in col3_nums:
                nums = tuple(sorted([n1, n2, n3]))
                # 3頭が全て異なること
                if len(set(nums)) == 3 and nums not in combos_set:
                    combos_set.add(nums)
                    all_combos.append(nums)
    
    # 最大点数制限
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
    min_so = FUND_MANAGEMENT["min_synthetic_odds"]
    if core_synthetic_odds < min_so:
        skip_msg = (
            f"合成オッズ不足"
            f"(コア:{core_synthetic_odds}倍 < {min_so}倍)"
            f"({'実オッズ' if so_method=='actual' else '推定'})"
        )
        analysis["合成オッズ"] = core_synthetic_odds
        analysis["合成オッズ_全体"] = full_synthetic_odds
        analysis["合成オッズ_方法"] = so_method
        analysis["スキップ理由"] = skip_msg
        return None, 0, skip_msg, analysis, old_logic
    
    # --- 賭け金計算 (コア合成オッズに応じて倍率調整) ---
    base_stake = FUND_MANAGEMENT["base_stake_trifecta"]
    if core_synthetic_odds >= FUND_MANAGEMENT["odds_boost_threshold_5"]:
        adjusted_stake = int(base_stake * 2)
        stake_reason = f"コア合成オッズ{core_synthetic_odds}倍(5倍超→2倍増額)"
    elif core_synthetic_odds >= FUND_MANAGEMENT["odds_boost_threshold_4"]:
        adjusted_stake = int(base_stake * 1.5)
        stake_reason = f"コア合成オッズ{core_synthetic_odds}倍(4倍超→1.5倍増額)"
    else:
        adjusted_stake = base_stake
        stake_reason = f"コア合成オッズ{core_synthetic_odds}倍(基本賭け金)"
    
    # 投資額 = 固定賭け金（点数に関わらず）
    investment = adjusted_stake
    
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
                "評価": "◎" if i == 0 else "○",
                "スコア": h.get('新スコア', 0),
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
                "評価": "▲",
                "スコア": h.get('新スコア', 0),
                "根拠": generate_reason(h),
                "断層役割": h.get('断層役割', '未分類')
            }
            for h in col2 if h.get('馬番') not in [x.get('馬番') for x in col1]
        ],
        "穴": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": "△",
                "スコア": h.get('新スコア', 0),
                "根拠": generate_reason(h),
                "断層役割": h.get('断層役割', '未分類')
            }
            for h in col3
        ],
        # 後方互換: 旧フォーマット用
        "相手": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": "△",
                "スコア": h.get('新スコア', 0),
                "根拠": generate_reason(h)
            }
            for h in (col2 + col3)
            if h.get('馬番') not in [x.get('馬番') for x in col1]
        ],
        "買い目タイプ": "三連複フォーメーション(断層役割ベース)",
        "組み合わせ数": combo_count,
        "合成オッズ": core_synthetic_odds,
        "合成オッズ_全体": full_synthetic_odds,
        "合成オッズ_方法": so_method,
        "賭け金調整": stake_reason,
        "全買い目": [
            '-'.join(str(n) for n in combo)
            for combo in all_combos
        ],
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
    analysis["組み合わせ数_新"] = combo_count
    analysis["組み合わせ数_旧"] = old_logic["旧_組み合わせ数"]
    analysis["投資額削減率"] = round(
        (1 - investment / max(old_logic["旧_投資額"], 1)) * 100, 1
    )
    
    return betting_plan, investment, None, analysis, old_logic


# =============================================
# レース選定
# =============================================
def select_races(race_data, max_races=9999):
    """予想対象レースを選定"""
    races = race_data.get('races', [])
    selected = []
    skipped = []
    turbulence_counts = {"低": 0, "中": 0, "高": 0}
    
    for race in races:
        horses = race.get('horses', [])
        
        # 基本フィルター: 出馬数
        if len(horses) < 8:
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": f"出馬数不足({len(horses)}頭)"
            })
            continue
        
        # 基本フィルター: スコアデータ
        horses_with_score = [h for h in horses if h.get('新スコア')]
        if len(horses_with_score) < len(horses) * 0.8:
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": "新スコアデータ不足"
            })
            continue
        
        # 評価スコア計算
        scores = [h.get('新スコア', 0) for h in horses_with_score]
        top_3_scores = sorted(scores, reverse=True)[:3]
        evaluation_score = sum(top_3_scores) / 3 if len(top_3_scores) >= 3 else 0
        data_quality = int((len(horses_with_score) / len(horses)) * 20)
        
        if evaluation_score < 50 or data_quality < 10:
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": "評価不足"
            })
            continue
        
        turbulence = calculate_turbulence(race)
        
        # 新ロジック: 買い目生成
        betting_plan, investment, skip_reason, analysis, old_logic = generate_betting_plan(race)
        
        # 断層フラット・合成オッズ不足によるスキップ
        if skip_reason:
            skip_type = "断層なし" if "フラット" in skip_reason else "合成オッズ不足"
            skipped.append({
                "race_id": race.get('race_id'),
                "reason": skip_reason,
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
    
    return final_selected, skipped, turbulence_counts


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
        
        selected_races, skipped_races, turbulence_counts = select_races(race_data)
        total_investment = sum(r["investment"] for r in selected_races)
        old_total_investment = sum(
            r.get("旧ロジック", {}).get("旧_投資額", 0)
            for r in selected_races
        )
        
        # スキップ内訳
        skip_flat = sum(1 for s in skipped_races
                       if s.get('skip_type') == '断層なし')
        skip_odds = sum(1 for s in skipped_races
                       if s.get('skip_type') == '合成オッズ不足')
        skip_other = len(skipped_races) - skip_flat - skip_odds
        
        output_data = {
            "ymd": ymd,
            "logic_version": "v12_断層・合成オッズ対応",
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
                }
            },
            "fund_management": FUND_MANAGEMENT,
            "selected_predictions": selected_races
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
