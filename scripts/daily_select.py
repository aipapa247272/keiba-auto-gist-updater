#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_select.py - 当日のrace_idを自動取得（修正版）
"""

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
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    
    print(f"fetch_url: {url}")
    print(f"status: {r.status_code}")
    print(f"len: {len(r.text)}")
    
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

def get_raceid_map_for_day(ymd: str) -> dict:
    """
    指定日の全場のrace_idを取得して、場ごとに分類して返す
    """
    url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}"
    html = http_get(url)
    
    print(f"contains race_id=?: {'race_id=' in html}")
    
    # race_id 抽出（12桁）
    race_ids = list(dict.fromkeys(RACE_ID_RE.findall(html)))
    print(f"race_ids count: {len(race_ids)}")
    print(f"race_ids head: {race_ids[:5]}")
    
    # 場ごとに分類
    races_by_jyo = {}
    
    for rid in race_ids:
        jyo_cd = rid[4:6]  # race_idの5〜6文字目が場コード
        rno = race_no_from_race_id(rid)
        
        if rno is None:
            continue
        
        if jyo_cd not in races_by_jyo:
            races_by_jyo[jyo_cd] = {
                "name": JYO_CODE_TO_NAME.get(jyo_cd, f"場コード{jyo_cd}"),
                "race_id_map": {}
            }
        
        races_by_jyo[jyo_cd]["race_id_map"][rno] = rid
    
    return races_by_jyo, race_ids  # race_idsも返す

def main():
    # 今日の日付（JST）
    jst = ZoneInfo("Asia/Tokyo")
    ymd = datetime.now(jst).strftime("%Y%m%d")
    
    print(f"📅 対象日: {ymd}")
    
    # 全場のrace_id取得
    races_by_jyo, all_race_ids = get_raceid_map_for_day(ymd)
    
    print(f"✅ 開催場数: {len(races_by_jyo)}")
    for jyo_cd, data in races_by_jyo.items():
        print(f"  {jyo_cd} ({data['name']}): {len(data['race_id_map'])}R")
    
    print(f"✅ 総レース数: {len(all_race_ids)}")
    
    # JSON 出力（fetch_shutuba.py が期待する形式）
    output = {
        "ymd": ymd,
        "race_ids": all_race_ids,  # ← これが重要！
        "races_by_venue": races_by_jyo  # 場別データも残す（参考用）
    }
    
    with open("today_jobs.latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("✅ today_jobs.latest.json created")
    print(f"📊 race_ids: {len(all_race_ids)}件")

if __name__ == "__main__":
    main()
