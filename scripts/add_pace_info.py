#!/usr/bin/env python3
"""
レース結果記録時に展開情報を追加するスクリプト
既存のrecord_results.pyを拡張
"""

import json
import sys
from collections import Counter

def analyze_pace_from_horses(horses):
    """
    出走馬の脚質からレース展開を予測
    
    Args:
        horses: 馬データのリスト
        
    Returns:
        str: 'ハイペース', 'ミドルペース', 'スローペース'
    """
    runstyles = [h.get('推定脚質', '不明') for h in horses if '推定脚質' in h]
    
    if not runstyles:
        return 'ミドルペース'
    
    counter = Counter(runstyles)
    nige_count = counter.get('逃げ', 0)
    senkou_count = counter.get('先行', 0)
    total = len(runstyles)
    
    # 逃げ馬が3頭以上、または逃げ+先行が50%以上
    if nige_count >= 3 or (nige_count + senkou_count) / total >= 0.5:
        return 'ハイペース'
    # 逃げ馬が0-1頭
    elif nige_count <= 1:
        return 'スローペース'
    else:
        return 'ミドルペース'


def add_pace_info_to_results(race_data_file, results_file, output_file):
    """
    結果データに展開情報を追加
    
    Args:
        race_data_file: race_data_YYYYMMDD.json
        results_file: latest_results.json または results_YYYYMMDD.json
        output_file: 出力先ファイル
    """
    # レースデータを読み込み
    try:
        with open(race_data_file, 'r', encoding='utf-8') as f:
            race_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ レースデータが見つかりません: {race_data_file}")
        return False
    
    # 結果データを読み込み
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    except FileNotFoundError:
        print(f"❌ 結果データが見つかりません: {results_file}")
        return False
    
    # レースIDごとの馬データをマップ作成
    race_horses_map = {}
    for race in race_data.get('races', []):
        race_id = race.get('race_id')
        if race_id:
            race_horses_map[race_id] = race.get('horses', [])
    
    # 各結果に展開情報を追加
    updated_count = 0
    for result in results.get('races', []):
        race_id = result.get('race_id')
        if race_id and race_id in race_horses_map:
            horses = race_horses_map[race_id]
            predicted_pace = analyze_pace_from_horses(horses)
            result['predicted_pace'] = predicted_pace
            updated_count += 1
    
    # 出力
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 展開情報を追加しました: {updated_count} レース")
    print(f"📄 出力ファイル: {output_file}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python add_pace_info.py <race_data.json> <results.json> <output.json>")
        sys.exit(1)
    
    race_data_file = sys.argv[1]
    results_file = sys.argv[2]
    output_file = sys.argv[3]
    
    success = add_pace_info_to_results(race_data_file, results_file, output_file)
    sys.exit(0 if success else 1)
