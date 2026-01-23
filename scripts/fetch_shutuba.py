import json
import requests
import re
from typing import Dict, List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def http_get(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_shutuba_html(html: str, race_id: str) -> Dict:
    """
    デバッグ用：HTMLの先頭1000文字を出力
    """
    print(f"\n=== HTML Preview (race_id={race_id}) ===")
    print(html[:1000])  # 先頭1000文字を出力
    print("=== End Preview ===\n")
    
    # 既存の解析ロジック（暫定的に残す）
    race_name = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    distance = re.search(r'(ダ|芝)(\d+)m', html)
    
    horses = []
    horse_rows = re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>.*?</tr>', html, re.DOTALL)
    
    return {
        "race_id": race_id,
        "race_info": {
            "レース名": race_name.group(1) if race_name else "不明",
            "距離": f"{distance.group(1)}{distance.group(2)}m" if distance else "不明",
            "頭数": len(horses)
        },
        "horses": horses
    }

def fetch_race_data(race_id: str) -> Dict:
    url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
    print(f"Fetching: {url}")
    html = http_get(url)
    return parse_shutuba_html(html, race_id)

def main():
    with open("today_jobs.latest.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    ymd = data["ymd"]
    print(f"対象日: {ymd}")
    
    races_output = []
    
    for jyo_cd, jyo_data in data["races"].items():
        jyo_name = jyo_data["name"]
        race_id_map = jyo_data["race_id_map"]
        
        print(f"\n=== {jyo_name}({jyo_cd}) ===")
        
        # デバッグ用：最初の1レースだけ取得
        for rno, race_id in list(race_id_map.items())[:1]:  # [:1] = 1レースのみ
            race_data = fetch_race_data(race_id)
            race_data["競馬場"] = jyo_name
            race_data["レース番号"] = rno
            races_output.append(race_data)
            break  # 1レースだけでデバッグ
    
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
