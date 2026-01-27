#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出馬表データ取得スクリプト（改善版 v2.1）
- コマンドライン引数対応
- オッズ・人気順位の取得を追加
- 枠番の取得を追加
- レース条件（頭数、重量条件）の取得を追加
"""

import json
import re
import time
import sys
from datetime import datetime
import requests
from bs4 import BeautifulSoup

def fetch_race_data(race_id):
    """
    指定されたrace_idの出馬表データを取得
    """
    url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'EUC-JP'  # 重要: netkeibaはEUC-JP
        
        if resp.status_code != 200:
            print(f"❌ HTTP Error {resp.status_code} for race_id={race_id}")
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # レース基本情報の取得
        race_info = extract_race_info(soup, race_id)
        if not race_info:
            print(f"⚠️ レース情報を取得できませんでした: {race_id}")
            return None
        
        # 馬データの取得
        horses = extract_horses(soup)
        if not horses:
            print(f"⚠️ 馬データを取得できませんでした: {race_id}")
            return None
        
        race_info['horses'] = horses
        race_info['取得頭数'] = len(horses)
        
        print(f"✅ {race_info.get('レース名', 'N/A')}: {len(horses)}頭")
        
        return race_info
        
    except Exception as e:
        print(f"❌ エラー: {race_id} - {str(e)}")
        return None


def extract_race_info(soup, race_id):
    """
    レース基本情報を抽出
    """
    race_data = {
        'race_id': race_id
    }
    
    # レース名
    race_title = soup.find('div', class_='RaceName')
    if race_title:
        race_data['レース名'] = race_title.get_text(strip=True)
    
    # レースデータ（距離、発走時刻など）
    race_data_div = soup.find('div', class_='RaceData01')
    if race_data_div:
        race_text = race_data_div.get_text(strip=True)
        
        # 距離の抽出（例: ダ1400m）
        distance_match = re.search(r'([ダ芝])(\d+)m', race_text)
        if distance_match:
            race_data['トラック'] = distance_match.group(1)
            race_data['距離'] = int(distance_match.group(2))
        
        # 発走時刻（例: 10:55発走）
        time_match = re.search(r'(\d{1,2}):(\d{2})発走', race_text)
        if time_match:
            race_data['発走時刻'] = f"{time_match.group(1)}:{time_match.group(2)}"
        
        # 重量条件の抽出（別定、定量、ハンデ）
        if '別定' in race_text:
            race_data['重量条件'] = '別定'
        elif '定量' in race_text:
            race_data['重量条件'] = '定量'
        elif 'ハンデ' in race_text or 'ハンディ' in race_text:
            race_data['重量条件'] = 'ハンデ'
        else:
            race_data['重量条件'] = '不明'
    
    # 競馬場の判定（race_idから）
    venue_code = race_id[4:6]
    venue_map = {
        '30': '門別', '35': '盛岡', '36': '水沢', '42': '浦和', '43': '船橋',
        '44': '大井', '45': '川崎', '46': '金沢', '47': '笠松', '48': '名古屋',
        '50': '園田', '51': '姫路', '54': '高知', '55': '佐賀', '65': '帯広ば'
    }
    race_data['競馬場'] = venue_map.get(venue_code, '不明')
    
    # レース番号（race_idの末尾2桁）
    race_data['レース番号'] = int(race_id[-2:])
    
    return race_data


def extract_horses(soup):
    """
    出馬表から馬データを抽出（オッズ・人気・枠番を含む）
    """
    horses = []
    
    # 出馬表のテーブルを取得
    horse_table = soup.find('table', class_='Shutuba_Table')
    if not horse_table:
        return horses
    
    rows = horse_table.find_all('tr')
    
    for row in rows:
        # データ行のみ処理（ヘッダー行をスキップ）
        if not row.find('td', class_='Waku'):
            continue
        
        horse_data = {}
        
        # 枠番
        waku_td = row.find('td', class_='Waku')
        if waku_td:
            waku_text = waku_td.get_text(strip=True)
            try:
                horse_data['枠番'] = int(waku_text)
            except:
                horse_data['枠番'] = None
        
        # 馬番
        umaban_td = row.find('td', class_='Umaban')
        if umaban_td:
            umaban_text = umaban_td.get_text(strip=True)
            try:
                horse_data['馬番'] = int(umaban_text)
            except:
                horse_data['馬番'] = None
        
        # 馬名とhorse_id
        horse_name_td = row.find('td', class_='Horse_Name')
        if horse_name_td:
            horse_link = horse_name_td.find('a')
            if horse_link:
                horse_data['馬名'] = horse_link.get_text(strip=True)
                # horse_idの抽出
                href = horse_link.get('href', '')
                horse_id_match = re.search(r'/horse/(\d+)', href)
                if horse_id_match:
                    horse_data['horse_id'] = horse_id_match.group(1)
        
        # 性齢
        sex_age_td = row.find('td', class_='Barei')
        if sex_age_td:
            horse_data['性齢'] = sex_age_td.get_text(strip=True)
        
        # 斤量
        weight_td = row.find('td', class_='Weight')
        if weight_td:
            weight_text = weight_td.get_text(strip=True)
            try:
                horse_data['斤量'] = float(weight_text)
            except:
                horse_data['斤量'] = None
        
        # 騎手
        jockey_td = row.find('td', class_='Jockey')
        if jockey_td:
            jockey_link = jockey_td.find('a')
            if jockey_link:
                horse_data['騎手'] = jockey_link.get_text(strip=True)
        
        # 厩舎（調教師）
        trainer_td = row.find('td', class_='Trainer')
        if trainer_td:
            trainer_link = trainer_td.find('a')
            if trainer_link:
                horse_data['厩舎'] = trainer_link.get_text(strip=True)
        
        # オッズ（単勝）
        odds_td = row.find('td', class_='Odds')
        if odds_td:
            odds_text = odds_td.get_text(strip=True)
            try:
                horse_data['オッズ'] = float(odds_text)
            except:
                horse_data['オッズ'] = None
        
        # 人気順位
        popular_td = row.find('td', class_='Popular')
        if popular_td:
            popular_text = popular_td.get_text(strip=True)
            try:
                horse_data['人気'] = int(popular_text)
            except:
                horse_data['人気'] = None
        
        # 馬主（オーナー）
        owner_td = row.find('td', class_='Owner')
        if owner_td:
            horse_data['馬主'] = owner_td.get_text(strip=True)
        
        # 最低限のデータがあれば追加
        if horse_data.get('馬番') and horse_data.get('馬名'):
            horses.append(horse_data)
    
    return horses


def main():
    """
    メイン処理
    """
    # コマンドライン引数から ymd を取得
    ymd = None
    
    if len(sys.argv) > 1:
        ymd = sys.argv[1]
        print(f"📅 指定された日付: {ymd}")
    
    # today_jobs.latest.json から race_id リストを読み込み
    try:
        with open('today_jobs.latest.json', 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
        
        race_ids = jobs_data.get('race_ids', [])
        
        # ymd が指定されていない場合は jobs_data から取得
        if not ymd:
            # 'date' または 'ymd' キーを試す
            ymd = jobs_data.get('date') or jobs_data.get('ymd', '')
            if ymd:
                print(f"📅 取得した日付: {ymd}")
            else:
                print("⚠️ 日付が取得できませんでした（空文字列で続行）")
        
        if not race_ids:
            print("❌ race_idsが見つかりません")
            sys.exit(1)
        
        print(f"📊 対象レース数: {len(race_ids)}")
        print("-" * 50)
        
    except FileNotFoundError:
        print("❌ today_jobs.latest.json が見つかりません")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ today_jobs.latest.json の形式が不正です")
        sys.exit(1)
    
    # 各レースのデータを取得
    all_races = []
    success_count = 0
    
    for i, race_id in enumerate(race_ids, 1):
        print(f"[{i}/{len(race_ids)}] {race_id} を取得中...")
        
        race_data = fetch_race_data(race_id)
        
        if race_data:
            all_races.append(race_data)
            success_count += 1
        
        # サーバー負荷軽減のため待機
        if i < len(race_ids):
            time.sleep(1)
    
    # 結果を保存
    output_file = f"race_data_{ymd}.json"
    
    # バックアップ作成
    import os
    if os.path.exists(output_file):
        backup_file = f"race_data_{ymd}.backup.json"
        os.rename(output_file, backup_file)
        print(f"📦 バックアップ作成: {backup_file}")
    
    # 新しいデータを保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'ymd': ymd,
            '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'レース数': len(all_races),
            'races': all_races
        }, f, ensure_ascii=False, indent=2)
    
    print("-" * 50)
    print(f"✅ 完了: {success_count}/{len(race_ids)} レース")
    print(f"💾 保存先: {output_file}")
    
    # 統計情報
    total_horses = sum(race.get('取得頭数', 0) for race in all_races)
    print(f"🐴 総馬数: {total_horses}頭")


if __name__ == '__main__':
    main()
