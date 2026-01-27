#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_select.py - 当日のrace_idを自動取得（修正版 v3）
- コマンドライン引数対応
"""

import sys
import re
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# 場コード → 場名のマッピング（NAR地方競馬）
JYO_CODE_TO_NAME = {
    "30": "門別",
    "35": "盛岡",
    "36": "水沢",
    "42": "浦和",
    "43": "船橋",
    "44": "大井",
    "45": "川崎",
    "46": "金沢",
    "47": "笠松",
    "48": "名古屋",
    "50": "園田",
    "51": "姫路",
    "54": "高知",
    "55": "佐賀",
    "65": "帯広ば"
}

RACE_ID_RE = re.compile(r"race_id=(\d{12})")

def http_get(url: str, timeout=20) -> str:
    """HTTP GET リクエスト"""
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    
    print(f"📡 fetch_url: {url}")
    print(f"📊 status: {r.status_code}")
    print(f"📏 len: {len(r.text)}")
    
    r.raise_for_status()
    return r.text

def race_no_from_race_id(race_id: str):
    """race_idの末尾2桁からレース番号を取得"""
    try:
        n = int(race_id[-2:])
        if 1 <= n <= 12:
            return n
    except Exception:
        pass
    return None

def get_venue_name(jyo_code: str) -> str:
    """場コードから場名を取得"""
    return JYO_CODE_TO_NAME.get(jyo_code, f"場コード{jyo_code}")

def get_raceid_map_for_day(ymd: str) -> tuple:
    """
    指定日の全場のrace_idを取得して、場ごとに分類して返す
    """
    url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}"
    html = http_get(url)
    
    print(f"🔍 contains 'race_id='?: {'race_id=' in html}")
    
    # race_id 抽出（12桁）
    race_ids = list(dict.fromkeys(RACE_ID_RE.findall(html)))
    print(f"📊 race_ids count: {len(race_ids)}")
    print(f"📋 race_ids head: {race_ids[:5]}")
    
    # 場ごとに分類
    races_by_jyo = {}
    race_list = []  # ← 後続スクリプト用のリスト
    
    for rid in race_ids:
        jyo_cd = rid[4:6]  # race_idの5〜6文字目が場コード
        rno = race_no_from_race_id(rid)
        
        if rno is None:
            continue
        
        # 場別集計用
        if jyo_cd not in races_by_jyo:
            races_by_jyo[jyo_cd] = {
                "name": get_venue_name(jyo_cd),
                "race_id_map": {}
            }
        
        races_by_jyo[jyo_cd]["race_id_map"][rno] = rid
        
        # 後続スクリプト用リスト
        race_list.append({
            "race_id": rid,
            "race_info": {
                "venue": get_venue_name(jyo_cd),
                "venue_code": jyo_cd,
                "race_no": rno,
                "レース名": f"{rno}R"  # ← 仮のレース名
            }
        })
    
    return races_by_jyo, race_ids, race_list

def main():
    # コマンドライン引数から日付を取得（なければ今日）
    if len(sys.argv) > 1:
        ymd = sys.argv[1]
        print(f"📅 指定された日付: {ymd}")
    else:
        jst = ZoneInfo("Asia/Tokyo")
        ymd = datetime.now(jst).strftime("%Y%m%d")
        print(f"📅 今日の日付（自動取得）: {ymd}")
    
    print("=" * 60)
    
    # 全場のrace_id取得
    races_by_jyo, all_race_ids, race_list = get_raceid_map_for_day(ymd)
    
    # 開催場数とレース数を表示
    print("\n" + "=" * 60)
    print(f"✅ 開催場数: {len(races_by_jyo)}")
    for jyo_cd, data in sorted(races_by_jyo.items()):
        print(f"  📍 {data['name']} ({jyo_cd}): {len(data['race_id_map'])}R")
    
    print(f"\n✅ 総レース数: {len(all_race_ids)}")
    print("=" * 60)
    
    # JSON 出力（後続スクリプト用）
    jst = ZoneInfo("Asia/Tokyo")
    output = {
        "date": ymd,
        "generated_at": datetime.now(jst).isoformat(),
        "total_races": len(all_race_ids),
        "total_venues": len(races_by_jyo),
        "race_ids": all_race_ids,  # ← fetch_shutuba.py 用
        "selected_predictions": race_list,  # ← calculate_des_score.py 用
        "races_by_venue": races_by_jyo  # ← 参考用
    }
    
    # ファイル出力
    output_file = "today_jobs.latest.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ {output_file} created")
    print(f"📊 race_ids: {len(all_race_ids)}件")
    print(f"📊 selected_predictions: {len(race_list)}件")
    
    # サンプル表示
    if race_list:
        print("\n📋 サンプル（最初の3件）:")
        for i, race in enumerate(race_list[:3], 1):
            print(f"  {i}. {race['race_info']['venue']} {race['race_info']['race_no']}R - {race['race_id']}")
    
    # 終了
    print("\n✅ 処理完了")
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
