#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
過去走データ取得スクリプト（デバッグ版）

馬柱ページ（shutuba_past.html）から各馬の過去5走データを取得し、
race_data_{ymd}.json に追加する
"""

import json
import re
import sys
import time
from pathlib import Path
import shutil

import requests
from bs4 import BeautifulSoup

# ====================================================================
# 設定
# ====================================================================
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ====================================================================
# HTTP取得（共通関数）
# ====================================================================
def http_get(url, encoding="EUC-JP", timeout=10):
    """
    HTTP GET リクエストを送信
    
    Args:
        url (str): 取得対象URL
        encoding (str): 文字エンコーディング
        timeout (int): タイムアウト秒数
    
    Returns:
        str: レスポンステキスト（成功時）
        None: 失敗時
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout
        )
        resp.raise_for_status()
        resp.encoding = encoding
        return resp.text
    except Exception as e:
        print(f"[ERROR] HTTP GET failed: {url} -> {e}", file=sys.stderr)
        return None


# ====================================================================
# 馬柱ページ解析
# ====================================================================
def parse_past_races_html(html, horse_id):
    """
    馬柱ページ（shutuba_past.html）のHTMLを解析し、
    指定した horse_id の過去走データを抽出
    
    Args:
        html (str): 馬柱ページのHTML
        horse_id (str): 対象馬のhorse_id
    
    Returns:
        list: 過去走データのリスト
    """
    soup = BeautifulSoup(html, "html.parser")
    past_races = []
    
    # 馬名リンクを探して、該当馬のブロックを特定
    horse_link = soup.find("a", href=lambda x: x and f"/horse/{horse_id}" in x)
    if not horse_link:
        print(f"[WARN] horse_id={horse_id} のリンクが見つかりません")
        return past_races
    
    # <tr class="HorseList"> 要素を取得
    tr = horse_link.find_parent("tr", class_="HorseList")
    if not tr:
        print(f"[WARN] horse_id={horse_id} の <tr> が見つかりません")
        return past_races
    
    # tr 要素全体のテキストを取得
    text = tr.get_text(separator="\n", strip=True)
    
    # レースデータのパターン（改行区切り）
    pattern = re.compile(
        r"(\d{4}\.\d{2}\.\d{2})\s+(\S+)\s*\n"  # 開催日 競馬場
        r"(\d+)\s*\n"                        # レース番号
        r"[^\n]*\n"                          # レース条件（スキップ）
        r"(ダ|芝)(\d+)\s+([\d:\.]+)\s*\n"  # 距離 タイム
        r"(\S+)\s*\n"                       # 馬場状態
        r"(\d+)頭\s+(\d+)番\s+(\d+)人\s+(\S+)\s+([\d\.]+)\s*\n"  # 頭数 枠番 人気 騎手 斤量
        r"([\d\-]+)\s+\(([\d\.]+)\)\s+(\d+\([\+\-]?\d+\))"  # コーナー 上り 馬体重
    )
    
    for match in pattern.finditer(text):
        past_races.append({
            "race_date": match.group(1),
            "venue": match.group(2),
            "race_num": match.group(3),
            "distance": f"{match.group(4)}{match.group(5)}",
            "time": match.group(6),
            "track_condition": match.group(7),
            "field_size": f"{match.group(8)}頭",
            "post_position": f"{match.group(9)}番",
            "popularity": f"{match.group(10)}人",
            "jockey": match.group(11),
            "weight": match.group(12),
            "corner_positions": match.group(13),
            "last_3f": match.group(14),
            "horse_weight": match.group(15)
        })
    
    return past_races


# ====================================================================
# メイン処理
# ====================================================================
def main():
    """
    メイン処理
    
    1. race_data_{ymd}.json を読み込み
    2. 各レースの馬柱ページから過去走データを取得
    3. race_data_{ymd}.json に past_races を追加
    """
    # コマンドライン引数から ymd を取得
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python fetch_past_races.py <ymd>", file=sys.stderr)
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    
    # race_data_{ymd}.json を読み込み
    if not Path(input_file).exists():
        print(f"[ERROR] {input_file} が見つかりません", file=sys.stderr)
        sys.exit(1)
    
    # バックアップを作成
    backup_file = f"{input_file}.backup"
    shutil.copy(input_file, backup_file)
    print(f"[INFO] バックアップを作成しました: {backup_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        race_data = json.load(f)
    
    print(f"[INFO] {input_file} を読み込みました")
    print(f"[DEBUG] レース数: {len(race_data.get('races', []))}")
    
    # 過去走データ取得カウンター
    total_horses = 0
    total_past_races = 0
    
    # 各レースを処理
    for race in race_data["races"]:
        race_id = race["race_id"]
        print(f"\n[INFO] レース {race_id} の過去走データを取得中...")
        
        # 馬柱ページのURL
        past_url = f"https://nar.netkeiba.com/race/shutuba_past.html?race_id={race_id}"
        
        # HTML取得
        html = http_get(past_url)
        if not html:
            print(f"[WARN] {race_id} の馬柱ページ取得失敗")
            continue
        
        # 各馬の過去走データを取得
        for horse in race.get("horses", []):
            horse_id = horse.get("horse_id")
            if not horse_id:
                print(f"[WARN] {horse.get('馬名', '不明')} の horse_id が見つかりません")
                continue
            
            # 過去走データを抽出
            past_races = parse_past_races_html(html, horse_id)
            
            # 馬データに追加
            horse["past_races"] = past_races
            
            total_horses += 1
            total_past_races += len(past_races)
            
            print(f"  - {horse['馬名']}: {len(past_races)}走分取得")
        
        # レート制限（1秒待機）
        time.sleep(1)
    
    # 結果を保存
    output_file = input_file
    
    print(f"\n[DEBUG] 保存前の確認:")
    print(f"  - 対象馬数: {total_horses}")
    print(f"  - 取得過去走数: {total_past_races}")
    print(f"  - 保存先: {output_file}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(race_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] {output_file} に過去走データを保存しました")
    
    # 保存後の確認
    with open(output_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    
    # past_races フィールドの存在確認
    has_past_races = False
    for race in saved_data.get("races", []):
        for horse in race.get("horses", []):
            if "past_races" in horse:
                has_past_races = True
                break
        if has_past_races:
            break
    
    if has_past_races:
        print(f"[SUCCESS] past_races フィールドの存在を確認しました")
    else:
        print(f"[ERROR] past_races フィールドが見つかりません！")
        sys.exit(1)


if __name__ == "__main__":
    main()
