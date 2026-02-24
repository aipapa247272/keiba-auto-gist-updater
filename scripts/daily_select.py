#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_select.py - 当日のrace_idを自動取得（中央/地方両対応版）
- 統合ルール準拠：土日祝はJRAのみ、平日は中央→地方
- 修正: race_idが未来のレースでないか確認
"""

import sys
import re
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 中央競馬（JRA）場コード → 場名のマッピング
JRA_VENUE_MAP = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉"
}

# 地方競馬（NAR）場コード → 場名のマッピング
NAR_VENUE_MAP = {
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
    """HTTP GET リクエスト"""
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    
    print(f"📡 fetch_url: {url}")
    print(f"📊 status: {r.status_code}")
    print(f"📏 len: {len(r.text)}")
    
    r.raise_for_status()
    return r.text

def is_weekend_or_holiday(date_obj):
    """
    土日祝の判定
    - 土曜日: weekday() == 5
    - 日曜日: weekday() == 6
    - 祝日: 簡易実装（後で拡張可能）
    """
    # 土日判定
    if date_obj.weekday() >= 5:
        return True
    
    # 祝日判定（簡易版：主要祝日のみ）
    holidays_2026 = [
        "20260101",  # 元日
        "20260113",  # 成人の日
        "20260211",  # 建国記念の日
        "20260223",  # 天皇誕生日
        "20260320",  # 春分の日
        "20260429",  # 昭和の日
        "20260503",  # 憲法記念日
        "20260504",  # みどりの日
        "20260505",  # こどもの日
        "20260720",  # 海の日
        "20260811",  # 山の日
        "20260921",  # 敬老の日
        "20260923",  # 秋分の日
        "20261012",  # 体育の日
        "20261103",  # 文化の日
        "20261123",  # 勤労感謝の日
    ]
    
    ymd_str = date_obj.strftime("%Y%m%d")
    return ymd_str in holidays_2026

def race_no_from_race_id(race_id: str):
    """race_idの末尾2桁からレース番号を取得"""
    try:
        n = int(race_id[-2:])
        if 1 <= n <= 12:
            return n
    except Exception:
        pass
    return None

def get_venue_name(race_id: str) -> tuple:
    """
    race_idから競馬場情報を取得
    返り値: (venue_type, venue_name)
    - venue_type: 'JRA' or 'NAR'
    - venue_name: 競馬場名
    """
    jyo_code = race_id[4:6]
    
    # 中央競馬
    if jyo_code in JRA_VENUE_MAP:
        return 'JRA', JRA_VENUE_MAP[jyo_code]
    
    # 地方競馬
    if jyo_code in NAR_VENUE_MAP:
        return 'NAR', NAR_VENUE_MAP[jyo_code]
    
    return 'UNKNOWN', f"場コード{jyo_code}"

def validate_race_id(race_id: str, target_ymd: str) -> bool:
    """
    race_idが指定日付のレースか確認
    
    JRA race_id: YYYY + 場コード + 開催回 + 日目 + RR
    NAR race_id: YYYY + 場コード + MM + DD + RR
    
    NARの場合、位置6:8が月、位置8:10が日
    """
    from datetime import datetime
    
    NAR_VENUE_MAP = {
        '30': '門別', '35': '盛岡', '36': '水沢', '42': '浦和', '43': '船橋',
        '44': '大井', '45': '川崎', '46': '金沢', '47': '笠松', '48': '名古屋',
        '50': '園田', '51': '姫路', '54': '高知', '55': '佐賀', '65': '帯広ば'
    }
    
    try:
        venue_code = race_id[4:6]
        target_date = datetime.strptime(target_ymd, "%Y%m%d")
        race_year = int(race_id[:4])
        
        # 年が一致するか確認
        if abs(race_year - target_date.year) > 0:
            return False
        
        # NARの場合、位置6:8が月、位置8:10が日
        if venue_code in NAR_VENUE_MAP:
            race_month = int(race_id[6:8])
            race_day = int(race_id[8:10])
            
            # 月が一致するか確認
            if abs(race_month - target_date.month) > 1:
                return False
            
            # 日が一致するか確認
            if abs(race_day - target_date.day) > 7:
                return False
        else:
            # JRAの場合、位置4:6が場コード
            # 簡易的に年が一致すればOK
            pass
        
        return True
        
    except Exception as e:
        print(f"⚠️ race_id validation error: {e}")
        return False

def fetch_jra_races(ymd: str) -> tuple:
    """
    中央競馬（JRA）のrace_idを取得
    返り値: (races_by_jyo, race_ids, race_list)
    """
    # JRAのレース一覧ページ
    # 注意: 複数のURLを試行
    
    urls = [
        f"https://race.netkeiba.com/top/race_list.html?kaisai_date={ymd}",
        f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}",
        f"https://race.netkeiba.com/?pid=race_list&date={ymd}",
    ]
    
    for url in urls:
        try:
            html = http_get(url)
            
            # race_id 抽出（12桁）
            race_ids = list(dict.fromkeys(RACE_ID_RE.findall(html)))
            
            # JRAのrace_idのみフィルタ（場コード01-10）
            jra_race_ids = [rid for rid in race_ids if rid[4:6] in JRA_VENUE_MAP]
            
            # 日付検証
            valid_race_ids = [rid for rid in jra_race_ids if validate_race_id(rid, ymd)]
            
            if len(jra_race_ids) != len(valid_race_ids):
                print(f"⚠️ 無効なrace_idを除外: {len(jra_race_ids) - len(valid_race_ids)}件")
            
            if valid_race_ids:
                print(f"✅ JRA: {len(valid_race_ids)} races found")
                jra_race_ids = valid_race_ids
                break
        except Exception as e:
            print(f"⚠️ JRA fetch failed for {url}: {e}")
            continue
    else:
        print(f"❌ JRA: No races found")
        return {}, [], []
    
    # 場ごとに分類
    races_by_jyo = {}
    race_list = []
    
    for rid in jra_race_ids:
        jyo_cd = rid[4:6]
        rno = race_no_from_race_id(rid)
        
        if rno is None:
            continue
        
        venue_type, venue_name = get_venue_name(rid)
        
        # 場別集計用
        if jyo_cd not in races_by_jyo:
            races_by_jyo[jyo_cd] = {
                "name": venue_name,
                "type": venue_type,
                "race_id_map": {}
            }
        
        races_by_jyo[jyo_cd]["race_id_map"][rno] = rid
        
        # 後続スクリプト用リスト
        race_list.append({
            "race_id": rid,
            "race_info": {
                "venue": venue_name,
                "venue_code": jyo_cd,
                "venue_type": venue_type,
                "race_no": rno,
                "レース名": f"{rno}R"
            }
        })
    
    return races_by_jyo, jra_race_ids, race_list

def fetch_nar_races(ymd: str) -> tuple:
    """
    地方競馬（NAR）のrace_idを取得
    返り値: (races_by_jyo, race_ids, race_list)
    """
    url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}"
    
    # NAR は Referer が必要
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://nar.netkeiba.com/top/race_list.html'
    }
    
    try:
        print(f"📡 NAR fetch_url: {url}")
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        html = r.text
        print(f"📊 NAR status: {r.status_code}, len: {len(html)}")
    except Exception as e:
        print(f"❌ NAR fetch failed: {e}")
        return {}, [], []
    
    # race_id 抽出（12桁）
    race_ids = list(dict.fromkeys(RACE_ID_RE.findall(html)))
    
    # NARのrace_idのみフィルタ（場コード11以上）
    nar_race_ids = [rid for rid in race_ids if rid[4:6] in NAR_VENUE_MAP]
    
    # 日付検証
    valid_race_ids = [rid for rid in nar_race_ids if validate_race_id(rid, ymd)]
    
    if len(nar_race_ids) != len(valid_race_ids):
        print(f"⚠️ 無効なrace_idを除外: {len(nar_race_ids) - len(valid_race_ids)}件")
    
    print(f"✅ NAR: {len(valid_race_ids)} races found")
    nar_race_ids = valid_race_ids
    
    # 場ごとに分類
    races_by_jyo = {}
    race_list = []
    
    for rid in nar_race_ids:
        jyo_cd = rid[4:6]
        rno = race_no_from_race_id(rid)
        
        if rno is None:
            continue
        
        venue_type, venue_name = get_venue_name(rid)
        
        # 場別集計用
        if jyo_cd not in races_by_jyo:
            races_by_jyo[jyo_cd] = {
                "name": venue_name,
                "type": venue_type,
                "race_id_map": {}
            }
        
        races_by_jyo[jyo_cd]["race_id_map"][rno] = rid
        
        # 後続スクリプト用リスト
        race_list.append({
            "race_id": rid,
            "race_info": {
                "venue": venue_name,
                "venue_code": jyo_cd,
                "venue_type": venue_type,
                "race_no": rno,
                "レース名": f"{rno}R"
            }
        })
    
    return races_by_jyo, nar_race_ids, race_list

def main():
    # コマンドライン引数から日付を取得（なければ今日）
    if len(sys.argv) > 1:
        ymd = sys.argv[1]
        print(f"📅 指定された日付: {ymd}")
    else:
        jst = ZoneInfo("Asia/Tokyo")
        ymd = datetime.now(jst).strftime("%Y%m%d")
        print(f"📅 今日の日付（自動取得）: {ymd}")
    
    # 日付オブジェクトを作成（曜日判定用）
    date_obj = datetime.strptime(ymd, "%Y%m%d")
    is_weekend = is_weekend_or_holiday(date_obj)
    
    weekday_name = ["月", "火", "水", "木", "金", "土", "日"][date_obj.weekday()]
    
    print("=" * 60)
    print(f"📆 曜日: {weekday_name}曜日")
    print(f"🎌 土日祝判定: {'YES (JRAのみ)' if is_weekend else 'NO (中央→地方)'}")
    print("=" * 60)
    
    # 統合ルールに従ってデータ取得
    all_races_by_jyo = {}
    all_race_ids = []
    all_race_list = []
    
    if is_weekend:
        # 土日祝：JRAを優先、なければ地方も取得
        print("\n🏇 土日祝モード: JRAを優先、なければ地方も取得")
        jra_races_by_jyo, jra_race_ids, jra_race_list = fetch_jra_races(ymd)
        
        all_races_by_jyo.update(jra_races_by_jyo)
        all_race_ids.extend(jra_race_ids)
        all_race_list.extend(jra_race_list)
        
        # JRAがない場合は地方も取得
        if not jra_race_ids:
            print("⚠️ JRAが開催されていないため、地方競馬も取得")
            nar_races_by_jyo, nar_race_ids, nar_race_list = fetch_nar_races(ymd)
            
            all_races_by_jyo.update(nar_races_by_jyo)
            all_race_ids.extend(nar_race_ids)
            all_race_list.extend(nar_race_list)
    else:
        # 平日：中央→地方の順
        print("\n🏇 平日モード: 中央→地方の順で取得")
        
        # 中央競馬を取得
        jra_races_by_jyo, jra_race_ids, jra_race_list = fetch_jra_races(ymd)
        
        all_races_by_jyo.update(jra_races_by_jyo)
        all_race_ids.extend(jra_race_ids)
        all_race_list.extend(jra_race_list)
        
        # 地方競馬を取得（中央がない場合、または追加取得）
        print("\n🏇 地方競馬も取得")
        nar_races_by_jyo, nar_race_ids, nar_race_list = fetch_nar_races(ymd)
        
        all_races_by_jyo.update(nar_races_by_jyo)
        all_race_ids.extend(nar_race_ids)
        all_race_list.extend(nar_race_list)
    
    # 開催場数とレース数を表示
    print("\n" + "=" * 60)
    print(f"✅ 開催場数: {len(all_races_by_jyo)}")
    
    # JRAとNARを分けて表示
    jra_venues = {k: v for k, v in all_races_by_jyo.items() if v.get('type') == 'JRA'}
    nar_venues = {k: v for k, v in all_races_by_jyo.items() if v.get('type') == 'NAR'}
    
    if jra_venues:
        print("\n🏇 中央競馬（JRA）:")
        for jyo_cd, data in sorted(jra_venues.items()):
            print(f"  📍 {data['name']} ({jyo_cd}): {len(data['race_id_map'])}R")
    
    if nar_venues:
        print("\n🏇 地方競馬（NAR）:")
        for jyo_cd, data in sorted(nar_venues.items()):
            print(f"  📍 {data['name']} ({jyo_cd}): {len(data['race_id_map'])}R")
    
    print(f"\n✅ 総レース数: {len(all_race_ids)}")
    print("=" * 60)
    
    # JSON 出力（後続スクリプト用）
    jst = ZoneInfo("Asia/Tokyo")
    output = {
        "date": ymd,
        "generated_at": datetime.now(jst).isoformat(),
        "is_weekend": is_weekend,
        "weekday": weekday_name,
        "total_race_count": len(all_race_ids),
        "total_venues": len(all_races_by_jyo),
        "jra_races": len(jra_race_ids) if 'jra_race_ids' in locals() else 0,
        "nar_races": len(nar_race_ids) if 'nar_race_ids' in locals() else 0,
        "race_ids": all_race_ids,
        "selected_predictions": all_race_list,
        "races_by_venue": all_races_by_jyo
    }
    
    # ファイル出力
    output_file = "today_jobs.latest.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ {output_file} created")
    print(f"📊 race_ids: {len(all_race_ids)}件")
    print(f"📊 selected_predictions: {len(all_race_list)}件")
    

    # ===== 🆕 レース0件時の処理（メンテナンス・全場休催対応）=====
    if len(all_race_ids) == 0:
        print("\n⚠️ 本日はレースが0件です")
        
        # 休催理由を推定
        no_race_reason = "本日は競馬の開催がありません"
        no_race_type = "no_race"
        
        # NARサイトにアクセスして休催理由を確認
        try:
            nar_url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'https://nar.netkeiba.com/'
            }
            r = requests.get(nar_url, headers=headers, timeout=10)
            nar_text = r.text.lower()
            if 'メンテナンス' in r.text or 'maintenance' in nar_text or 'システム' in r.text:
                no_race_reason = "システムメンテナンスのため全地方競馬休催日"
                no_race_type = "maintenance"
                print("🔧 システムメンテナンスによる休催を検知")
            elif '休止' in r.text or '休催' in r.text:
                no_race_reason = "本日は全競馬場が休催です"
                no_race_type = "closed"
                print("🚫 全場休催を検知")
        except Exception as e:
            print(f"⚠️ 休催理由の確認に失敗: {e}")
        
        # latest_predictions.json を「開催なし」状態で更新
        jst = ZoneInfo("Asia/Tokyo")
        no_race_data = {
            "ymd": ymd,
            "generated_at": datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S"),
            "no_race": True,
            "no_race_type": no_race_type,
            "no_race_reason": no_race_reason,
            "total_races": 0,
            "selected_races": 0,
            "skipped_races": 0,
            "selected_predictions": [],
            "summary": {
                "turbulence": {"低": 0, "中": 0, "高": 0},
                "total_investment": 0
            }
        }
        
        with open("latest_predictions.json", "w", encoding="utf-8") as f:
            json.dump(no_race_data, f, ensure_ascii=False, indent=2)
        
        # 日付別ファイルも保存
        no_race_file = f"final_predictions_{ymd}.json"
        with open(no_race_file, "w", encoding="utf-8") as f:
            json.dump(no_race_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ latest_predictions.json を「開催なし」状態で更新: {no_race_reason}")
        print(f"✅ {no_race_file} を作成")
        print("\n✅ 処理完了（開催なし）")
        return 0
    # ===== 0件処理終わり =====

    # サンプル表示
    if all_race_list:
        print("\n📋 サンプル（最初の3件）:")
        for i, race in enumerate(all_race_list[:3], 1):
            venue_type = race['race_info']['venue_type']
            venue_name = race['race_info']['venue']
            race_no = race['race_info']['race_no']
            race_id = race['race_id']
            print(f"  {i}. [{venue_type}] {venue_name} {race_no}R - {race_id}")
    
    # 終了
    print("\n✅ 処理完了")
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
