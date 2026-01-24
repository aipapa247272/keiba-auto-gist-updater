import json
import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def http_get(url: str) -> str:
    """HTTPリクエストを送信してHTMLを取得"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = 'EUC-JP'
    return resp.text

def extract_horse_id(horse_name_cell) -> str:
    """
    馬名セルから horse_id を抽出
    例: <a href="https://db.netkeiba.com/horse/2023101194">馬名</a>
    """
    link = horse_name_cell.find('a')
    if link and link.get('href'):
        href = link.get('href')
        # horse_id を抽出（例: /horse/2023101194 → 2023101194）
        match = re.search(r'/horse/(\d{10})', href)
        if match:
            return match.group(1)
    return None

def parse_shutuba_html(html: str, race_id: str) -> Dict:
    """BeautifulSoupで出馬表HTMLを解析（horse_id 追加版）"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # レース情報を取得
    race_column = soup.find('div', class_='RaceColumn01')
    race_info_text = race_column.get_text(strip=True) if race_column else ""
    
    # レース名を抽出
    race_name_match = re.search(r'サラ系\S+|オープン\S*|[A-Z]\d+|新馬|未勝利', race_info_text)
    race_name = race_name_match.group(0) if race_name_match else "不明"
    
    # 距離を抽出
    distance_match = re.search(r'(ダ|芝)(\d+)m', race_info_text)
    distance = f"{distance_match.group(1)}{distance_match.group(2)}m" if distance_match else "不明"
    
    # 発走時刻を抽出
    time_match = re.search(r'(\d{1,2}:\d{2})発走', race_info_text)
    race_time = time_match.group(1) if time_match else "不明"
    
    # 馬のデータを取得
    horses = []
    horse_table = soup.find('table', class_='RaceTable01')
    
    if horse_table:
        horse_rows = horse_table.find_all('tr')
        
        for row in horse_rows[1:]:  # ヘッダー行をスキップ
            cells = row.find_all('td')
            if len(cells) < 8:
                continue
            
            # 馬名と horse_id を取得
            horse_name_tag = cells[3].find('a')
            horse_name = horse_name_tag.get_text(strip=True) if horse_name_tag else cells[3].get_text(strip=True)
            horse_id = extract_horse_id(cells[3])  # ★ 追加
            
            # 騎手を取得
            jockey_tag = cells[6].find('a')
            jockey = jockey_tag.get_text(strip=True) if jockey_tag else cells[6].get_text(strip=True)
            
            # 厩舎を取得
            trainer_tag = cells[7].find('a')
            trainer = trainer_tag.get_text(strip=True) if trainer_tag else cells[7].get_text(strip=True)
            
            horse_data = {
                "枠番": cells[0].get_text(strip=True),
                "馬番": cells[1].get_text(strip=True),
                "馬名": horse_name,
                "horse_id": horse_id,  # ★ 追加
                "性齢": cells[4].get_text(strip=True),
                "斤量": cells[5].get_text(strip=True),
                "騎手": jockey,
                "厩舎": trainer,
                "馬主": cells[8].get_text(strip=True) if len(cells) > 8 else "不明"
            }
            horses.append(horse_data)
    
    return {
        "race_id": race_id,
        "race_info": {
            "レース名": race_name,
            "距離": distance,
            "発走時刻": race_time,
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
                "発走時刻": "不明",
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
            info = race_data['race_info']
            print(f"  {rno}R: {info['レース名']} {info['発走時刻']}")
            print(f"    距離: {info['距離']}, 頭数: {info['頭数']}頭")
            
            # horse_id 取得状況を確認
            horses_with_id = [h for h in race_data.get('horses', []) if h.get('horse_id')]
            print(f"    horse_id 取得: {len(horses_with_id)}/{info['頭数']}頭\n")
    
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
