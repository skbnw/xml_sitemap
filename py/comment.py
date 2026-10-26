# Yahoo!ニュース コメントランキング
# Version: 1.1
# Last Update: 2026-10-26
#
# 変更履歴:
# - v1.1 (2026-10-26): 生成クラス名への依存をやめ、rank.py と同じ構造で取る。
#   順位は data-cl-params、見出しは最長の直下テキスト、媒体は time の隣、
#   コメント数は「件/時」の数値。0件のときはワークフローを失敗させる。
# - v1.0: .sc-1hy2mez-* などを直接指定。クラス名の変更で見出しが空になり、その後CSVが止まった。

import os
import re
import time
from datetime import datetime

import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup


GENRES = [
    ("https://news.yahoo.co.jp/ranking/comment", "TTL", "総合"),
    ("https://news.yahoo.co.jp/ranking/comment/domestic", "domestic", "国内"),
    ("https://news.yahoo.co.jp/ranking/comment/world", "world", "国際"),
    ("https://news.yahoo.co.jp/ranking/comment/business", "business", "経済"),
    ("https://news.yahoo.co.jp/ranking/comment/entertainment", "entertainment", "エンタメ"),
    ("https://news.yahoo.co.jp/ranking/comment/sports", "sports", "スポーツ"),
    ("https://news.yahoo.co.jp/ranking/comment/it-science", "it-science", "IT・科学"),
    ("https://news.yahoo.co.jp/ranking/comment/life", "life", "ライフ"),
    ("https://news.yahoo.co.jp/ranking/comment/local", "local", "地域"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def get_japan_time():
    return datetime.now(pytz.timezone("Asia/Tokyo"))


def direct_text(tag):
    """Return text directly owned by a tag, excluding its child tags."""
    return " ".join(
        text.strip() for text in tag.find_all(string=True, recursive=False) if text.strip()
    )


def extract_comment_count(item):
    """コメント数は「件/時」の直前にある数値。生成クラス名は見ない。"""
    for node in item.find_all(string=re.compile(r"件\s*/\s*時")):
        parent = node.parent
        if parent is None:
            continue
        emphasized = parent.find("em")
        if emphasized:
            digits = re.sub(r"[^\d]", "", emphasized.get_text(strip=True))
            if digits:
                return digits
        matched = re.search(r"(\d[\d,]*)", parent.get_text(" ", strip=True))
        if matched:
            return matched.group(1).replace(",", "")
    return ""


def extract_item(item, fallback_rank):
    """Extract one comment-ranking row without generated CSS class names."""
    link_element = item.find_parent("a", href=True)
    time_element = item.find("time")
    if not link_element or not time_element:
        return None

    params = link_element.get("data-cl-params", "")
    match = re.search(r"_cl_position:(\d+)", params)
    rank = match.group(1) if match else str(fallback_rank)

    title_candidates = [direct_text(tag) for tag in item.find_all("div")]
    title_candidates = [text for text in title_candidates if text]
    title = max(title_candidates, key=len, default="")

    media_element = time_element.find_previous_sibling("span")
    media = media_element.get_text(" ", strip=True) if media_element else ""
    comment = extract_comment_count(item)

    if not title or not media or not comment:
        return None

    return {
        "rank": rank,
        "media_jp": media,
        "title": title,
        "comment": comment,
        "link": requests.compat.urljoin(link_element.get("href"), link_element.get("href")),
        "date_original": time_element.get_text(" ", strip=True),
    }


def scrape_and_save_news(session, url, genre_en, genre_jp, folder_name, scrape_datetime):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select(".newsFeed_item_body")

    news_data = []
    for index, item in enumerate(items, 1):
        extracted = extract_item(item, index)
        if not extracted:
            print(f"Warning: required elements not found for item {index}, skipping")
            continue
        news_data.append(
            [
                scrape_datetime.strftime("%Y-%m-%d"),
                scrape_datetime.strftime("%H:%M"),
                genre_en,
                genre_jp,
                extracted["rank"],
                extracted["media_jp"],
                extracted["title"],
                extracted["comment"],
                extracted["link"],
                extracted["date_original"],
            ]
        )

    if not news_data:
        print(f"ERROR: no comment ranking data found for {genre_en} at {url}")
        return 0

    os.makedirs(folder_name, exist_ok=True)
    filename = os.path.join(
        folder_name, f"{scrape_datetime.strftime('%Y_%m%d_%H%M')}_cmnt_{genre_en}.csv"
    )
    columns = [
        "scrp_date", "scrp_time", "genre_en", "genre_jp", "rank",
        "media_jp", "title", "comment", "link", "date_original",
    ]
    pd.DataFrame(news_data, columns=columns).to_csv(
        filename, index=False, encoding="utf-8-sig"
    )
    print(f"Saved {len(news_data)} rows to {filename}")
    return len(news_data)


def main():
    scrape_time = get_japan_time()
    folder_name = scrape_time.strftime("%Y_%m%d_cmnt")
    total_rows = 0

    with requests.Session() as session:
        session.headers.update(HEADERS)
        for index, (url, genre_en, genre_jp) in enumerate(GENRES):
            try:
                total_rows += scrape_and_save_news(
                    session, url, genre_en, genre_jp, folder_name, scrape_time
                )
            except requests.RequestException as exc:
                print(f"ERROR: request failed for {genre_en}: {exc}")
            if index < len(GENRES) - 1:
                time.sleep(3)

    if total_rows == 0:
        raise SystemExit("No comment ranking rows were collected; failing the workflow")
    print(f"Collection complete: {total_rows} rows")


if __name__ == "__main__":
    main()
