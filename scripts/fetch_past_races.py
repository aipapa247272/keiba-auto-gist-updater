#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
過去走データ取得スクリプト（JRA/NAR両対応版）

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

# JRA場コード（中央競馬）
JRA_VENUE_CODES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]

# ====================================================================
# URL判別関数
# ====================================================================
def get_base_url(race_id):
    """
    race_id から JRA/NAR を判別し、適切なベースURLを返す
    
    Args:
        race_id (str): 12桁のレースID
    
    Returns:
        str: ベースURL
    """
    if not race_id or len(race_id) < 6:
        return "https://nar.netkeiba.com"
    
    venue_code = race_id[4:6]
    
    if venue_code in JRA_VENUE_CODES:
        return "https://race.netkeiba.com"
    else:
        return "https://nar.netkeiba.com"


# ====================================================================
# HTTP取得（共通関数）
# ====================================================================
def http_get(url, encoding=None, timeout=10):
    """
    HTTP GET リクエストを送信
    
    Args:
        url (str): 取得対象URL
        encoding (str|None): 文字エンコーディング。None の場合はURL/レスポンスから自動判定
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

        if encoding:
            resp.encoding = encoding
        else:
            content_type = (resp.headers.get("content-type") or "").lower()
            if "charset=" in content_type:
                resp.encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            elif "nar.netkeiba.com" in url or "utf-8" in content_type:
                resp.encoding = "utf-8"
            else:
                resp.encoding = resp.apparent_encoding or "utf-8"

        return resp.text
    except Exception as e:
        print(f"[ERROR] HTTP GET failed: {url} -> {e}", file=sys.stderr)
        return None


# ====================================================================
# 馬柱ページ解析
# ====================================================================
def _normalize_cell_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_past_race_from_text(text):
    text = _normalize_cell_text(text)
    if not text or not re.search(r"\d{4}\.\d{2}\.\d{2}", text):
        return None

    race = {
        "開催日": "",
        "競馬場": "",
        "レース番号": "",
        "距離種別": "",
        "距離": "",
        "タイム": "",
        "馬場状態": "",
        "頭数": "",
        "枠番": "",
        "人気": "",
        "騎手": "",
        "斤量": "",
        "コーナー通過順": "",
        "上り": "",
        "馬体重": ""
    }

    m = re.search(r"(\d{4}\.\d{2}\.\d{2})\s+([^\s]+)", text)
    if m:
        race["開催日"] = m.group(1)
        race["競馬場"] = m.group(2)

    m = re.search(r"\b(\d{1,2})R\b", text)
    if m:
        race["レース番号"] = m.group(1)
    else:
        m = re.search(r"\d{4}\.\d{2}\.\d{2}\s+[^\s]+\s+(\d{1,2})\b", text)
        if m:
            race["レース番号"] = m.group(1)

    m = re.search(r"(ダ|芝)(\d{3,4})", text)
    if m:
        race["距離種別"] = m.group(1)
        race["距離"] = m.group(2)

    m = re.search(r"(\d:\d{2}\.\d)", text)
    if m:
        race["タイム"] = m.group(1)

    for cond in ["不良", "稍重", "良", "重", "稍"]:
        if cond in text:
            race["馬場状態"] = cond
            break

    m = re.search(r"(\d+)頭\s+(\d+)番\s+(\d+)人", text)
    if m:
        race["頭数"] = m.group(1)
        race["枠番"] = m.group(2)
        race["人気"] = m.group(3)

    m = re.search(r"\d+頭\s+\d+番\s+\d+人\s+([^\d\s][^\d]*?)\s+(\d{2}(?:\.\d)?)\b", text)
    if m:
        race["騎手"] = m.group(1).strip()
        race["斤量"] = m.group(2)

    m = re.search(r"(\d+(?:-\d+){1,3})", text)
    if m:
        race["コーナー通過順"] = m.group(1)

    m = re.search(r"\((\d{2}\.\d)\)\s+(\d+\([+\-]?\d+\))", text)
    if m:
        race["上り"] = m.group(1)
        race["馬体重"] = m.group(2)
    else:
        m = re.search(r"(\d+\([+\-]?\d+\))", text)
        if m:
            race["馬体重"] = m.group(1)

    if not race["開催日"]:
        return None
    return race


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
    
    # NARページでは HorseList クラスが無いことがあるため一般trにフォールバック
    tr = horse_link.find_parent("tr", class_="HorseList")
    if not tr:
        tr = horse_link.find_parent("tr")
        if tr:
            print(f"[INFO] horse_id={horse_id} は一般trを使用して解析します")
    if not tr:
        print(f"[WARN] horse_id={horse_id} の <tr> が見つかりません")
        return past_races

    tds = tr.find_all("td")
    print(f"[DEBUG] horse_id={horse_id} td_count={len(tds)}")

    # まずは td 単位で抽出（NAR向け）
    for td in tds:
        td_text = td.get_text(" ", strip=True)
        if not re.search(r"\d{4}\.\d{2}\.\d{2}", td_text):
            continue
        race = _extract_past_race_from_text(td_text)
        if race:
            past_races.append(race)

    # td抽出で失敗した場合は行全体を日付ごとに分割して再試行
    if not past_races:
        row_text = tr.get_text(" ", strip=True)
        segments = [seg.strip() for seg in re.split(r"(?=\d{4}\.\d{2}\.\d{2})", row_text) if seg.strip()]
        for seg in segments:
            race = _extract_past_race_from_text(seg)
            if race:
                past_races.append(race)

    deduped = []
    seen = set()
    for race in past_races:
        key = (race.get("開催日", ""), race.get("競馬場", ""), race.get("レース番号", ""), race.get("距離", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(race)

    deduped = deduped[:5]
    if not deduped:
        print(f"[WARN] horse_id={horse_id} の過去走抽出に失敗しました")
    else:
        print(f"[DEBUG] horse_id={horse_id} parsed_past_races={len(deduped)}")

    return deduped


# ====================================================================
# メイン処理
# ====================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_past_races.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    input_file = f"race_data_{ymd}.json"
    
    if not Path(input_file).exists():
        print(f"[ERROR] {input_file} が見つかりません")
        sys.exit(1)
    
    # バックアップ作成
    backup_file = f"race_data_{ymd}.json.bak"
    shutil.copy(input_file, backup_file)
    print(f"[INFO] バックアップを作成しました: {backup_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        race_data = json.load(f)
    
    print(f"[INFO] {input_file} を読み込みました")
    print(f"[DEBUG] レース数: {len(race_data.get('races', []))}")
    
    # 過去走データ取得カウンター
    total_horses = 0
    total_past_races = 0
    total_warning_horses = 0
    jra_count = 0
    nar_count = 0
    
    # 各レースを処理
    for race in race_data["races"]:
        race_id = race["race_id"]
        
        # JRA/NAR判別
        base_url = get_base_url(race_id)
        venue_type = "JRA" if "race.netkeiba.com" in base_url else "NAR"
        
        if venue_type == "JRA":
            jra_count += 1
        else:
            nar_count += 1
        
        print(f"\n[INFO] [{venue_type}] レース {race_id} の過去走データを取得中...")
        
        # 馬柱ページのURL
        past_url = f"{base_url}/race/shutuba_past.html?race_id={race_id}"
        print(f"[DEBUG] URL: {past_url}")
        
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
            if not past_races:
                warning_reason = f"{venue_type} past_races parse failed or empty"
                horse["past_races_fetch_warning"] = warning_reason
                total_warning_horses += 1
            else:
                horse.pop("past_races_fetch_warning", None)
            
            total_horses += 1
            total_past_races += len(past_races)
            
            if len(past_races) > 0:
                print(f"  ✅ {horse['馬名']}: {len(past_races)}走分取得")
            else:
                print(f"  ⚠️ {horse['馬名']}: 0走（データなし）")
        
        # レート制限（1秒待機）
        time.sleep(1)
    
    # 結果を保存
    output_file = input_file
    
    print(f"\n[DEBUG] 保存前の確認:")
    print(f"  - JRAレース数: {jra_count}")
    print(f"  - NARレース数: {nar_count}")
    print(f"  - 対象馬数: {total_horses}")
    print(f"  - 取得過去走数: {total_past_races}")
    print(f"  - 平均過去走数: {total_past_races / max(total_horses, 1):.1f}走/馬")
    print(f"  - 警告馬数: {total_warning_horses}")
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
            if "past_races" in horse and len(horse["past_races"]) > 0:
                has_past_races = True
                break
        if has_past_races:
            break
    
    if has_past_races:
        print(f"[SUCCESS] past_races フィールドの存在を確認しました")
    else:
        print(f"[WARN] past_races フィールドが空の可能性があります")
    
    print(f"\n✅ 完了")


if __name__ == "__main__":
    main()
