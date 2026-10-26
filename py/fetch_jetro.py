# ジェトロ ビジネス短信と世界の政治経済日程
# Version: 1.0
# Last Update: 2026-10-26
#
# 公式RSSの各記事本文と、日程ページが指す四半期記事をJSONで保存する。
# RSSは直近およそ20件しか残さないため、実行のたびにスナップショットを残す。
# 日程の本文は「10月」「【政治関連…】」「10月5～6日　行事名」の並び。

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RSS_URL = "https://www.jetro.go.jp/rss2/biznews.xml"
DIARY_URL = "https://www.jetro.go.jp/biznews/diary.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.jetro.go.jp/biznews/",
}
PAUSE_SECONDS = 0.8


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def article_url(link: str) -> str:
    link = link.strip()
    if not link.endswith(".html"):
        link += ".html"
    return link


def article_id(link: str) -> str:
    name = link.rstrip("/").split("/")[-1]
    return name[:-5] if name.endswith(".html") else name


def fetch(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=40)
    response.raise_for_status()
    return response.content.decode("utf-8")


def parse_regions(text: str) -> list[str]:
    matched = re.search(r"（(.+)）", text or "")
    if not matched:
        return []
    return [part.strip() for part in matched.group(1).split("、") if part.strip()]


def parse_published(text: str) -> str:
    matched = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text or "")
    if not matched:
        return ""
    year, month, day = matched.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def parse_events(container) -> list[dict]:
    month = ""
    category = ""
    events = []
    for element in container.find_all(["h2", "p"]):
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        if element.name == "h2":
            month = text
            category = ""
            continue
        if text.startswith("【") and "】" in text:
            category = text.strip("【】")
            continue
        if "\u3000" not in text:
            continue
        date_text, description = text.split("\u3000", 1)
        description = description.strip()
        if not description:
            continue
        events.append(
            {
                "month": month,
                "category": category,
                "date_text": date_text.strip(),
                "description": description,
            }
        )
    return events


def parse_article(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_element = soup.select_one("#elem_heading_lv1 h1")
    title = title_element.get_text(" ", strip=True) if title_element else ""
    region_element = soup.select_one("#elem_heading_lv1 .elem_paragraph.pb0 p")
    region_text = region_element.get_text(" ", strip=True) if region_element else ""
    department_element = soup.select_one("p.text.left")
    published_element = soup.select_one("p.gov_proc")
    body = soup.select_one(".elem_paragraph.wzg")
    paragraphs = []
    author = ""
    notes = []
    if body:
        for paragraph in body.find_all("p"):
            text = paragraph.get_text(" ", strip=True)
            if not text:
                continue
            if text.startswith("（注）"):
                notes.append(text)
                continue
            if re.fullmatch(r"（[^）]{1,30}）", text) and not text.startswith("（注"):
                author = text.strip("（）")
                continue
            paragraphs.append(text)
    return {
        "id": article_id(url),
        "title": title,
        "regions": parse_regions(region_text),
        "department": department_element.get_text(" ", strip=True) if department_element else "",
        "published": parse_published(published_element.get_text(" ", strip=True) if published_element else ""),
        "url": url,
        "author": author,
        "body": paragraphs,
        "notes": notes,
        "events": parse_events(body) if body else [],
    }


def parse_diary_index(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    editions = []
    for item in soup.select(".elem_list_news li"):
        link = item.select_one(".title a")
        if not link or not link.get("href"):
            continue
        title = link.get_text(" ", strip=True)
        href = link["href"]
        if href.startswith("/"):
            href = "https://www.jetro.go.jp" + href
        period = ""
        region = ""
        period_match = re.search(r"（(\d{4}年[^）]+)）", title)
        region_match = re.search(r"\)\((.+)\)\s*$", title.replace("（", "(").replace("）", ")"))
        if period_match:
            period = period_match.group(1)
        if region_match:
            region = region_match.group(1)
        date_element = item.select_one(".date")
        editions.append(
            {
                "title": title,
                "region": region,
                "period": period,
                "published": parse_published(date_element.get_text(" ", strip=True) if date_element else ""),
                "url": article_url(href),
            }
        )
    return editions


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rss_items(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        if not link:
            continue
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": article_url(link),
                "published_raw": (item.findtext("pubDate") or "").strip(),
                "category": (item.findtext("category") or "").strip(),
            }
        )
    return items


def main() -> None:
    fetched_at = now_iso()
    stamp = datetime.now(timezone.utc)
    out_dir = Path(f"rss_jetro_{stamp:%Y%m%d}")
    out_dir.mkdir(parents=True, exist_ok=True)
    rss_path = out_dir / f"jetro_biznews_{stamp:%Y%m%d_%H}.xml"

    with requests.Session() as session:
        session.headers.update(HEADERS)
        rss_text = fetch(session, RSS_URL)
        rss_path.write_text(rss_text, encoding="utf-8")
        items = rss_items(rss_text)
        if not items:
            raise SystemExit("JETRO RSS had no items")

        saved_articles = 0
        saved_diaries = 0
        seen = set()

        def save_page(url: str, edition: dict | None = None) -> None:
            nonlocal saved_articles, saved_diaries
            page_id = article_id(url)
            if page_id in seen:
                return
            seen.add(page_id)
            time.sleep(PAUSE_SECONDS)
            record = parse_article(fetch(session, url), url)
            record["fetched_at"] = fetched_at
            if not record["title"]:
                print(f"Warning: no title for {url}")
                return
            if record["events"] or (edition and "日程" in record["title"]):
                period = (edition or {}).get("period") or ""
                if not period:
                    period_in_title = re.search(r"（(\d{4}年[^）]+)）", record["title"])
                    period = period_in_title.group(1) if period_in_title else ""
                payload = {
                    "source": "jetro_diary",
                    "fetched_at": fetched_at,
                    "id": record["id"],
                    "title": record["title"],
                    "region": (edition or {}).get("region") or (record["regions"][0] if record["regions"] else ""),
                    "period": period,
                    "department": record["department"],
                    "published": record["published"],
                    "url": record["url"],
                    "events": record["events"],
                }
                write_json(out_dir / f"diary_{page_id}.json", payload)
                saved_diaries += 1
                print(f"Diary {page_id}: {len(record['events'])} events")
                return
            payload = {
                "source": "jetro_biznews",
                "fetched_at": fetched_at,
                **record,
            }
            payload.pop("events", None)
            write_json(out_dir / f"article_{page_id}.json", payload)
            saved_articles += 1
            print(f"Article {page_id}: {record['title'][:40]}")

        for item in items:
            try:
                save_page(item["link"])
            except requests.RequestException as exc:
                print(f"ERROR: article fetch failed {item['link']}: {exc}")

        diary_html = fetch(session, DIARY_URL)
        editions = parse_diary_index(diary_html)
        write_json(
            out_dir / "diary_index.json",
            {
                "source": "jetro_diary_index",
                "fetched_at": fetched_at,
                "url": DIARY_URL,
                "editions": editions,
            },
        )
        print(f"Diary index: {len(editions)} editions")
        for edition in editions:
            try:
                save_page(edition["url"], edition)
            except requests.RequestException as exc:
                print(f"ERROR: diary fetch failed {edition['url']}: {exc}")

    if saved_articles == 0:
        raise SystemExit("No JETRO articles were saved")
    print(f"Saved {saved_articles} articles and {saved_diaries} diary editions in {out_dir}")


if __name__ == "__main__":
    main()
