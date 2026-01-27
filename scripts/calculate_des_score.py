#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DESスコア計算スクリプト（改善版 v2.0）
- 配点変更: A(30) B(25) C(20) D(25)
- D（展開適性）の本格実装
  - 脚質適性: 10点
  - 枠順適性: 8点
  - ペース予測: 7点
"""

import json
import sys
from typing import Dict, List, Tuple


def estimate_running_style(past_races: List[Dict]) -> str:
    """
    過去走データから脚質を推定
    
    判定基準:
    - 逃げ: 1コーナー1-3位 かつ 最後まで前（着順と1コーナー順位の差が小さい）
    - 先行: 1コーナー4-6位 かつ 直線で前に出る
    - 差し: 1コーナー中団 かつ 直線で伸びる
    - 追込: 1コーナー後方 かつ 直線で一気
    """
    if not past_races:
        return '不明'
    
    scores = {
        '逃げ': 0,
        '先行': 0,
        '差し': 0,
        '追込': 0
    }
    
    for race in past_races:
        corner_pos = race.get('corner_positions', '')
        if not corner_pos:
            continue
        
        # コーナー通過順の最初（1コーナー）を取得
        corners = corner_pos.split('-')
        if not corners or not corners[0]:
            continue
        
        try:
            first_corner = int(corners[0])
        except:
            continue
        
        # 着順
        try:
            finish_pos = int(race.get('着順', 99))
        except:
            finish_pos = 99
        
        # 脚質判定
        if first_corner <= 3:
            # 1コーナー3位以内
            if finish_pos - first_corner <= 2:
                scores['逃げ'] += 2  # 位置をキープ
            else:
                scores['先行'] += 1  # 後退
        
        elif first_corner <= 6:
            # 1コーナー4-6位
            if finish_pos < first_corner:
                scores['先行'] += 2  # 直線で前に出た
            else:
                scores['差し'] += 1
        
        elif first_corner <= 10:
            # 1コーナー中団
            if finish_pos <= 3:
                scores['差し'] += 2  # 好走
            else:
                scores['差し'] += 1
        
        else:
            # 1コーナー後方
            if finish_pos <= 3:
                scores['追込'] += 2  # 大外一気
            else:
                scores['追込'] += 1
    
    # 最もスコアが高い脚質を返す
    if max(scores.values()) == 0:
        return '不明'
    
    return max(scores, key=scores.get)


def analyze_race_pace(horses: List[Dict]) -> Dict:
    """
    レース全体の脚質構成を分析してペースを予測
    """
    running_styles = [h.get('推定脚質', '不明') for h in horses]
    
    style_count = {
        '逃げ': running_styles.count('逃げ'),
        '先行': running_styles.count('先行'),
        '差し': running_styles.count('差し'),
        '追込': running_styles.count('追込')
    }
    
    # ペース予測
    if style_count['逃げ'] == 0:
        pace = 'スロー'  # 逃げ馬不在 → スローペース
    elif style_count['逃げ'] == 1 and style_count['先行'] <= 2:
        pace = 'スロー'  # 逃げ馬1頭で先行馬少ない → マイペース
    elif style_count['逃げ'] >= 3 or (style_count['逃げ'] + style_count['先行']) >= 6:
        pace = 'ハイ'  # 前に行きたい馬が多い → ハイペース
    else:
        pace = 'ミドル'
    
    return {
        '脚質構成': style_count,
        '予想ペース': pace
    }


def calculate_a_score(horse: Dict) -> float:
    """
    A: 過去実績スコア（30点満点）
    - 着順実績: 10点
    - タイム指数: 10点
    - 連対率・勝率: 10点
    """
    past_races = horse.get('past_races', [])
    
    if not past_races:
        return 0.0
    
    score = 0.0
    
    # 着順実績（10点）
    finish_positions = []
    for race in past_races:
        try:
            pos = int(race.get('着順', 99))
            if pos < 99:
                finish_positions.append(pos)
        except:
            continue
    
    if finish_positions:
        avg_finish = sum(finish_positions) / len(finish_positions)
        # 平均着順が1位なら10点、10位以下なら0点
        finish_score = max(0, 10 - avg_finish)
        score += min(10, finish_score)
    
    # タイム指数（10点）
    # 簡易実装: 上がり3Fの速さで評価
    last_3f_times = []
    for race in past_races:
        last_3f = race.get('last_3f', '')
        if last_3f:
            try:
                # 例: "38.5" → 38.5秒
                time_value = float(last_3f)
                last_3f_times.append(time_value)
            except:
                continue
    
    if last_3f_times:
        avg_last_3f = sum(last_3f_times) / len(last_3f_times)
        # 上がり3Fが速いほど高得点（35秒台なら10点、40秒以上なら0点）
        time_score = max(0, 10 - (avg_last_3f - 35) * 2)
        score += min(10, time_score)
    
    # 連対率・勝率（10点）
    wins = sum(1 for p in finish_positions if p == 1)
    top2 = sum(1 for p in finish_positions if p <= 2)
    
    if finish_positions:
        win_rate = wins / len(finish_positions)
        top2_rate = top2 / len(finish_positions)
        
        rate_score = (win_rate * 5) + (top2_rate * 5)
        score += rate_score
    
    return round(score, 1)


def calculate_b_score(horse: Dict, race_distance: int) -> float:
    """
    B: 距離・馬場適性スコア（25点満点）
    - 距離適性: 10点
    - 馬場適性: 5点
    - コース適性: 5点
    - 競馬場経験: 5点
    """
    past_races = horse.get('past_races', [])
    
    if not past_races:
        return 0.0
    
    score = 0.0
    
    # 距離適性（10点）← 改善: ±200m範囲も評価
    same_distance_races = []
    similar_distance_races = []
    
    for race in past_races:
        try:
            past_dist = int(race.get('distance', 0))
            if past_dist == 0:
                continue
            
            diff = abs(past_dist - race_distance)
            
            if diff == 0:
                same_distance_races.append(race)
            elif diff <= 200:
                similar_distance_races.append(race)
        except:
            continue
    
    # 同距離での成績
    if same_distance_races:
        same_dist_positions = []
        for race in same_distance_races:
            try:
                pos = int(race.get('着順', 99))
                if pos < 99:
                    same_dist_positions.append(pos)
            except:
                continue
        
        if same_dist_positions:
            avg_pos = sum(same_dist_positions) / len(same_dist_positions)
            dist_score = max(0, 10 - avg_pos)
            score += min(10, dist_score)
    
    # 類似距離での成績（同距離がない場合）
    elif similar_distance_races:
        similar_positions = []
        for race in similar_distance_races:
            try:
                pos = int(race.get('着順', 99))
                if pos < 99:
                    similar_positions.append(pos)
            except:
                continue
        
        if similar_positions:
            avg_pos = sum(similar_positions) / len(similar_positions)
            dist_score = max(0, 7 - avg_pos * 0.7)  # 同距離より低めに評価
            score += min(7, dist_score)
    
    # 馬場適性（5点）- 簡易実装
    # TODO: 馬場状態別の成績を分析
    score += 2.5
    
    # コース適性（5点）- 簡易実装
    # TODO: 左回り・右回り別の成績を分析
    score += 2.5
    
    # 競馬場経験（5点）
    venue = horse.get('past_races', [{}])[0].get('venue', '')
    venue_races = [r for r in past_races if r.get('venue') == venue]
    
    if len(venue_races) >= 3:
        score += 5
    elif len(venue_races) >= 1:
        score += 3
    else:
        score += 1
    
    return round(score, 1)


def calculate_c_score(horse: Dict) -> float:
    """
    C: 騎手・厩舎スコア（20点満点）
    - 騎手実績: 10点
    - 厩舎実績: 5点
    - 騎手×馬の相性: 5点
    """
    # 簡易実装: 基本点を付与
    # TODO: 騎手・厩舎のデータベースを構築して詳細評価
    
    score = 0.0
    
    # 騎手実績（10点）- 簡易版
    score += 5
    
    # 厩舎実績（5点）- 簡易版
    score += 2.5
    
    # 騎手×馬の相性（5点）- 簡易版
    score += 2.5
    
    return round(score, 1)


def calculate_d_score(horse: Dict, race_info: Dict, race_analysis: Dict) -> float:
    """
    D: 展開適性スコア（25点満点）← 大幅強化
    - 脚質適性: 10点
    - 枠順適性: 8点
    - ペース予測: 7点
    """
    score = 0.0
    
    running_style = horse.get('推定脚質', '不明')
    waku = horse.get('枠番', 0)
    head_count = race_info.get('取得頭数', 8)
    pace = race_analysis.get('予想ペース', 'ミドル')
    style_count = race_analysis.get('脚質構成', {})
    
    # 1. 脚質適性（10点）
    nige_count = style_count.get('逃げ', 0)
    senko_count = style_count.get('先行', 0)
    
    if running_style == '逃げ':
        if nige_count == 1:
            score += 7  # 単独逃げ → 有利
        elif nige_count == 0:
            score += 5  # 逃げ不在 → まずまず
        else:
            score += 2  # 逃げ争い → 不利
    
    elif running_style == '先行':
        if nige_count <= 1 and senko_count <= 3:
            score += 7  # 理想的な前残り展開
        else:
            score += 5
    
    elif running_style == '差し':
        if nige_count >= 3 or pace == 'ハイ':
            score += 7  # ハイペース → 差し有利
        elif pace == 'スロー':
            score += 3  # スローペース → 差し不利
        else:
            score += 5
    
    elif running_style == '追込':
        if pace == 'ハイ':
            score += 6  # ハイペース → 追込チャンス
        elif head_count >= 12:
            score += 5  # 大レース → 展開が向く
        else:
            score += 3
    
    else:  # 不明
        score += 2
    
    # 2. 枠順適性（8点）
    if running_style == '逃げ':
        if waku <= 3:
            score += 6  # 内枠 → 先頭に立ちやすい
        else:
            score += 2
    
    elif running_style == '先行':
        if 2 <= waku <= 5:
            score += 6  # 中枠 → 理想的
        else:
            score += 4
    
    elif running_style in ['差し', '追込']:
        if waku >= 6:
            score += 6  # 外枠 → 外を回って伸びやすい
        else:
            score += 3
    
    else:  # 不明
        score += 2
    
    # 頭数による補正
    if head_count >= 14:  # 大レース
        if running_style in ['差し', '追込'] and waku >= 6:
            score += 2  # 外枠の差し・追込がさらに有利
    elif head_count <= 8:  # 少頭数
        if running_style in ['逃げ', '先行'] and waku <= 4:
            score += 2  # 内枠の逃げ・先行が有利
    
    # 3. ペース予測（7点）
    if pace == 'スロー':
        if running_style in ['逃げ', '先行']:
            score += 5  # スローペース → 前有利
        else:
            score += 2
    
    elif pace == 'ハイ':
        if running_style in ['差し', '追込']:
            score += 5  # ハイペース → 差し・追込有利
        else:
            score += 2
    
    else:  # ミドル
        score += 3.5  # 中立
    
    return round(min(25, score), 1)


def calculate_des_score(horse: Dict, race_info: Dict, race_analysis: Dict) -> Dict:
    """
    DESスコアを計算（新配点: A30, B25, C20, D25）
    """
    race_distance = race_info.get('距離', 1400)
    
    a_score = calculate_a_score(horse)
    b_score = calculate_b_score(horse, race_distance)
    c_score = calculate_c_score(horse)
    d_score = calculate_d_score(horse, race_info, race_analysis)
    
    total = a_score + b_score + c_score + d_score
    
    # 信頼度判定（データ品質も考慮）
    past_race_count = len(horse.get('past_races', []))
    
    if total >= 80 and past_race_count >= 3:
        confidence = '高'
    elif total >= 60 and past_race_count >= 2:
        confidence = '中'
    elif total >= 40 and past_race_count >= 1:
        confidence = '低'
    else:
        confidence = '極低'
    
    return {
        'A_過去実績': a_score,
        'B_距離馬場適性': b_score,
        'C_騎手厩舎': c_score,
        'D_展開適性': d_score,
        'total': round(total, 1),
        '信頼度': confidence
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python calculate_des_score.py <ymd>")
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
    
    print(f"📊 DESスコア計算開始: {len(races)}レース")
    print("-" * 50)
    
    for race in races:
        race_id = race.get('race_id', '')
        race_name = race.get('レース名', 'N/A')
        horses = race.get('horses', [])
        
        print(f"🏇 {race_name} ({race_id}): {len(horses)}頭")
        
        # 各馬の脚質を推定
        for horse in horses:
            past_races = horse.get('past_races', [])
            horse['推定脚質'] = estimate_running_style(past_races)
        
        # レース全体の展開を分析
        race_analysis = analyze_race_pace(horses)
        race['レース分析'] = race_analysis
        
        print(f"  脚質構成: {race_analysis['脚質構成']}")
        print(f"  予想ペース: {race_analysis['予想ペース']}")
        
        # 各馬のDESスコアを計算
        for horse in horses:
            des_score = calculate_des_score(horse, race, race_analysis)
            horse['des_score'] = des_score
        
        # スコア順にソート
        horses.sort(key=lambda h: h.get('des_score', {}).get('total', 0), reverse=True)
        
        # 上位3頭を表示
        for i, horse in enumerate(horses[:3], 1):
            score = horse.get('des_score', {})
            print(f"  {i}位: {horse.get('馬番', '?')}番 {horse.get('馬名', 'N/A')} "
                  f"{score.get('total', 0)}点 ({score.get('信頼度', '?')})")
    
    # 結果を保存
    with open(input_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("-" * 50)
    print(f"✅ 完了: {input_file} を更新しました")


if __name__ == '__main__':
    main()
