#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
実際のHTMLを取得して構造を確認するスクリプト
"""

import requests
from bs4 import BeautifulSoup

race_id = "202651012904"
url = f"https://nar.sp.netkeiba.com/race/race_result.html?race_id={race_id}"

headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
}

print(f"URL: {url}\n")

response = requests.get(url, headers=headers)
response.encoding = 'EUC-JP'

soup = BeautifulSoup(response.content, 'html.parser')

# HTML全体を保存
with open('race_result_full.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())

print("✅ HTMLを race_result_full.html に保存しました\n")

# テーブルを探す
tables = soup.find_all('table')
print(f"📊 テーブル数: {len(tables)}\n")

for i, table in enumerate(tables, 1):
    print(f"{'='*60}")
    print(f"テーブル {i}")
    print(f"{'='*60}")
    
    # クラス名を表示
    table_class = table.get('class', ['なし'])
    print(f"クラス: {table_class}")
    
    rows = table.find_all('tr')
    print(f"行数: {len(rows)}\n")
    
    # 最初の10行を表示
    for j, row in enumerate(rows[:10], 1):
        cells = row.find_all(['td', 'th'])
        if cells:
            print(f"行{j} ({len(cells)}列):")
            for k, cell in enumerate(cells, 1):
                text = cell.get_text(strip=True)
                if text:
                    print(f"  列{k}: {text[:50]}")
    print()

# 「三連複」を含むテキストを探す
print(f"{'='*60}")
print("「三連複」を含む要素")
print(f"{'='*60}")

all_text = soup.get_text()
if '三連複' in all_text:
    print("✅ 「三連複」が見つかりました")
    
    # 三連複を含む要素を探す
    elements = soup.find_all(string=lambda text: text and '三連複' in text)
    for elem in elements[:3]:
        parent = elem.parent
        print(f"\n要素: {parent.name}")
        print(f"クラス: {parent.get('class', ['なし'])}")
        print(f"テキスト: {parent.get_text(strip=True)[:100]}")
        
        # 兄弟要素を表示
        next_sibling = parent.find_next_sibling()
        if next_sibling:
            print(f"次の要素: {next_sibling.get_text(strip=True)[:50]}")
else:
    print("❌ 「三連複」が見つかりません")
