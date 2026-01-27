#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出馬表データ取得スクリプト（デバッグ版 v2.2）
- HTML構造の詳細ログを追加
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
    指定されたrace_idの出馬表データを取得（デバッグログ付き）
    """
    url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"\n🔍 [DEBUG] URL: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'EUC-JP'
        
        print(f"🔍 [DEBUG] HTTP Status: {resp.status_code}")
        print(f"🔍 [DEBUG] Response Length: {len(resp.text)} characters")
        
        if resp.status_code != 200:
            print(f"❌ HTTP Error {resp.status_code} for race_id={race_id}")
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # デバッグ: テーブルの存在確認
        horse_table = soup.find('table', class_='Shutuba_Table')
        print(f"🔍 [DEBUG] Shutuba_Table found: {horse_table is not None}")
        
        if not horse_table:
            # すべてのテーブルを検索
            all_tables = soup.find_all('table')
            print(f"🔍 [DEBUG] Total tables found: {len(all_tables)}")
            for idx, table in enumerate(all_tables[:3]):  # 最初の3つだけ
                table_classes = table.get('class', [])
                print(f"🔍 [DEBUG] Table {idx+1} classes: {table_classes}")
        
        # レース基本情報の取得
        race_info = extract_race_info(soup, race_id)
        if not race_info:
            print(f"⚠️ レース情報を取得できませんでした: {race_id}")
            return None
        
        # 馬データの取得
        horses = extract_horses(soup)
        if not horses:
            print(f"⚠️ 馬データを取得できませんでした: {race_id}")
            print(f"🔍 [DEBUG] Checking HTML structure...")
            
            # デバッグ: 馬名を含む要素を検索
            horse_names = soup.find_all('a', href=re.compile(r'/horse/'))
            print(f"🔍 [DEBUG] Horse links found: {len(horse_names)}")
            if horse_names:
                print(f"🔍 [DEBUG] First horse: {horse_names[0].get_text(strip=True)}")
            
            return None
        
        race_info['horses'] = horses
        race_info['取得頭数'] = len(horses)
        
        print(f"✅ {race_info.get('レース名', 'N/A')}: {len(horses)}頭")
        
        return race_info
        
    except Exception as e:
        print(f"❌ エラー: {race_id} - {str(e)}")
        import traceback
        traceback.print_exc()
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
        print(f"🔍 [DEBUG] Race name: {race_data['レース名']}")
    else:
        print(f"🔍 [DEBUG] RaceName div not found")
    
    # レースデータ（距離、発走時刻など）
    race_data_div = soup.find('div', class_='RaceData01')
    if race_data_div:
        race_text = race_data_div.get_text(strip=True)
        
        # 距離の抽出
        distance_match = re.search(r'([ダ芝])(\d+)m', race_text)
        if distance_match:
            race_data['トラック'] = distance_match.group(1)
            race_data['距離'] = int(distance_match.group(2))
        
        # 発走時刻
        time_match = re.search(r'(\d{1,2}):(\d{2})発走', race_text)
        if time_match:
            race_data['発走時刻'] = f"{time_match.group(1)}:{time_match.group(2)}"
        
        # 重量条件
        if '別定' in race_text:
            race_data['重量条件'] = '別定'
        elif '定量' in race_text:
            race_data['重量条件'] = '定量'
        elif 'ハンデ' in race_text or 'ハンディ' in race_text:
            race_data['重量条件'] = 'ハンデ'
        else:
            race_data['重量条件'] = '不明'
    
    # 競馬場
    venue_code = race_id[4:6]
    venue_map = {
        '30': '門別', '35': '盛岡', '36': '水沢', '42': '浦和', '43': '船橋',
        '44': '大井', '45': '川崎', '46': '金沢', '47': '笠松', '48': '名古屋',
        '50': '園田', '51': '姫路', '54': '高知', '55': '佐賀', '65': '帯広ば'
    }
    race_data['競馬場'] = venue_map.get(venue_code, '不明')
    race_data['レース番号'] = int(race_id[-2:])
    
    return race_data


def extract_horses(soup):
    """
    出馬表から馬データを抽出（デバッグログ付き）
    """
    horses = []
    
    # 出馬表のテーブルを取得
    horse_table = soup.find('table', class_='Shutuba_Table')
    if not horse_table:
        print(f"🔍 [DEBUG] Shutuba_Table not found, trying alternative selectors...")
        
        # 代替セレクタを試す
        horse_table = soup.find('table', class_='HorseList')
        if horse_table:
            print(f"🔍 [DEBUG] Found table with class 'HorseList'")
        else:
            # テーブルをIDで検索
            horse_table = soup.find('table', id='shutuba_table')
            if horse_table:
                print(f"🔍 [DEBUG] Found table with id 'shutuba_table'")
    
    if not horse_table:
        return horses
    
    rows = horse_table.find_all('tr')
    print(f"🔍 [DEBUG] Total rows: {len(rows)}")
    
    for idx, row in enumerate(rows):
        # データ行のみ処理
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
        
        # 厩舎
        trainer_td = row.find('td', class_='Trainer')
        if trainer_td:
            trainer_link = trainer_td.find('a')
            if trainer_link:
                horse_data['厩舎'] = trainer_link.get_text(strip=True)
        
        # オッズ
        odds_td = row.find('td', class_='Odds')
        if odds_td:
            odds_text = odds_td.get_text(strip=True)
            try:
                horse_data['オッズ'] = float(odds_text)
            except:
                horse_data['オッズ'] = None
        
        # 人気
        popular_td = row.find('td', class_='Popular')
        if popular_td:
            popular_text = popular_td.get_text(strip=True)
            try:
                horse_data['人気'] = int(popular_text)
            except:
                horse_data['人気'] = None
        
        # 馬主
        owner_td = row.find('td', class_='Owner')
        if owner_td:
            horse_data['馬主'] = owner_td.get_text(strip=True)
        
        # データチェック
        if horse_data.get('馬番') and horse_data.get('馬名'):
            horses.append(horse_data)
            if idx == 1:  # 最初のデータ行をログ出力
                print(f"🔍 [DEBUG] First horse data: {horse_data}")
    
    print(f"🔍 [DEBUG] Total horses extracted: {len(horses)}")
    return horses


def main():
    """
    メイン処理（デバッグ版）
    """
    # コマンドライン引数
    ymd = None
    
    if len(sys.argv) > 1:
        ymd = sys.argv[1]
        print(f"📅 指定された日付: {ymd}")
    
    # today_jobs.latest.json から取得
    try:
        with open('today_jobs.latest.json', 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
        
        race_ids = jobs_data.get('race_ids', [])
        
        if not ymd:
            ymd = jobs_data.get('date') or jobs_data.get('ymd', '')
            if ymd:
                print(f"📅 取得した日付: {ymd}")
            else:
                print("⚠️ 日付が取得できませんでした")
        
        if not race_ids:
            print("❌ race_idsが見つかりません")
            sys.exit(1)
        
        print(f"📊 対象レース数: {len(race_ids)}")
        print("-" * 50)
        
        # 🔥 デバッグモード: 最初の1レースのみテスト
        print(f"\n🔥 デバッグモード: 最初の1レースのみテスト\n")
        race_ids = race_ids[:1]
        
    except FileNotFoundError:
        print("❌ today_jobs.latest.json が見つかりません")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ today_jobs.latest.json の形式が不正です")
        sys.exit(1)
    
    # レースデータ取得
    all_races = []
    success_count = 0
    
    for i, race_id in enumerate(race_ids, 1):
        print(f"\n[{i}/{len(race_ids)}] {race_id} を取得中...")
        
        race_data = fetch_race_data(race_id)
        
        if race_data:
            all_races.append(race_data)
            success_count += 1
        
        time.sleep(1)
    
    # 結果保存
    output_file = f"race_data_{ymd}_debug.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'ymd': ymd,
            '取得日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'レース数': len(all_races),
            'races': all_races
        }, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print(f"✅ 完了: {success_count}/{len(race_ids)} レース")
    print(f"💾 保存先: {output_file}")
    
    if all_races:
        total_horses = sum(race.get('取得頭数', 0) for race in all_races)
        print(f"🐴 総馬数: {total_horses}頭")


if __name__ == '__main__':
    main()
