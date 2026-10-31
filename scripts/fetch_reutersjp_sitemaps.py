#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_reutersjp_sitemaps.py — Reuters JP sitemap 取得（GitHub Actions / ローカル）

v1.2 (2026-10-31)
  - ウォームアップ: www.reuters.com/world/japan/
  - page.evaluate(fetch) で outboundfeeds XML 取得
  - index 失敗時は jp/news-sitemap 直 URL にフォールバック
v1.1 (2026-10-26)
  - Reuters 新形式: news-sitemap-index → www.reuters.com/.../jp/news-sitemap/ をたどる
v1.0 (2026-10-26)
  - DataDome 対策: Playwright + ページ遷移で sitemap 取得
  - CHROME_CDP_URL 指定時は既存 Chrome(CDP) に接続（推奨・セルフホスト runner）
  - 出力: rss_reutersjp_YYYYMMDD/ （既存 transfer_sitemap_multi 互換）
  - 取得失敗時は exit 1（空 commit の success を防ぐ）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

NEWS_INDEX = (
    "https://www.reuters.com/arc/outboundfeeds/news-sitemap-index/?outputType=xml"
)
SITEMAP_INDEX = (
    "https://www.reuters.com/arc/outboundfeeds/sitemap-index/?outputType=xml"
)
JP_NEWS_SITEMAP = (
    "https://www.reuters.com/arc/outboundfeeds/jp/news-sitemap/?outputType=xml"
)
HOME = "https://www.reuters.com/world/japan/"

CHROME_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-automation",
    "--no-first-run",
]

INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
"""


def is_xml(body: bytes) -> bool:
    if not body or len(body) < 20:
        return False
    head = body.lstrip()[:300].lower()
    if b"captcha-delivery.com" in head or b"please enable js" in head:
        return False
    return head.startswith(b"<?xml") or head.startswith(b"<")


def loc_urls(root: ET.Element) -> list[str]:
    urls: list[str] = []
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == "loc" and el.text and el.text.strip():
            urls.append(el.text.strip())
    return urls


def from_param(url: str) -> str:
    m = re.search(r"from=(\d+)", url)
    if m:
        return m.group(1)
    if "/jp/news-sitemap" in url:
        return "jp"
    return "0"


async def fetch_bytes_via_evaluate(page, url: str) -> bytes:
    result = await page.evaluate(
        """async (url) => {
            const res = await fetch(url, { credentials: "include" });
            const text = await res.text();
            return { status: res.status, text };
        }""",
        url,
    )
    status = int(result.get("status") or 0)
    body = (result.get("text") or "").encode("utf-8", errors="replace")
    if status >= 400:
        raise RuntimeError(f"HTTP {status} for {url}")
    if not is_xml(body):
        raise RuntimeError(f"non-XML for {url}")
    return body


async def fetch_bytes(page, url: str) -> bytes:
    """evaluate(fetch) 優先、失敗時はページ遷移。"""
    try:
        return await fetch_bytes_via_evaluate(page, url)
    except Exception as exc:
        print(f"  evaluate fetch failed ({exc}); trying goto", flush=True)
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    status = resp.status if resp else 0
    body = (await resp.body()) if resp else b""
    if not body:
        body = (await page.content()).encode("utf-8", errors="replace")
    if status and status >= 400:
        raise RuntimeError(f"HTTP {status} for {url}")
    if not is_xml(body):
        raise RuntimeError(f"non-XML for {url}")
    return body


async def run(out_dir: Path, today: str) -> int:
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    cdp_url = (os.environ.get("CHROME_CDP_URL") or "").strip()

    async with async_playwright() as p:
        if cdp_url:
            print(f"=== CDP connect: {cdp_url} ===", flush=True)
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
        else:
            browser = await p.chromium.launch(headless=True, args=CHROME_ARGS)
            context = await browser.new_context(
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1365, "height": 900},
                ignore_https_errors=True,
            )
            await context.add_init_script(INIT_SCRIPT)

        page = context.pages[0] if context.pages else await context.new_page()
        print(f"=== Warm-up: {HOME} ===", flush=True)
        await page.goto(HOME, wait_until="domcontentloaded", timeout=90_000)
        await page.wait_for_timeout(8000)
        title = await page.title()
        if not any(k in (title or "") for k in ("reuters", "ロイター")):
            print(f"  warn: unexpected homepage title: {title!r}", flush=True)

        # 全体 index（任意）
        try:
            raw = await fetch_bytes(page, SITEMAP_INDEX)
            if is_xml(raw):
                path = out_dir / f"reutersjp_sitemap_index_{today}.xml"
                path.write_bytes(raw)
                saved += 1
                print(f"  saved {path.name}", flush=True)
            else:
                print("  skip sitemap-index (not XML / blocked)", flush=True)
        except Exception as exc:
            print(f"  warn sitemap-index: {exc}", flush=True)

        print(f"=== news-sitemap-index: {NEWS_INDEX} ===", flush=True)
        child_urls: list[str] = []
        try:
            index_raw = await fetch_bytes(page, NEWS_INDEX)
            if is_xml(index_raw):
                index_path = out_dir / f"reutersjp_news_sitemap_index_{today}.xml"
                index_path.write_bytes(index_raw)
                saved += 1
                root = ET.fromstring(index_raw)
                for u in loc_urls(root):
                    if "news-sitemap" not in u:
                        continue
                    if "jp.reuters.com" in u or "/jp/news-sitemap" in u:
                        child_urls.append(u)
            else:
                print("  warn: news-sitemap-index response not XML", flush=True)
        except Exception as exc:
            print(f"  warn news-sitemap-index: {exc}", flush=True)

        if not child_urls:
            print(f"  fallback child: {JP_NEWS_SITEMAP}", flush=True)
            child_urls = [JP_NEWS_SITEMAP]
            fallback_index = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"<sitemap><loc>{JP_NEWS_SITEMAP}</loc></sitemap>"
                "</sitemapindex>"
            ).encode("utf-8")
            index_path = out_dir / f"reutersjp_news_sitemap_index_{today}.xml"
            index_path.write_bytes(fallback_index)
            saved += 1
        url_list_path = out_dir / f"reutersjp_news_sitemap_urls_{today}.txt"
        url_list_path.write_text("\n".join(child_urls) + ("\n" if child_urls else ""), encoding="utf-8")
        print(f"  child sitemaps: {len(child_urls)}", flush=True)

        for child_url in child_urls:
            from_val = from_param(child_url)
            out_file = out_dir / f"reutersjp_news_from{from_val}_{today}.xml"
            print(f"  fetch from={from_val}", flush=True)
            try:
                child_raw = await fetch_bytes(page, child_url)
            except Exception as exc:
                print(f"    skip: {exc}", flush=True)
                continue
            if not is_xml(child_raw):
                print("    skip: response not XML", flush=True)
                continue
            out_file.write_bytes(child_raw)
            saved += 1

        if not cdp_url:
            await browser.close()

    print(f"=== Done: {saved} files in {out_dir} ===", flush=True)
    if saved < 2:
        print("[ERROR] too few files saved (expected index + >=1 child)", flush=True)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y%m%d"),
        help="UTC YYYYMMDD (folder rss_reutersjp_YYYYMMDD)",
    )
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = ap.parse_args()
    out_dir = args.repo_root / f"rss_reutersjp_{args.date}"

    import asyncio

    return asyncio.run(run(out_dir, args.date))


if __name__ == "__main__":
    sys.exit(main())
