#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出馬表データ取得スクリプト（修正版 v3.2）
- テーブルの行数で判定（10行以上のテーブルを出馬表として認識）
- 1頭しか取得できない問題を解決
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'EUC-JP'
        
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
        horses = extract_horses_from_table(soup)
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
    
    # レースデータ
    race_data_div = soup.find('div', class_='RaceData01')
    if race_data_div:
        race_text = race_data_div.get_text(strip=True)
        
        # 距離
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


def extract_horses_from_table(soup):
    """
    出馬表テーブルから馬データを抽出（行数判定版）
    """
    horses = []
    
    # Shutuba_Table クラスを持つすべてのテーブルを取得
    candidate_tables = soup.find_all('table', class_='Shutuba_Table')
    
    # 行数が10以上のテーブルを出馬表として判定
    shutuba_table = None
    for table in candidate_tables:
        rows = table.find_all('tr')
        if len(rows) >= 10:  # 出馬表は最低10行以上（ヘッダー + 9頭以上）
            shutuba_table = table
            break
    
    if not shutuba_table:
        # 代替: RaceTable01 クラスを持つテーブルを探す
        shutuba_table = soup.find('table', class_='RaceTable01')
    
    if not shutuba_table:
        return horses
    
    # すべての行を取得
    rows = shutuba_table.find_all('tr')
    
    # 馬データ行を抽出（馬リンクを含む行）
    for row in rows:
        horse_link = row.find('a', href=re.compile(r'/horse/\d+'))
        if not horse_link:
            continue
        
        horse_data = {}
        
        # 馬名とhorse_id
        horse_data['馬名'] = horse_link.get_text(strip=True)
        href = horse_link.get('href', '')
        horse_id_match = re.search(r'/horse/(\d+)', href)
        if horse_id_match:
            horse_data['horse_id'] = horse_id_match.group(1)
        
        # すべてのtdセルを取得
        cells = row.find_all('td')
        
        # セルから情報を抽出
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            cell_class = ' '.join(cell.get('class', []))
            
            # 枠番
            if 'Waku' in cell_class and cell_text.isdigit():
                horse_data['枠番'] = int(cell_text)
            
            # 馬番
            elif 'Umaban' in cell_class and cell_text.isdigit():
                horse_data['馬番'] = int(cell_text)
            
            # 性齢（例: 牡4, 牝3）
            elif re.match(r'^[牡牝セ][0-9]$', cell_text):
                horse_data['性齢'] = cell_text
            
            # 斤量（例: 54.0, 55.5）
            elif re.match(r'^\d{2}\.\d$', cell_text):
                try:
                    horse_data['斤量'] = float(cell_text)
                except:
                    pass
            
            # オッズ
            elif 'Odds' in cell_class:
                try:
                    horse_data['オッズ'] = float(cell_text)
                except:
                    pass
            
            # 人気
            elif 'Popular' in cell_class and cell_text.isdigit():
                horse_data['人気'] = int(cell_text)
        
        # 騎手リンク
        jockey_link = row.find('a', href=re.compile(r'/jockey/'))
        if jockey_link:
            horse_data['騎手'] = jockey_link.get_text(strip=True)
        
        # 調教師リンク
        trainer_link = row.find('a', href=re.compile(r'/trainer/'))
        if trainer_link:
            horse_data['厩舎'] = trainer_link.get_text(strip=True)
        
        # 馬主
        owner_cell = row.find('td', class_='Owner')
        if owner_cell:
            horse_data['馬主'] = owner_cell.get_text(strip=True)
        
        # 最低限のデータがあれば追加
        if horse_data.get('馬名') and horse_data.get('horse_id'):
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
