#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_race_cancellation.py - レース開催中止情報の取得

netkeibaから開催中止情報を取得し、JSON形式で出力する
"""

import sys
import requests
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup


def http_get(url: str, timeout=20) -> str:
    """HTTP GET リクエスト"""
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def check_cancellation_news(ymd: str) -> dict:
    """
    netkeibaのニュースから開催中止情報を取得
    
    Args:
        ymd (str): 対象日付（YYYYMMDD）
    
    Returns:
        dict: 開催中止情報
    """
    # netkeibaのニュースページ
    url = "https://news.netkeiba.com/?pid=news_list"
    
    try:
        html = http_get(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # ニュース記事を検索
        articles = soup.find_all('div', class_='news_list')
        
        for article in articles[:20]:  # 最新20件を確認
            title_elem = article.find('a')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '')
            
            # 「開催中止」「中止」「取りやめ」などのキーワードを検索
            cancellation_keywords = ['開催中止', '中止', '取りやめ', '取り止め', '開催取りやめ']
            
            if any(keyword in title for keyword in cancellation_keywords):
                # 日付を確認（記事内に含まれる日付）
                date_match = re.search(r'(\d+)日', title)
                
                if date_match:
                    day = int(date_match.group(1))
                    target_day = int(ymd[6:8])
                    
                    # 日付が一致する場合
                    if day == target_day:
                        # 理由を抽出（雪・台風・馬場不良など）
                        reason = "天候不良"
                        if '雪' in title or '積雪' in title:
                            reason = "雪のため"
                        elif '台風' in title:
                            reason = "台風のため"
                        elif '馬場' in title:
                            reason = "馬場不良のため"
                        
                        # 競馬場を抽出
                        venues = []
                        venue_keywords = ['東京', '京都', '阪神', '中山', '小倉', '新潟', '福島', '中京', '札幌', '函館']
                        for venue in venue_keywords:
                            if venue in title:
                                venues.append(venue)
                        
                        return {
                            "is_cancelled": True,
                            "reason": reason,
                            "venues": venues if venues else ["全競馬場"],
                            "title": title,
                            "link": f"https://news.netkeiba.com{link}" if link.startswith('/') else link,
                            "date": ymd
                        }
        
        return {"is_cancelled": False, "date": ymd}
        
    except Exception as e:
        print(f"⚠️ 開催中止情報の取得に失敗: {e}")
        return {"is_cancelled": False, "date": ymd, "error": str(e)}


def check_race_list_page(ymd: str) -> dict:
    """
    レース一覧ページから開催中止情報を取得
    
    Args:
        ymd (str): 対象日付（YYYYMMDD）
    
    Returns:
        dict: 開催中止情報
    """
    url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={ymd}"
    
    try:
        html = http_get(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # 「開催中止」「中止」などのテキストを検索
        page_text = soup.get_text()
        
        if '開催中止' in page_text or '中止' in page_text:
            # 中止情報を抽出
            cancellation_info = soup.find(string=re.compile(r'開催中止|中止'))
            
            if cancellation_info:
                parent = cancellation_info.find_parent()
                if parent:
                    info_text = parent.get_text(strip=True)
                    
                    # 理由を抽出
                    reason = "天候不良"
                    if '雪' in info_text or '積雪' in info_text:
                        reason = "雪のため"
                    elif '台風' in info_text:
                        reason = "台風のため"
                    elif '馬場' in info_text:
                        reason = "馬場不良のため"
                    
                    return {
                        "is_cancelled": True,
                        "reason": reason,
                        "info": info_text,
                        "date": ymd
                    }
        
        return {"is_cancelled": False, "date": ymd}
        
    except Exception as e:
        print(f"⚠️ レース一覧ページの確認に失敗: {e}")
        return {"is_cancelled": False, "date": ymd, "error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_race_cancellation.py YYYYMMDD")
        sys.exit(1)
    
    ymd = sys.argv[1]
    
    print(f"📅 対象日付: {ymd}")
    print("=" * 60)
    
    # ニュースから確認
    print("\n🔍 ニュースから開催中止情報を確認中...")
    news_result = check_cancellation_news(ymd)
    
    if news_result.get('is_cancelled'):
        print(f"✅ 開催中止を検出:")
        print(f"   理由: {news_result['reason']}")
        print(f"   競馬場: {', '.join(news_result['venues'])}")
        print(f"   タイトル: {news_result['title']}")
        print(f"   リンク: {news_result['link']}")
        
        import json
        output = {
            "date": ymd,
            "is_cancelled": True,
            "reason": news_result['reason'],
            "venues": news_result['venues'],
            "source": "news",
            "title": news_result['title'],
            "link": news_result['link']
        }
        
        with open(f"cancellation_info_{ymd}.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ cancellation_info_{ymd}.json を作成しました")
        return 0
    
    # レース一覧ページから確認
    print("\n🔍 レース一覧ページから確認中...")
    list_result = check_race_list_page(ymd)
    
    if list_result.get('is_cancelled'):
        print(f"✅ 開催中止を検出:")
        print(f"   理由: {list_result['reason']}")
        print(f"   情報: {list_result.get('info', '')}")
        
        import json
        output = {
            "date": ymd,
            "is_cancelled": True,
            "reason": list_result['reason'],
            "source": "race_list",
            "info": list_result.get('info', '')
        }
        
        with open(f"cancellation_info_{ymd}.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ cancellation_info_{ymd}.json を作成しました")
        return 0
    
    # 開催中止なし
    print("\n✅ 開催中止の情報は見つかりませんでした")
    
    import json
    output = {
        "date": ymd,
        "is_cancelled": False
    }
    
    with open(f"cancellation_info_{ymd}.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ cancellation_info_{ymd}.json を作成しました")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
