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
    
    # EUC-JP エンコーディングを明示的に指定
    resp.encoding = 'EUC-JP'
    
    return resp.text

def parse_shutuba_html(html: str, race_id: str) -> Dict:
    """BeautifulSoupで出馬表HTMLを解析"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # レース名を取得（<h1> タグから）
    race_name_tag = soup.find('h1', class_='RaceName')
    race_name = race_name_tag.get_text(strip=True) if race_name_tag else "不明"
    
    # レース情報を取得（距離・馬場状態等）
    race_data_tag = soup.find('div', class_='RaceData01')
    race_data_text = race_data_tag.get_text(strip=True) if race_data_tag else ""
    
    # 距離を抽出（例: "ダ1200m" "芝2000m"）
    import re
    distance_match = re.search(r'(ダ|芝)(\d+)m', race_data_text)
    distance = f"{distance_match.group(1)}{distance_match.group(2)}m" if distance_match else "不明"
    
    # 馬のデータを取得（<table> の各行から）
    horses = []
    horse_table = soup.find('table', class_='Shutuba_Table')
    
    if horse_table:
        horse_rows = horse_table.find_all('tr')[1:]  # ヘッダー行をスキップ
        
        for row in horse_rows:
            cells = row.find_all('td')
            if len(cells) < 8:
                continue
            
            # 各セルからデータを抽出
            horse_data = {
                "枠番": cells[0].get_text(strip=True),
                "馬番": cells[1].get_text(strip=True),
                "馬名": cells[3].get_text(strip=True),
                "性齢": cells[4].get_text(strip=True),
                "斤量": cells[5].get_text(strip=True),
                "騎手": cells[6].get_text(strip=True),
                "厩舎": cells[7].get_text(strip=True) if len(cells) > 7 else "不明"
            }
            horses.append(horse_data)
    
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
    
    for jyo_cd, jyo_data in data["races"].items():
        jyo_name = jyo_data["name"]
        race_id_map = jyo_data["race_id_map"]
        
        print(f"=== {jyo_name}({jyo_cd}) ===")
        
        for rno, race_id in race_id_map.items():
            race_data = fetch_race_data(race_id)
            race_data["競馬場"] = jyo_name
            race_data["レース番号"] = rno
            races_output.append(race_data)
            
            # レース情報を表示
            print(f"  {rno}R: {race_data['race_info']['レース名']}")
            print(f"    距離: {race_data['race_info']['距離']}")
            print(f"    頭数: {race_data['race_info']['頭数']}頭\n")
    
    output = {
        "ymd": ymd,
        "races": races_output
    }
    
    output_file = f"race_data_{ymd}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ {output_file} を作成しました ({len(races_output)}レース)")

if __name__ == "__main__":
    main()
