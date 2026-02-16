#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
select_predictions.py - レース選定・買い目生成スクリプト

race_data_{ymd}.json から DESスコアに基づいてレースを選定し、
買い目と投資額を計算して final_predictions_{ymd}.json を出力する

統合ルール準拠:
- 基本3レース、最大5レース
- 波乱度: 低/中/高
- 買い目: 三連複フォーメーション（軸3頭、相手6～7頭）
- 投資配分: 低60%、中40%、高0%（見送り）
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import shutil


# ====================================================================
# 波乱度判定
# ====================================================================
def calculate_turbulence(race):
    """
    波乱度を判定
    
    Args:
        race (dict): レースデータ
    
    Returns:
        str: 波乱度（低/中/高）
    """
    horses = race.get('horses', [])
    
    if not horses:
        return "中"
    
    # DESスコアを取得
    scores = []
    for horse in horses:
        des_score = horse.get('des_score', {})
        total = des_score.get('total', 0)
        scores.append(total)
    
    if not scores:
        return "中"
    
    scores.sort(reverse=True)
    
    # 上位3頭の平均スコア
    top_3_avg = sum(scores[:3]) / 3 if len(scores) >= 3 else sum(scores) / len(scores)
    
    # スコア差（1位と3位の差）
    score_diff = scores[0] - scores[2] if len(scores) >= 3 else 0
    
    # 波乱度判定
    if top_3_avg >= 70 and score_diff >= 15:
        return "低"  # 本命有利
    elif top_3_avg >= 60 or score_diff >= 10:
        return "中"  # 混戦
    else:
        return "高"  # 大波乱


# ====================================================================
# 買い目生成
# ====================================================================
def generate_betting_plan(race):
    """
    三連複フォーメーションの買い目を生成
    
    Args:
        race (dict): レースデータ
    
    Returns:
        dict: 買い目データ
    """
    horses = race.get('horses', [])
    
    # DESスコアでソート
    sorted_horses = sorted(
        horses, 
        key=lambda h: h.get('des_score', {}).get('total', 0), 
        reverse=True
    )
    
    # 上位10頭を選出
    top_10 = sorted_horses[:min(10, len(sorted_horses))]
    
    # 軸: 上位3頭（◎○▲）
    axis_horses = top_10[:3]
    
    # 相手: 4～10位（△）
    opponent_horses = top_10[3:10]
    
    # 買い目: 軸3頭BOX
    betting_plan = {
        "軸": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": ["◎", "○", "▲"][i],
                "スコア": h.get('des_score', {}).get('total', 0)
            }
            for i, h in enumerate(axis_horses)
        ],
        "相手": [
            {
                "馬番": h.get('馬番'),
                "馬名": h.get('馬名'),
                "評価": "△",
                "スコア": h.get('des_score', {}).get('total', 0)
            }
            for h in opponent_horses
        ],
        "買い目タイプ": "三連複フォーメーション（軸3頭BOX）",
        "組み合わせ数": 1  # 3頭BOX = 1通り
    }
    
    return betting_plan


