import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import time
import pytz
import re

# 日本時間を取得する関数
def get_japan_time():
    tokyo_timezone = pytz.timezone('Asia/Tokyo')
    return datetime.now(tokyo_timezone)

def scrape_and_save_news(url, genre_en, genre_jp, folder_name, scrape_datetime):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = soup.select('li[data-ual-view-type="list"]')  # ニュースアイテムを取得

        if not news_items:
            print("No news items found. Check the HTML structure.")
            return

        news_data = []

        for idx, item in enumerate(news_items):
            # 各要素を取得
            rank_element = item.select_one('.sc-1hy2mez-11')  # ランク
            title_element = item.select_one('.sc-3ls169-0.dHAJpi')  # タイトル
            media_element = item.select_one('.sc-1hy2mez-3')  # メディア名
            date_element = item.select_one('time')  # 日付
            link_element = item.select_one('a')  # リンク
            comment_element = item.select_one('.sc-1hy2mez-6')  # コメント

            # 各要素が存在するか確認
            if not rank_element:
                print(f"Rank element not found for item {idx}. Skipping.")
                continue

            # 各要素のテキストを取得
            rank = rank_element.get_text(strip=True)
            title = title_element.get_text(strip=True) if title_element else "N/A"
            media = media_element.get_text(strip=True) if media_element else "N/A"
            date = date_element.get_text(strip=True) if date_element else "N/A"
            link = link_element['href'].strip() if link_element else "N/A"
            comment = comment_element.get_text(strip=True) if comment_element else "N/A"
            comment = re.sub(r'件/時', '', comment)  # 「件/時」を削除

            # データリストに追加
            news_data.append([
                scrape_datetime.strftime('%Y-%m-%d'),
                scrape_datetime.strftime('%H:%M'),
                genre_en, genre_jp,
                rank, media, title,
                comment, link, date
            ])

        # CSVファイルに保存
        if news_data:
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)
            filename = os.path.join(folder_name, f"{scrape_datetime.strftime('%Y_%m%d_%H%M')}_cmnt_{genre_en}.csv")
            df = pd.DataFrame(news_data, columns=[
                'scrp_date', 'scrp_time', 'genre_en', 'genre_jp', 'rank', 'media_jp', 'title', 'comment', 'link', 'date_original'
            ])
            df.to_csv(filename, index=False, encoding='utf-8-sig')  # UTF-8 BOM付きで保存
            print(f"CSV file saved as {filename}")
        else:
            print(f"No data to save for {genre_en} at {url}")

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
    except Exception as e:
        print(f"Scraping error at {url}: {e}")
        raise


# URLとジャンルのリスト
genres = [
    ("TTL", "総合", "https://news.yahoo.co.jp/ranking/comment"),
    ("domestic", "国内", "https://news.yahoo.co.jp/ranking/comment/domestic"),
    ("world", "国際", "https://news.yahoo.co.jp/ranking/comment/world"),
    ("business", "経済", "https://news.yahoo.co.jp/ranking/comment/business"),
    ("entertainment", "エンタメ", "https://news.yahoo.co.jp/ranking/comment/entertainment"),
    ("sports", "スポーツ", "https://news.yahoo.co.jp/ranking/comment/sports"),
    ("it-science", "IT・科学", "https://news.yahoo.co.jp/ranking/comment/it-science"),
    ("life", "ライフ", "https://news.yahoo.co.jp/ranking/comment/life"),
    ("local", "地域", "https://news.yahoo.co.jp/ranking/comment/local")
]

# スクレイプ実行時間（日本時間）
scrape_time = get_japan_time()

# 保存先フォルダ名（日本時間の年月日）
folder_name = scrape_time.strftime('%Y_%m%d_cmnt')

# 各ジャンルのニュースをスクレイプしてCSVに保存
try:
    for genre_en, genre_jp, url in genres:
        scrape_and_save_news(url, genre_en, genre_jp, folder_name, scrape_time)
        time.sleep(3)  # 3秒間の休止
except Exception as e:
    print(f"Process stopped due to error: {e}")
    exit(1)
