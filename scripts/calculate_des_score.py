#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DESスコア計算スクリプト

race_data_{ymd}.json から各馬の過去走データを読み込み、
A～Dの4軸でスコアを計算してdes_scoreフィールドを更新する

スコア構造（100点満点）:
- A 過去実績: 40点
- B 血統・適性: 30点
- C 騎手・厩舎: 20点
- D 展開適性: 10点
"""

import json
import sys
from pathlib import Path
import shutil

# ====================================================================
# A. 過去実績スコア（40点満点）
# ====================================================================
def calculate_past_performance_score(horse, race_info):
    """
    過去実績スコアを計算
    
    Args:
        horse (dict): 馬データ
        race_info (dict): レース情報
    
    Returns:
        float: 過去実績スコア（0～40点）
    """
    score = 0.0
    past_races = horse.get('past_races', [])
    
    if not past_races:
        return score
    
    # 1. 同距離・同馬場での成績（20点）
    target_distance = race_info.get('距離', 0)
    target_track = race_info.get('トラック', '')
    
    same_condition_score = 0
    for race in past_races:
        race_distance = int(race.get('距離', 0))
        race_track = race.get('距離種別', '')
        
        # 距離の許容範囲: ±200m
        if abs(race_distance - target_distance) <= 200 and race_track == target_track:
            # 着順を取得（例: "1" → 1着）
            try:
                rank_text = race.get('着順', '99')
                # "1(1)" のような表記から数字を抽出
                rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                
                if rank == 1:
                    same_condition_score += 10
                elif rank == 2:
                    same_condition_score += 7
                elif rank == 3:
                    same_condition_score += 3
            except:
                pass
    
    # 最大20点
    score += min(same_condition_score, 20)
    
    # 2. 近3走の着順推移（10点）
    recent_3_races = past_races[:3]
    if len(recent_3_races) >= 2:
        try:
            ranks = []
            for race in recent_3_races:
                rank_text = race.get('着順', '99')
                rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                ranks.append(rank)
            
            # 上昇傾向判定
            if len(ranks) >= 3:
                if ranks[0] < ranks[1] < ranks[2]:  # 新しい順なので逆
                    score += 10  # 上昇傾向
                elif ranks[0] <= 3 and ranks[1] <= 3 and ranks[2] <= 3:
                    score += 7  # 安定
        except:
            pass
    
    # 3. 通算勝率・連対率（10点）
    # 簡易計算: 過去5走での勝率・連対率
    if len(past_races) > 0:
        wins = 0
        places = 0
        
        for race in past_races[:5]:
            try:
                rank_text = race.get('着順', '99')
                rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                
                if rank == 1:
                    wins += 1
                    places += 1
                elif rank == 2:
                    places += 1
            except:
                pass
        
        win_rate = wins / len(past_races[:5])
        place_rate = places / len(past_races[:5])
        
        if win_rate >= 0.10:  # 10%以上
            score += 5
        if place_rate >= 0.30:  # 30%以上
            score += 5
    
    return round(score, 1)


# ====================================================================
# B. 血統・適性スコア（30点満点）
# ====================================================================
def calculate_pedigree_score(horse, race_info):
    """
    血統・適性スコアを計算
    
    Args:
        horse (dict): 馬データ
        race_info (dict): レース情報
    
    Returns:
        float: 血統・適性スコア（0～30点）
    """
    score = 0.0
    
    # 1. 父系・母系の距離適性（15点）
    # 簡易実装: 過去走での同距離帯での成績で判定
    target_distance = race_info.get('距離', 0)
    past_races = horse.get('past_races', [])
    
    same_distance_performance = 0
    same_distance_count = 0
    
    for race in past_races:
        race_distance = int(race.get('距離', 0))
        
        # 距離帯判定（±300m）
        if abs(race_distance - target_distance) <= 300:
            same_distance_count += 1
            try:
                rank_text = race.get('着順', '99')
                rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                
                if rank <= 3:
                    same_distance_performance += 1
            except:
                pass
    
    if same_distance_count > 0:
        performance_rate = same_distance_performance / same_distance_count
        
        if performance_rate >= 0.5:  # 50%以上で好成績
            score += 15  # 適性○
        elif performance_rate >= 0.3:
            score += 8   # 適性△
    
    # 2. ダート/芝の血統適性（10点）
    target_track = race_info.get('トラック', '')
    
    track_performance = 0
    track_count = 0
    
    for race in past_races:
        race_track = race.get('距離種別', '')
        
        if race_track == target_track:
            track_count += 1
            try:
                rank_text = race.get('着順', '99')
                rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                
                if rank <= 3:
                    track_performance += 1
            except:
                pass
    
    if track_count > 0:
        track_rate = track_performance / track_count
        
        if track_rate >= 0.4:  # 40%以上
            score += 10
        elif track_rate >= 0.2:
            score += 5
    
    # 3. 馬体重推移の安定性（5点）
    if len(past_races) >= 2:
        try:
            # 最新の馬体重
            latest_weight_text = past_races[0].get('馬体重', '0(0)')
            latest_weight = int(latest_weight_text.split('(')[0])
            
            # 前走の馬体重
            prev_weight_text = past_races[1].get('馬体重', '0(0)')
            prev_weight = int(prev_weight_text.split('(')[0])
            
            weight_diff = abs(latest_weight - prev_weight)
            
            if weight_diff <= 3:
                score += 5
            elif weight_diff >= 10:
                score -= 3
        except:
            pass
    
    return round(score, 1)


# ====================================================================
# C. 騎手・厩舎スコア（20点満点）
# ====================================================================
def calculate_jockey_trainer_score(horse, race_info):
    """
    騎手・厩舎スコアを計算
    
    Args:
        horse (dict): 馬データ
        race_info (dict): レース情報
    
    Returns:
        float: 騎手・厩舎スコア（0～20点）
    """
    score = 0.0
    
    # 1. 騎手の当該コース成績（10点）
    jockey = horse.get('騎手', '')
    past_races = horse.get('past_races', [])
    
    if jockey:
        jockey_wins = 0
        jockey_places = 0
        jockey_total = 0
        
        for race in past_races:
            if race.get('騎手', '') == jockey:
                jockey_total += 1
                try:
                    rank_text = race.get('着順', '99')
                    rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                    
                    if rank == 1:
                        jockey_wins += 1
                    if rank <= 2:
                        jockey_places += 1
                except:
                    pass
        
        if jockey_total > 0:
            jockey_win_rate = jockey_wins / jockey_total
            
            if jockey_win_rate >= 0.15:  # 15%以上
                score += 10
            elif jockey_win_rate >= 0.05:
                score += 5
    
    # 2. 厩舎の直近調整成績（10点）
    trainer = horse.get('厩舎', '')
    
    if trainer and len(past_races) > 0:
        # 過去5走での連対率で判定
        trainer_places = 0
        
        for race in past_races[:5]:
            try:
                rank_text = race.get('着順', '99')
                rank = int(rank_text.split('(')[0]) if '(' in rank_text else int(rank_text)
                
                if rank <= 2:
                    trainer_places += 1
            except:
                pass
        
        place_rate = trainer_places / len(past_races[:5])
        
        if place_rate >= 0.30:  # 30%以上
            score += 10
        elif place_rate >= 0.10:
            score += 5
    
    return round(score, 1)


# ====================================================================
# D. 展開適性スコア（10点満点）
# ====================================================================
def calculate_race_style_score(horse, race_info):
    """
    展開適性スコアを計算
    
    Args:
        horse (dict): 馬データ
        race_info (dict): レース情報
    
    Returns:
        float: 展開適性スコア（0～10点）
    """
    score = 0.0
    
    # 1. AI展開予測との相性（7点）
    # 簡易実装: 脚質推定
    past_races = horse.get('past_races', [])
    
    if len(past_races) > 0:
        # コーナー通過順から脚質を推定
        front_runner_count = 0
        closer_count = 0
        
        for race in past_races[:3]:
            corner_position = race.get('コーナー通過順', '')
            
            if corner_position:
                try:
                    # "1-1-1-1" のような形式から最初の位置を取得
                    first_position = int(corner_position.split('-')[0])
                    
                    if first_position <= 3:
                        front_runner_count += 1
                    elif first_position >= 8:
                        closer_count += 1
                except:
                    pass
        
        # 脚質判定
        if front_runner_count >= 2:
            score += 7  # 逃げ・先行
        elif closer_count >= 2:
            score += 7  # 差し・追込
        else:
            score += 3  # 汎用
    
    # 2. 枠順・脚質の有利度（3点）
    waku = horse.get('枠番', 0)
    
    if waku:
        # 簡易判定: 内枠（1～3）または外枠（6～8）
        if waku <= 3 or waku >= 6:
            score += 3
    
    return round(score, 1)


# ====================================================================
# 総合スコア計算
# ====================================================================
def calculate_des_score(horse, race_info):
    """
    DES総合スコアを計算
    
    Args:
        horse (dict): 馬データ
        race_info (dict): レース情報
    
    Returns:
        dict: des_score（A～D + total + 信頼度）
    """
    a_score = calculate_past_performance_score(horse, race_info)
    b_score = calculate_pedigree_score(horse, race_info)
    c_score = calculate_jockey_trainer_score(horse, race_info)
    d_score = calculate_race_style_score(horse, race_info)
    
    total = a_score + b_score + c_score + d_score
    
    # 信頼度判定
    if total >= 75:
        confidence = "高"
    elif total >= 65:
        confidence = "中"
    elif total >= 50:
        confidence = "低"
    else:
        confidence = "極低"
    
    return {
        "A_過去実績": a_score,
        "B_距離馬場適性": b_score,
        "C_騎手厩舎": c_score,
        "D_展開適性": d_score,
        "total": round(total, 1),
        "信頼度": confidence
    }


# ====================================================================
# メイン処理
# ====================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python calculate_des_score.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    
    if not Path(input_file).exists():
        print(f"[ERROR] {input_file} が見つかりません")
        sys.exit(1)
    
    # バックアップ作成
    backup_file = f"race_data_{ymd}.json.des_bak"
    shutil.copy(input_file, backup_file)
    print(f"[INFO] バックアップを作成しました: {backup_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        race_data = json.load(f)
    
    print(f"[INFO] {input_file} を読み込みました")
    print(f"[INFO] レース数: {len(race_data.get('races', []))}")
    
    # DESスコア計算カウンター
    total_horses = 0
    calculated_count = 0
    
    # 各レースを処理
    for race in race_data["races"]:
        race_id = race["race_id"]
        
        print(f"\n[INFO] レース {race_id} のDESスコアを計算中...")
        
        # 各馬のDESスコアを計算
        for horse in race.get("horses", []):
            horse_name = horse.get('馬名', '不明')
            
            # DESスコア計算
            des_score = calculate_des_score(horse, race)
            
            # 馬データに追加
            horse["des_score"] = des_score
            
            total_horses += 1
            calculated_count += 1
            
            print(f"  ✅ {horse_name}: {des_score['total']}/100点 (信頼度: {des_score['信頼度']})")
            print(f"     A:{des_score['A_過去実績']} B:{des_score['B_距離馬場適性']} C:{des_score['C_騎手厩舎']} D:{des_score['D_展開適性']}")
    
    # 結果を保存
    output_file = input_file
    
    print(f"\n[INFO] 保存前の確認:")
    print(f"  - 対象馬数: {total_horses}")
    print(f"  - 計算完了: {calculated_count}")
    print(f"  - 保存先: {output_file}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(race_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] {output_file} にDESスコアを保存しました")
    
    # 保存後の確認
    with open(output_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    
    # des_score フィールドの存在確認
    has_des_score = False
    sample_score = None
    
    for race in saved_data.get("races", []):
        for horse in race.get("horses", []):
            if "des_score" in horse and horse["des_score"].get("total", 0) > 0:
                has_des_score = True
                sample_score = horse["des_score"]
                break
        if has_des_score:
            break
    
    if has_des_score:
        print(f"[SUCCESS] des_score フィールドの存在を確認しました")
        print(f"[SAMPLE] {sample_score}")
    else:
        print(f"[WARN] des_score フィールドが正しく設定されていない可能性があります")
    
    print(f"\n✅ 完了")


if __name__ == "__main__":
    main()
