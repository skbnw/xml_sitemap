# v1.1.0 (2026-10-05): 一覧の記事リンクを CSS クラスではなく
# data-cl-params の _cl_link:article で取得する。
# Yahoo が styled-components のクラス名を変えたため、旧クラスでは 0 件になっていた。
import sys
import random 
import json
from datetime import datetime, timedelta
import pytz
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import time


# 日本時間のタイムゾーンを指定
JST = pytz.timezone('Asia/Tokyo')

# 日本時間のタイムゾーンを指定
JST = pytz.timezone('Asia/Tokyo')

# 作業日（実行日）の前日を日本時間で設定
# 引数から日付を取得
def get_target_date():
    if len(sys.argv) > 1:
        try:
            return datetime.strptime(sys.argv[1], '%Y-%m-%d')
        except ValueError:
            print(f"Invalid date format: {sys.argv[1]}. Use YYYY-MM-DD.")
    return datetime.now(JST) - timedelta(days=1)

TARGET_DATE = get_target_date()


# スクレイピング対象グループを限定
TARGET_GROUPS = ['g15']  # 必要に応じてグループを追加

# HTML構造の定義
EXPECTED_CLASSES = {
    "news_link": "sc-1gg21n8-0",          # ニュースリンクのクラス
    "content_div": "sc-278a0v-0",        # コンテンツ全体を含むdivのクラス
    "title_div": "sc-3ls169-0",          # タイトルを含むdivのクラス
    "time": "sc-16vsoxb-1",               # 時間表示のクラス
    "article_body": "article_body"   # 記事本文のクラス
}

def create_save_directory(target_date):
    """
    保存ディレクトリを作成する。
    py フォルダの親ディレクトリに、指定した日付のフォルダを作成。
    """
    current_dir = Path(__file__).parent.parent  # py フォルダの親ディレクトリ
    save_dir = current_dir / target_date.strftime('%Y-%m%d')  # 例: 2024-1231
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir




def save_articles_to_csv(article_data, media_en, target_date):
    """記事データをCSVに保存する"""
    if not article_data:
        return

    save_dir = create_save_directory(target_date)
    filename = f"{target_date.strftime('%Y%m%d')}-{media_en}.csv"
    file_path = save_dir / filename

    columns = [
        "headline",
        "mainEntityOfPage",
        "image",
        "datePublished",
        "dateModified",
        "author",
        "media_en",
        "media_jp",
        "str_count",
        "body",
        "images",
        "external_links"
    ]

    df = pd.DataFrame(article_data)
    df = df[columns]
    df.to_csv(file_path, index=False, encoding="utf-8")
    print(f"Articles saved as {file_path}")

def fetch_full_article(url, timeout_duration=30):
    """記事の本文を取得する"""
    full_text = ''
    json_ld_data = None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout_duration)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        script_tag = soup.find('script', type='application/ld+json')
        if script_tag:
            try:
                json_ld_data = json.loads(script_tag.string)
                if not isinstance(json_ld_data, dict):
                    json_ld_data = {}
            except json.JSONDecodeError:
                json_ld_data = {}

        article_body = soup.find('div', {'class': EXPECTED_CLASSES["article_body"]})
        if article_body:
            full_text = article_body.get_text('\n', strip=True)

        return re.sub(r'\s+', ' ', full_text).strip(), json_ld_data
    except Exception as e:
        print(f"Error fetching article {url}: {e}")
        return None, None


def get_yahoo_news_urls(base_url, target_date, timeout_duration=30, max_pages=20):
    """Yahooニュースから指定日付の記事リンクを取得する（ページ番号インクリメント方式）"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    urls = []

    # ターゲット日付をURLパラメータに追加
    year = target_date.year
    month = target_date.month
    day = target_date.day

    page = 1  # 初期ページ番号
    while page <= max_pages:
        current_url = f"{base_url}?year={year}&month={month}&day={day}&page={page}"
        print(f"Fetching page {page} from URL: {current_url}")
        try:
            response = requests.get(current_url, headers=headers, timeout=timeout_duration)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 記事リンクを取得。クラス名（sc-*）は配信のたびに変わるため使わない。
            news_items = soup.find_all(
                "a",
                attrs={"data-cl-params": re.compile(r"_cl_link:article")},
            )
            print(f"Found {len(news_items)} articles on page {page}.")
            
            if not news_items:
                print("No articles found on the current page. Stopping pagination.")
                break

            for item in news_items:
                article_url = item.get('href')
                if article_url and article_url not in urls:
                    urls.append(article_url)
                    print(f"Found article URL: {article_url}")

            page += 1  # 次のページへ進む
            time.sleep(random.uniform(1, 2))  # ページ間のスリープ
        except Exception as e:
            print(f"Error fetching page {page} from URL {current_url}: {e}")
            break

    print(f"Total {len(urls)} articles found for date {target_date.strftime('%Y-%m-%d')}.\n")
    return urls



def process_group(group, urls_df, target_date):
    """グループごとの処理を行う"""
    print(f"Processing group: {group}")
    group_data = urls_df[urls_df['group'] == group]

    if group_data.empty:
        print(f"No URLs found for group {group}")
        return

    for _, row in group_data.iterrows():
        media_en = row['media_en']
        media_jp = row['media_jp']
        base_url = row['url']

        # target_date を明示的に渡す
        article_links = get_yahoo_news_urls(base_url, target_date, max_pages=20)
        article_data = []

        for link in article_links:
            article_text, json_ld_data = fetch_full_article(link)
            if article_text and json_ld_data:
                article_data.append({
                    "headline": json_ld_data.get("headline", ""),
                    "mainEntityOfPage": json_ld_data.get("mainEntityOfPage", {}).get("@id", ""),
                    "image": json_ld_data.get("image", ""),
                    "datePublished": json_ld_data.get("datePublished", ""),
                    "dateModified": json_ld_data.get("dateModified", ""),
                    "author": json_ld_data.get("author", {}).get("name", ""),
                    "media_en": media_en,
                    "media_jp": media_jp,
                    "str_count": len(article_text),
                    "body": article_text,
                    "images": [],
                    "external_links": []
                })

        save_articles_to_csv(article_data, media_en, target_date)


def main():
    """メインの処理"""
    print(f"Starting scraping for date: {TARGET_DATE.strftime('%Y-%m-%d')}")

    csv_file_path = 'url/url_group.csv'  # リポジトリ内の相対パス
    urls_df = pd.read_csv(csv_file_path)

    for group in TARGET_GROUPS:
        process_group(group, urls_df, TARGET_DATE)

    print("\nAll processing completed!")

if __name__ == "__main__":
    main()