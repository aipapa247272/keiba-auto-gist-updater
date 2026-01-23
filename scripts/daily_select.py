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

import re
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

# ---- netkeiba / keiba.go.jp basic config ----
BABACODE_TO_NETKEIBA_JYOCD = {
  "19": "43",  # 船橋
  "23": "47",  # 笠松
  "28": "51",  # 姫路
  "31": "54",  # 高知
}

NETKEIBA_CALENDAR_URL = "https://nar.netkeiba.com/top/calendar.html?year={year}&month={month}&jyo_cd={jyo_cd}"
NETKEIBA_RACE_LIST_URL = "https://nar.netkeiba.com/top/race_list.html?kaisai_date={ymd}&kaisai_id={kaisai_id}"

NETKEIBA_SHUTUBA_PC = "https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
NETKEIBA_SHUTUBA_SP = "https://nar.sp.netkeiba.com/race/shutuba.html?race_id={race_id}"

KASAII_ID_RE = re.compile(r"kaisai_id=(\d+)")
RACE_ID_RE = re.compile(r"race_id=(\d{12})")

def http_get(url: str, timeout=20) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)

    print("fetch_url:", url)
    print("status:", r.status_code)
    print("len:", len(r.text))
    print("head:", r.text[:200].replace("\n", " "))

    r.raise_for_status()
    return r.text

def race_no_from_race_id(race_id: str):
    # 末尾2桁がR番号(01..12)の想定
    try:
        n = int(race_id[-2:])
        if 1 <= n <= 12:
            return n
    except Exception:
        pass
    return None

def get_kaisai_id_from_calendar(jyo_cd: str, ymd: str):
    year = int(ymd[:4]); month = int(ymd[4:6])
    url = NETKEIBA_CALENDAR_URL.format(year=year, month=month, jyo_cd=jyo_cd)
    html = http_get(url)

    key = f"kaisai_date={ymd}"
    idx = html.find(key)
    if idx == -1:
        return None
    window = html[max(0, idx-250): idx+250]
    m = KASAII_ID_RE.search(window)
    return m.group(1) if m else None

def get_raceid_map_for_day(ymd: str) -> dict:
    """
    指定日の全場のrace_idを取得して、場ごとに分類して返す
    """
    url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}"
    html = http_get(url)

    print("fetch_url(race_list_sub):", url)
    print("contains race_id=?:", "race_id=" in html)
    print("len(race_list_sub html):", len(html))

    # race_id 抽出（12桁）
    race_ids = list(dict.fromkeys(RACE_ID_RE.findall(html)))
    print("race_ids count:", len(race_ids))
    print("race_ids head:", race_ids[:5])

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

    return races_by_jyo

import json

def demo():
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    # 今日の日付（JST）
    jst = ZoneInfo("Asia/Tokyo")
    ymd = datetime.now(jst).strftime("%Y%m%d")
    
    # 全場のrace_id取得
    races = get_raceid_map_for_day(ymd)
    
    print("ymd:", ymd)
    print("開催場数:", len(races))
    for jyo_cd, data in races.items():
        print(f"  {jyo_cd} ({data['name']}): {len(data['race_id_map'])}R")

    # JSON 出力
    output = {
        "ymd": ymd,
        "races": races
    }
    
    with open("today_jobs.latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("✅ today_jobs.latest.json created")


if __name__ == "__main__":
    demo()
