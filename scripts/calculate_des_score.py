#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DESスコア計算スクリプト

過去走データから各馬の実力を評価し、100点満点のスコアを算出
- D: Distance（距離適性） - 35点
- E: Experience（経験値） - 30点
- S: Speed（スピード指数） - 35点
"""

import json
import sys
import re
from typing import Dict, List, Optional
from datetime import datetime


def parse_distance(distance: str) -> Optional[int]:
    """
    距離文字列を数値に変換
    例: 'ダ1300' -> 1300, '芝1600' -> 1600
    """
    if not distance:
        return None
    match = re.search(r'(\d+)', distance)
    return int(match.group(1)) if match else None


def parse_time(time_str: str) -> Optional[float]:
    """
    タイム文字列を秒数に変換
    例: '1:29.5' -> 89.5
    """
    if not time_str or ':' not in time_str:
        return None
    try:
        parts = time_str.split(':')
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    except:
        return None


def parse_last_3f(last_3f: str) -> Optional[float]:
    """
    上がり3F文字列を数値に変換
    例: '40.9' -> 40.9
    """
    if not last_3f:
        return None
    try:
        return float(last_3f)
    except:
        return None


def calculate_distance_score(past_races: List[Dict], current_distance: int) -> float:
    """
    距離適性スコアを計算（35点満点）
    
    評価項目:
    1. 同距離での経験（15点）
    2. 近似距離での経験（10点）
    3. 距離別成績（10点）
    """
    if not past_races or not current_distance:
        return 0.0
    
    score = 0.0
    same_distance_count = 0
    similar_distance_count = 0
    
    for race in past_races:
        distance = parse_distance(race.get('distance', ''))
        if not distance:
            continue
        
        diff = abs(distance - current_distance)
        
        # 同距離での経験（15点）
        if diff == 0:
            same_distance_count += 1
        
        # 近似距離での経験（±200m以内）（10点）
        if 0 < diff <= 200:
            similar_distance_count += 1
    
    # 同距離経験スコア（15点満点）
    # 3走以上で満点
    score += min(same_distance_count * 5, 15)
    
    # 近似距離経験スコア（10点満点）
    # 2走以上で満点
    score += min(similar_distance_count * 5, 10)
    
    # 距離別成績スコア（10点満点）
    # 同距離での着順を評価（実装予定）
    # 現時点では経験値ベースで簡易評価
    if same_distance_count > 0:
        score += min(same_distance_count * 3, 10)
    
    return min(score, 35.0)


def calculate_experience_score(past_races: List[Dict], current_venue: str, current_distance: int) -> float:
    """
    経験値スコアを計算（30点満点）
    
    評価項目:
    1. 総出走回数（10点）
    2. 当該競馬場での経験（10点）
    3. 当該距離での経験（10点）
    """
    if not past_races:
        return 0.0
    
    score = 0.0
    
    # 総出走回数（10点満点）
    # 5走以上で満点
    race_count = len(past_races)
    score += min(race_count * 2, 10)
    
    # 当該競馬場での経験（10点満点）
    venue_count = sum(1 for race in past_races if race.get('venue') == current_venue)
    # 3走以上で満点
    score += min(venue_count * 3.3, 10)
    
    # 当該距離での経験（10点満点）
    distance_count = 0
    for race in past_races:
        distance = parse_distance(race.get('distance', ''))
        if distance and abs(distance - current_distance) <= 100:
            distance_count += 1
    # 3走以上で満点
    score += min(distance_count * 3.3, 10)
    
    return min(score, 30.0)


def calculate_speed_score(past_races: List[Dict], current_distance: int) -> float:
    """
    スピード指数スコアを計算（35点満点）
    
    評価項目:
    1. タイム指数（15点）
    2. 上がり3F（10点）
    3. 前走との比較（10点）
    """
    if not past_races:
        return 0.0
    
    score = 0.0
    
    # タイム指数（15点満点）
    # 同距離または近似距離のタイムを評価
    same_distance_times = []
    for race in past_races:
        distance = parse_distance(race.get('distance', ''))
        time = parse_time(race.get('time', ''))
        if distance and time and abs(distance - current_distance) <= 200:
            # 距離補正（1mあたり0.1秒）
            corrected_time = time + (distance - current_distance) * 0.0001
            same_distance_times.append(corrected_time)
    
    if same_distance_times:
        # 最速タイムを評価
        best_time = min(same_distance_times)
        avg_time = sum(same_distance_times) / len(same_distance_times)
        
        # 簡易的なタイム評価（実際の競馬では標準タイムとの比較が必要）
        # ここでは平均タイムからの偏差で評価
        if best_time < avg_time * 0.98:  # 平均より2%以上速い
            score += 15
        elif best_time < avg_time:
            score += 10
        else:
            score += 5
    
    # 上がり3F（10点満点）
    last_3f_values = []
    for race in past_races[:3]:  # 直近3走
        last_3f = parse_last_3f(race.get('last_3f', ''))
        if last_3f:
            last_3f_values.append(last_3f)
    
    if last_3f_values:
        avg_last_3f = sum(last_3f_values) / len(last_3f_values)
        
        # 上がり3Fの評価（ダート1300m想定: 38秒台が優秀）
        if avg_last_3f < 39.0:
            score += 10
        elif avg_last_3f < 41.0:
            score += 7
        elif avg_last_3f < 43.0:
            score += 4
        else:
            score += 2
    
    # 前走との比較（10点満点）
    if len(past_races) >= 2:
        # 直近2走のタイムを比較
        recent_time_1 = parse_time(past_races[0].get('time', ''))
        recent_time_2 = parse_time(past_races[1].get('time', ''))
        
        if recent_time_1 and recent_time_2:
            if recent_time_1 < recent_time_2:  # 前走より改善
                score += 10
            elif recent_time_1 == recent_time_2:  # 維持
                score += 7
            else:  # 悪化
                score += 4
    
    return min(score, 35.0)


def calculate_des_score(horse: Dict, current_race_info: Dict) -> Dict:
    """
    各馬のDESスコアを計算
    
    Args:
        horse: 馬データ（past_races を含む）
        current_race_info: 今回のレース情報（距離、競馬場など）
    
    Returns:
        スコア詳細を含む辞書
    """
    past_races = horse.get('past_races', [])
    current_distance = parse_distance(current_race_info.get('距離', ''))
    current_venue = current_race_info.get('venue', '')  # 競馬場名（要追加）
    
    # 各スコアを計算
    distance_score = calculate_distance_score(past_races, current_distance)
    experience_score = calculate_experience_score(past_races, current_venue, current_distance)
    speed_score = calculate_speed_score(past_races, current_distance)
    
    # 総合スコア
    total_score = distance_score + experience_score + speed_score
    
    return {
        'horse_id': horse.get('horse_id'),
        '馬名': horse.get('馬名'),
        '枠番': horse.get('枠番'),
        '馬番': horse.get('馬番'),
        'distance_score': round(distance_score, 1),
        'experience_score': round(experience_score, 1),
        'speed_score': round(speed_score, 1),
        'total_score': round(total_score, 1),
        'past_race_count': len(past_races)
    }


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python calculate_des_score.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    
    print(f"[INFO] {input_file} を読み込んでいます...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] {input_file} が見つかりません")
        sys.exit(1)
    
    print(f"[DEBUG] レース数: {len(data.get('races', []))}")
    
    # 各レースのスコアを計算
    for race in data.get('races', []):
        race_id = race.get('race_id')
        race_info = race.get('race_info', {})
        horses = race.get('horses', [])
        
        print(f"\n[INFO] レース {race_id} のスコアを計算中...")
        print(f"  レース名: {race_info.get('レース名')}")
        print(f"  距離: {race_info.get('距離')}")
        print(f"  頭数: {len(horses)}")
        
        # 競馬場名を race_id から抽出（簡易的）
        # race_id の形式: 202654012501 -> 2026 54(場コード) 01(回) 25(日) 01(R)
        venue_code = race_id[4:6] if len(race_id) >= 6 else ''
        venue_map = {
            '54': '高知',
            '55': '佐賀',
            '65': '帯広',
            '50': '門別',
            '51': '盛岡',
            '52': '水沢',
            '53': '浦和',
            '56': '園田',
            '57': '名古屋',
            '58': '金沢',
            '59': '笠松',
        }
        race_info['venue'] = venue_map.get(venue_code, '')
        
        # 各馬のスコアを計算
        scores = []
        for horse in horses:
            if not horse.get('past_races'):
                print(f"  [WARN] {horse.get('馬名')} の過去走データがありません")
                continue
            
            score = calculate_des_score(horse, race_info)
            scores.append(score)
        
        # スコア順にソート
        scores.sort(key=lambda x: x['total_score'], reverse=True)
        
        # 結果を race に追加
        race['des_scores'] = scores
        
        # 上位3頭を表示
        print(f"\n  【スコア上位3頭】")
        for i, score in enumerate(scores[:3], 1):
            print(f"  {i}位: {score['馬番']}番 {score['馬名']}")
            print(f"      総合: {score['total_score']}点 (D:{score['distance_score']} E:{score['experience_score']} S:{score['speed_score']})")
    
    # 結果を保存
    output_file = f"race_data_{ymd}.json"
    print(f"\n[INFO] {output_file} に保存中...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"[SUCCESS] {output_file} にスコアを保存しました")


if __name__ == '__main__':
    main()
