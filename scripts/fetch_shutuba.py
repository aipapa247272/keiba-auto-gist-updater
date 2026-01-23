import json
import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo


def http_get(url: str, timeout=20) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_shutuba_html(html: str, race_id: str) -> dict:
    """
    出馬表HTMLを解析して構造化データに変換
    """
    # レース情報の抽出
    race_name_match = re.search(r'<div class="RaceName">(.+?)</div>', html)
    race_name = race_name_match.group(1).strip() if race_name_match else "不明"
    
    # 距離の抽出（例：ダ1200m）
    distance_match = re.search(r'(ダ|芝)(\d+)m', html)
    distance = distance_match.group(0) if distance_match else "不明"
    
    # 馬データの抽出（簡易版：馬番・馬名・騎手のみ）
    horses = []
    
    # 馬番の抽出
    umaban_pattern = re.compile(r'<td[^>]*class="Umaban[^"]*">.*?(\d+).*?</td>', re.DOTALL)
    umaban_list = [int(m.group(1)) for m in umaban_pattern.finditer(html)]
    
    # 馬名の抽出
    horse_name_pattern = re.compile(r'<a[^>]*title="([^"]+)"[^>]*class="Horse_Name"', re.DOTALL)
    horse_names = [m.group(1) for m in horse_name_pattern.finditer(html)]
    
    # 騎手名の抽出
    jockey_pattern = re.compile(r'<a[^>]*title="([^"]+)"[^>]*>騎手</a>', re.DOTALL)
    jockeys = [m.group(1) for m in jockey_pattern.finditer(html)]
    
    # データの結合
    for i in range(min(len(umaban_list), len(horse_names))):
        horse = {
            "馬番": umaban_list[i],
            "馬名": horse_names[i] if i < len(horse_names) else "不明",
            "騎手": jockeys[i] if i < len(jockeys) else "不明"
        }
        horses.append(horse)
    
    return {
        "race_id": race_id,
        "race_info": {
            "レース名": race_name,
            "距離": distance,
            "頭数": len(horses)
        },
        "horses": horses
    }


def fetch_race_data(race_id: str) -> dict:
    """
    race_idから出馬表データを取得
    """
    url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
    print(f"Fetching: {url}")
    
    html = http_get(url)
    data = parse_shutuba_html(html, race_id)
    
    print(f"  レース: {data['race_info']['レース名']}")
    print(f"  頭数: {data['race_info']['頭数']}")
    
    return data


def main():
    # today_jobs.latest.json を読み込む
    try:
        with open("today_jobs.latest.json", "r", encoding="utf-8") as f:
            today_jobs = json.load(f)
    except FileNotFoundError:
        print("❌ today_jobs.latest.json が見つかりません")
        return
    
    ymd = today_jobs["ymd"]
    print(f"対象日: {ymd}")
    
    # 全レースのデータを取得
    all_race_data = []
    
    for jyo_cd, jyo_data in today_jobs["races"].items():
        jyo_name = jyo_data["name"]
        print(f"\n=== {jyo_name} ({jyo_cd}) ===")
        
        for race_no, race_id in jyo_data["race_id_map"].items():
            try:
                race_data = fetch_race_data(race_id)
                race_data["競馬場"] = jyo_name
                race_data["レース番号"] = race_no
                all_race_data.append(race_data)
            except Exception as e:
                print(f"  ❌ エラー: {e}")
    
    # JSON 保存
    output_file = f"race_data_{ymd}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "ymd": ymd,
            "races": all_race_data
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ {output_file} を作成しました（{len(all_race_data)}レース）")


if __name__ == "__main__":
    main()