# ====================================================================
# 投資額計算
# ====================================================================
def calculate_investment(selected_races, total_budget=10000):
    """
    波乱度に基づいて投資額を配分
    
    Args:
        selected_races (list): 選定されたレースリスト
        total_budget (int): 総予算
    
    Returns:
        dict: 投資配分
    """
    # 波乱度別にレースを分類
    low_turbulence = [r for r in selected_races if r['turbulence'] == '低']
    mid_turbulence = [r for r in selected_races if r['turbulence'] == '中']
    high_turbulence = [r for r in selected_races if r['turbulence'] == '高']
    
    # 波乱度高は見送り
    if high_turbulence:
        print(f"⚠️ 見送りレース: {len(high_turbulence)}レース（波乱度「高」のため）")
    
    # 投資対象レース
    investable_races = low_turbulence + mid_turbulence
    
    if not investable_races:
        return {
            "total_investment": 0,
            "low_investment": 0,
            "mid_investment": 0,
            "races": []
        }
    
    # 配分比率
    low_ratio = 0.60
    mid_ratio = 0.40
    
    # 各波乱度の予算
    low_budget = int(total_budget * low_ratio) if low_turbulence else 0
    mid_budget = int(total_budget * mid_ratio) if mid_turbulence else 0
    
    # レース数で均等配分
    low_per_race = low_budget // len(low_turbulence) if low_turbulence else 0
    mid_per_race = mid_budget // len(mid_turbulence) if mid_turbulence else 0
    
    # 100円単位に丸める
    low_per_race = (low_per_race // 100) * 100
    mid_per_race = (mid_per_race // 100) * 100
    
    # 投資額を設定
    race_investments = []
    
    for race in selected_races:
        if race['turbulence'] == '低':
            investment = low_per_race
        elif race['turbulence'] == '中':
            investment = mid_per_race
        else:  # 高
            investment = 0
        
        race_investments.append({
            "race_id": race['race_id'],
            "turbulence": race['turbulence'],
            "investment": investment
        })
    
    # 実際の総投資額
    actual_total = sum(r['investment'] for r in race_investments)
    
    return {
        "total_investment": actual_total,
        "low_investment": low_per_race * len(low_turbulence) if low_turbulence else 0,
        "mid_investment": mid_per_race * len(mid_turbulence) if mid_turbulence else 0,
        "races": race_investments
    }


# ====================================================================
# レース選定
# ====================================================================
def select_races(race_data, max_races=5):
    """
    DESスコアに基づいてレースを選定
    
    Args:
        race_data (dict): レースデータ
        max_races (int): 最大選定レース数
    
    Returns:
        list: 選定されたレース
    """
    races = race_data.get('races', [])
    
    if not races:
        print("[WARN] レースデータが空です")
        return []
    
    print(f"[INFO] 予想選定開始: {len(races)}レース")
    
    # 各レースの評価
    race_scores = []
    
    for race in races:
        horses = race.get('horses', [])
        
        if not horses:
            continue
        
        # DESスコアの統計
        scores = [h.get('des_score', {}).get('total', 0) for h in horses]
        
        if not scores:
            continue
        
        # 上位3頭の平均スコア
        sorted_scores = sorted(scores, reverse=True)
        top_3_avg = sum(sorted_scores[:3]) / 3 if len(sorted_scores) >= 3 else sum(sorted_scores) / len(sorted_scores)
        
        # データ品質スコア
        data_quality = len([h for h in horses if h.get('past_races', [])])
        
        # 評価点
        evaluation_score = top_3_avg + (data_quality * 2)
        
        race_scores.append({
            "race": race,
            "evaluation_score": evaluation_score,
            "top_3_avg": top_3_avg,
            "data_quality": data_quality
        })
    
    # 評価点でソート
    race_scores.sort(key=lambda x: x['evaluation_score'], reverse=True)
    
    # 上位レースを選定
    selected = []
    
    for item in race_scores[:max_races]:
        race = item['race']
        turbulence = calculate_turbulence(race)
        
        selected.append({
            "race_id": race['race_id'],
            "race_name": race.get('レース名', '不明'),
            "venue": race.get('競馬場', '不明'),
            "distance": race.get('距離', 0),
            "track": race.get('トラック', '不明'),
            "start_time": race.get('発走時刻', '不明'),
            "turbulence": turbulence,
            "evaluation_score": item['evaluation_score'],
            "top_3_avg": item['top_3_avg'],
            "data_quality": item['data_quality'],
            "betting_plan": generate_betting_plan(race)
        })
    
    print(f"[INFO] ✅ 予想対象: {len(selected)}レース")
    
    # 波乱度別の集計
    turbulence_count = {
        "低": len([r for r in selected if r['turbulence'] == '低']),
        "中": len([r for r in selected if r['turbulence'] == '中']),
        "高": len([r for r in selected if r['turbulence'] == '高'])
    }
    
    print(f"[INFO] 【波乱度別内訳】")
    print(f"  - 🟢 低: {turbulence_count['低']}レース (本命有利)")
    print(f"  - 🟡 中: {turbulence_count['中']}レース (拮抗)")
    print(f"  - 🔴 高: {turbulence_count['高']}レース (荒れる可能性)")
    
    return selected


# ====================================================================
# メイン処理
# ====================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python select_predictions.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    output_file = f"final_predictions_{ymd}.json"
    
    if not Path(input_file).exists():
        print(f"[ERROR] {input_file} が見つかりません")
        sys.exit(1)
    
    # データ読み込み
    with open(input_file, "r", encoding="utf-8") as f:
        race_data = json.load(f)
    
    print(f"[INFO] {input_file} を読み込みました")
    
    # レース選定
    selected_races = select_races(race_data, max_races=5)
    
    if not selected_races:
        print("[ERROR] 選定可能なレースがありません")
        sys.exit(1)
    
    # 投資額計算
    investment_plan = calculate_investment(selected_races, total_budget=12000)
    
    # 投資額を各レースに追加
    for race in selected_races:
        race_investment = next(
            (r for r in investment_plan['races'] if r['race_id'] == race['race_id']), 
            None
        )
        if race_investment:
            race['investment'] = race_investment['investment']
    
    # 出力データ作成
    output_data = {
        "ymd": ymd,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_races": len(race_data.get('races', [])),
        "selected_races": len(selected_races),
        "skipped_races": len(race_data.get('races', [])) - len(selected_races),
        "summary": {
            "turbulence": {
                "低": len([r for r in selected_races if r['turbulence'] == '低']),
                "中": len([r for r in selected_races if r['turbulence'] == '中']),
                "高": len([r for r in selected_races if r['turbulence'] == '高'])
            },
            "total_investment": investment_plan['total_investment']
        },
        "selected_predictions": selected_races
    }
    
    # 保存
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] {output_file} を生成しました")
    
    # latest_predictions.json も生成(フロントエンド用)
    latest_file = "latest_predictions.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"[SUCCESS] {latest_file} も生成しました")
    
    # サマリー表示
    print(f"\n# 📊 本日の予想サマリー")
    print(f"")
    print(f"**日付**: {ymd[:4]}/{ymd[4:6]}/{ymd[6:8]}")
    print(f"")
    print(f"- **総レース数**: {output_data['total_races']}レース")
    print(f"- **予想対象**: {output_data['selected_races']}レース")
    print(f"- **見送り**: {output_data['skipped_races']}レース")
    print(f"")
    print(f"【波乱度別内訳】")
    print(f"- 🟢 低: {output_data['summary']['turbulence']['低']}レース (本命有利)")
    print(f"- 🟡 中: {output_data['summary']['turbulence']['中']}レース (拮抗)")
    print(f"- 🔴 高: {output_data['summary']['turbulence']['高']}レース (荒れる可能性)")
    print(f"")
    print(f"【合計投資額】")
    print(f"💰 **¥{output_data['summary']['total_investment']:,}円** (投資OFFのため実購入なし)")
    print(f"")
    
    # 各レースの表示
    for i, race in enumerate(selected_races, 1):
        print(f"---")
        print(f"")
        print(f"## 🎯 予想 {i}")
        print(f"")
        print(f"📍 **{race['venue']} R{race['race_id'][-2:]} {race['race_name']}**")
        print(f"🏃 {race['track']} {race['distance']}m | ⏰ {race['start_time']}")
        print(f"🌊 波乱度: {'🟢' if race['turbulence'] == '低' else '🟡' if race['turbulence'] == '中' else '🔴'} {race['turbulence']} (拮抗)")
        print(f"")
        
        # 本命馬
        betting = race['betting_plan']
        for axis in betting['軸']:
            print(f"**{axis['評価']} 本命 {axis['馬番']} {axis['馬名']}**")
            print(f"📊 総合点: {axis['スコア']:.1f} / 100 ({_get_confidence(axis['スコア'])})")
        
        print(f"")
        
        # 対抗馬
        if betting['相手']:
            print(f"**{betting['相手'][0]['評価']} 対抗馬**")
            for opponent in betting['相手'][:3]:
                print(f"- {opponent['馬番']} {opponent['馬名']}: {opponent['スコア']:.1f}点")
        
        print(f"")
        print(f"【買い目提案】")
        print(f"💰 投資額: {race.get('investment', 0):,}円")
        print(f"")
        print(f"**3連複 {betting['買い目タイプ']}**")
        print(f"")
        print(f"【軸馬】")
        axis_numbers = [str(a['馬番']) for a in betting['軸']]
        print(f"🔵 {' '.join(axis_numbers)}")
        print(f"")
        print(f"【組み合わせ】")
        print(f"{'-'.join(axis_numbers)}")
        print(f"")
    
    print(f"---")
    print(f"\n✅ 完了")


def _get_confidence(score):
    """信頼度を取得"""
    if score >= 75:
        return "高"
    elif score >= 65:
        return "中"
    elif score >= 50:
        return "低"
    else:
        return "極低"


if __name__ == "__main__":
    main()
