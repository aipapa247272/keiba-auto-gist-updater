import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

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

def get_raceid_map_for_day(jyo_cd: str, ymd: str) -> dict:
    # race_list.html には race_id が載らないことがあるので、race_list_sub を使う
    url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}"
    html = http_get(url)

    print("fetch_url(race_list_sub):", url)
    print("contains /race/?:", "/race/" in html)
    print("contains shutuba.html?:", "shutuba.html" in html)
    print("contains race_id=?:", "race_id=" in html)
    print("len(race_list_sub html):", len(html))

    # race_id 抽出（12桁想定）
    race_ids = list(dict.fromkeys(RACE_ID_RE.findall(html)))
    print("race_ids count:", len(race_ids))
    print("race_ids head:", race_ids[:5])

    m = {}
    for rid in race_ids:
        rno = race_no_from_race_id(rid)
        if rno is None:
            continue
        m.setdefault(rno, rid)

    return m

def demo():
    # まずは動作確認用：今日の日付(JST)で船橋のrace_id mapを取る
    jst = ZoneInfo("Asia/Tokyo")
    ymd = datetime.now(jst).strftime("%Y%m%d")
    jyo_cd = "43"  # 船橋
    m = get_raceid_map_for_day(jyo_cd, ymd)
    print("ymd:", ymd)
    print("race_id_map keys:", sorted(m.keys()))
    if 10 in m:
        print("10R PC:", NETKEIBA_SHUTUBA_PC.format(race_id=m[10]))
        print("10R SP:", NETKEIBA_SHUTUBA_SP.format(race_id=m[10]))

if __name__ == "__main__":
    demo()

