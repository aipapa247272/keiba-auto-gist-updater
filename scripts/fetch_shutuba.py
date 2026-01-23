import json
import requests
from bs4 import BeautifulSoup
from typing import Dict, List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def http_get(url: str) -> str:
    """HTTPリクエストを送信してHTMLを取得"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = 'EUC-JP'
    return resp.text

def parse_shutuba_html(html: str, race_id: str) -> Dict:
    """BeautifulSoupで出馬表HTMLを解析（デバッグ版）"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # デバッグ: HTMLの主要な要素を出力
    print(f"\n=== DEBUG: race_id={race_id} ===")
    
    # レース名候補を探す
    h1_tags = soup.find_all('h1')
    print(f"Found {len(h1_tags)} <h1> tags:")
    for i, tag in enumerate(h1_tags[:3]):  # 最初の3つだけ
        print(f"  h1[{i}]: class={tag.get('class')}, text={tag.get_text(strip=True)[:50]}")
    
    # レース情報候補を探す
    div_tags = soup.find_all('div', class_=lambda x: x and 'race' in x.lower())
    print(f"\nFound {len(div_tags)} <div> with 'race' in class:")
    for i, tag in enumerate(div_tags[:5]):  # 最初の5つだけ
        print(f"  div[{i}]: class={tag.get('class')}, text={tag.get_text(strip=True)[:80]}")
    
    # テーブル候補を探す
    table_tags = soup.find_all('table')
    print(f"\nFound {len(table_tags)} <table> tags:")
    for i, tag in enumerate(table_tags[:3]):  # 最初の3つだけ
        print(f"  table[{i}]: class={tag.get('class')}, id={tag.get('id')}")
        if tag.get('class'):
            print(f"    First row: {tag.find('tr').get_text(strip=True)[:100] if tag.find('tr') else 'N/A'}")
    
    print("=== END DEBUG ===\n")
    
    # 既存の解析ロジック（暫定）
    import re
    race_name = "不明"
    distance = "不明"
    horses = []
    
    # 距離を抽出（正規表現で全体から探す）
    distance_match = re.search(r'(ダ|芝)(\d+)m', html)
    if distance_match:
        distance = f"{distance_match.group(1)}{distance_match.group(2)}m"
    
    return {
        "race_id": race_id,
        "race_info": {
            "レース名": race_name,
            "距離": distance,
            "頭数": len(horses)
        },
        "horses": horses
    }

def fetch_race_data(race_id: str) -> Dict:
    """race_id から出馬表データを取得"""
    url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
    print(f"Fetching: {url}")
    
    try:
        html = http_get(url)
        return parse_shutuba_html(html, race_id)
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return {
            "race_id": race_id,
            "race_info": {
                "レース名": "取得失敗",
                "距離": "不明",
                "頭数": 0
            },
            "horses": [],
            "error": str(e)
        }

def main():
    """today_jobs.latest.json を読み込んで出馬表を取得"""
    with open("today_jobs.latest.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    ymd = data["ymd"]
    print(f"対象日: {ymd}\n")
    
    races_output = []
    
    # デバッグ用：最初の1レースだけ取得
    for jyo_cd, jyo_data in list(data["races"].items())[:1]:
        jyo_name = jyo_data["name"]
        race_id_map = jyo_data["race_id_map"]
        
        print(f"=== {jyo_name}({jyo_cd}) ===")
        
        for rno, race_id in list(race_id_map.items())[:1]:  # 1レースのみ
            race_data = fetch_race_data(race_id)
            race_data["競馬場"] = jyo_name
            race_data["レース番号"] = rno
            races_output.append(race_data)
            break
        break
    
    output = {
        "ymd": ymd,
        "races": races_output
    }
    
    output_file = f"race_data_{ymd}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ {output_file} を作成しました ({len(races_output)}レース)")

if __name__ == "__main__":
    main()
