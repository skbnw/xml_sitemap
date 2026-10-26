"""
csv_to_gcs_yahoo_json.py
v1.2.0 — Yahoo CSV → 記事単位 JSON → GCS アップロード（並列パス）

追加機能:
  - y_body の日付フォルダ `{YYYY-MMDD}/{YYYYMMDD}-{media}.csv` を読み込み
  - 記事1件につき1 JSON（kyodo 風スキーマ、id は Yahoo 記事 ID）
  - gs://gcs-json-collector-raw/yahoo/YYYY/MM/{id}.json へアップロード
  - --dry-run / --skip-existing / --date / --limit
  - v1.1.0: GitHub Actions 向けに件数サマリーを GITHUB_OUTPUT へ出力（Discord 通知用）
  - v1.2.0: 日付未指定のときは YYYY-MMDD フォルダをすべて古い順にアップロードする
    （欠測日がリポジトリに残っているとき、最新1日だけになって取りこぼすのを防ぐ）

既存のローカル CSV 保存・Schedule-g01..g16 には干渉しない。
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

JST = timezone(timedelta(hours=9))
FULL_ARTICLE_MIN_CHARS = 300
DEFAULT_BUCKET = "gcs-json-collector-raw"
DEFAULT_PREFIX = "yahoo"
FOLDER_RE = re.compile(r"^(\d{4})-(\d{4})$")
YAHOO_ID_RE = re.compile(r"/articles/([a-f0-9]+)", re.IGNORECASE)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def jst_yesterday(now: datetime | None = None) -> datetime:
    now = now or datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def folder_name_for_date(d: datetime) -> str:
    """例: 2026-0302"""
    return d.strftime("%Y-%m%d")


def parse_date_arg(raw: str) -> datetime:
    """YYYY-MM-DD / YYYYMMDD / YYYY-MMDD を受理。"""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=JST)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid date: {raw!r}. Use YYYY-MM-DD, YYYYMMDD, or YYYY-MMDD."
    )


def extract_yahoo_id(url: str) -> str:
    m = YAHOO_ID_RE.search(url or "")
    if m:
        return m.group(1).lower()
    return hashlib.sha256((url or "").encode()).hexdigest()[:40]


def normalize_datetime(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()
    if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", raw):
        if "+" not in raw and "Z" not in raw:
            raw += "+09:00"
        return raw
    return None


def parse_list_field(raw: str | None) -> list:
    if not raw or str(raw).strip() in ("", "[]"):
        return []
    try:
        result = ast.literal_eval(str(raw).strip())
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        pass
    return []


def parse_media_list(image_url: str | None, images_raw: str | None) -> list[dict]:
    urls: set[str] = set()
    media: list[dict] = []
    if image_url and str(image_url).strip():
        url = str(image_url).strip()
        urls.add(url)
        media.append({"url": url, "caption": None})
    for url in parse_list_field(images_raw):
        if url and url not in urls:
            urls.add(url)
            media.append({"url": url, "caption": None})
    return media


def is_full_article(body: str, char_count_raw: str | None) -> bool:
    body_len = len(body.strip()) if body else 0
    try:
        reported = int(char_count_raw or 0)
        if reported > 0:
            return (body_len / reported) >= 0.70
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    return body_len >= FULL_ARTICLE_MIN_CHARS


def gcs_object_path(article_id: str, published_at: str | None, scraped_at: str) -> str:
    """yahoo/YYYY/MM/{id}.json — YYYY/MM は published_at 優先、なければ scraped_at。"""
    pivot = published_at or scraped_at
    year, month = "0000", "00"
    m = re.match(r"^(\d{4})-(\d{2})", pivot or "")
    if m:
        year, month = m.group(1), m.group(2)
    return f"{DEFAULT_PREFIX}/{year}/{month}/{article_id}.json"


def build_record(row: dict, scraped_at: str) -> dict | None:
    url = (row.get("mainEntityOfPage") or "").strip()
    if not url:
        return None

    body = row.get("body") or ""
    article_id = extract_yahoo_id(url)
    published = normalize_datetime(row.get("datePublished"))
    modified = normalize_datetime(row.get("dateModified"))

    return {
        "article_info": {
            "id": article_id,
            "url": url,
            "title": (row.get("headline") or "").strip() or "",
            "publisher": (row.get("media_jp") or "").strip() or "",
            "original_url": "",
        },
        "publication_info": {
            "published": published,
            "modified": modified,
            "rss_date": None,
            "category": "",
            "author": (row.get("author") or "").strip() or None,
        },
        "content": {
            "main_text": body.strip() or "",
            "content_type": "full" if is_full_article(body, row.get("str_count")) else "excerpt",
            "char_count": len(body.strip()),
            "summary": "",
            "media_list": parse_media_list(row.get("image"), row.get("images")),
            "links": parse_list_field(row.get("external_links")),
        },
        "metadata": {
            "source": "Yahoo News",
            "media": "yahoo",
            "source_code": (row.get("media_en") or "").strip() or None,
            "scraped_at": scraped_at,
            "collector": "y_body/csv_to_gcs_yahoo_json",
            "language": "ja",
        },
    }


def iter_csv_rows(csv_path: Path) -> Iterator[dict]:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return
        for row in reader:
            yield row


def resolve_date_dirs(repo_root: Path, date: datetime | None) -> list[Path]:
    if date is not None:
        folder = repo_root / folder_name_for_date(date)
        if not folder.is_dir():
            raise FileNotFoundError(f"Date folder not found: {folder}")
        return [folder]

    # 明示日付なし: リポジトリにある YYYY-MMDD をすべて古い順に処理する。
    # 欠測リカバリで複数日が残っていても、最新1日だけにならない。
    yesterday = folder_name_for_date(jst_yesterday())
    candidates = sorted(
        (p for p in repo_root.iterdir() if p.is_dir() and FOLDER_RE.match(p.name)),
        key=lambda p: p.name,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No date folders under {repo_root} (expected e.g. {yesterday})"
        )
    names = [p.name for p in candidates]
    if yesterday not in names:
        logger.warning(
            "JST yesterday folder %s missing; uploading %d folder(s): %s",
            yesterday,
            len(names),
            ", ".join(names),
        )
    else:
        logger.info("Uploading %d date folder(s): %s", len(names), ", ".join(names))
    return candidates


def get_storage_client():
    from google.cloud import storage  # type: ignore

    return storage.Client()


def object_exists(bucket, object_name: str) -> bool:
    return bucket.blob(object_name).exists()


def upload_json(bucket, object_name: str, payload: dict, dry_run: bool) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    if dry_run:
        logger.info("[dry-run] would upload gs://%s/%s (%d bytes)", bucket.name, object_name, len(body.encode("utf-8")))
        return
    blob = bucket.blob(object_name)
    blob.upload_from_string(body, content_type="application/json; charset=utf-8")
    logger.debug("uploaded gs://%s/%s", bucket.name, object_name)


def write_github_output(stats: dict[str, int], date_folder: str) -> None:
    """GitHub Actions のステップ出力へ件数を書き出す。ローカル実行時は何もしない。"""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    values = {
        "date_folder": date_folder,
        "files": stats["files"],
        "rows": stats["rows"],
        "uploaded": stats["uploaded"],
        "skipped": stats["skipped"],
        "errors": stats["errors"],
    }
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def process(
    *,
    repo_root: Path,
    date: datetime | None,
    bucket_name: str,
    dry_run: bool,
    skip_existing: bool,
    limit: int | None,
    local_out: Path | None,
) -> tuple[dict[str, int], str]:
    scraped_at = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    date_dirs = resolve_date_dirs(repo_root, date)
    date_folder = ",".join(d.name for d in date_dirs)
    stats = {"files": 0, "rows": 0, "uploaded": 0, "skipped": 0, "errors": 0}

    bucket = None
    if not dry_run or skip_existing:
        try:
            client = get_storage_client()
            bucket = client.bucket(bucket_name)
        except Exception as e:
            if dry_run and not skip_existing:
                logger.warning("GCS client unavailable in dry-run (ok): %s", e)
            else:
                raise

    if local_out:
        local_out.mkdir(parents=True, exist_ok=True)

    done = 0
    for date_dir in date_dirs:
        csv_files = sorted(date_dir.glob("*.csv"))
        logger.info("Processing %s (%d csv files)", date_dir.name, len(csv_files))
        for csv_path in csv_files:
            stats["files"] += 1
            try:
                for row in iter_csv_rows(csv_path):
                    stats["rows"] += 1
                    record = build_record(row, scraped_at)
                    if record is None:
                        stats["skipped"] += 1
                        continue

                    aid = record["article_info"]["id"]
                    published = record["publication_info"].get("published")
                    object_name = gcs_object_path(aid, published, scraped_at)

                    if skip_existing and bucket is not None:
                        try:
                            if object_exists(bucket, object_name):
                                stats["skipped"] += 1
                                continue
                        except Exception as e:
                            logger.warning("exists check failed for %s: %s", object_name, e)

                    if local_out is not None:
                        out_file = local_out / f"{aid}.json"
                        out_file.write_text(
                            json.dumps(record, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )

                    if dry_run and bucket is None:
                        logger.info(
                            "[dry-run] %s -> gs://%s/%s",
                            csv_path.name,
                            bucket_name,
                            object_name,
                        )
                    else:
                        try:
                            if bucket is None and not dry_run:
                                raise RuntimeError("GCS bucket client is not initialized")
                            if bucket is not None:
                                upload_json(bucket, object_name, record, dry_run=dry_run)
                            elif dry_run:
                                logger.info(
                                    "[dry-run] %s -> gs://%s/%s",
                                    csv_path.name,
                                    bucket_name,
                                    object_name,
                                )
                        except Exception as e:
                            stats["errors"] += 1
                            logger.error("upload failed %s: %s", object_name, e)
                            continue

                    stats["uploaded"] += 1
                    done += 1
                    if limit is not None and done >= limit:
                        logger.info("Reached --limit %d", limit)
                        return stats, date_folder
            except Exception as e:
                stats["errors"] += 1
                logger.error("CSV failed %s: %s", csv_path, e)

    return stats, date_folder


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert y_body Yahoo CSV to per-article JSON and upload to GCS"
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="y_body repository root (contains YYYY-MMDD folders)",
    )
    p.add_argument(
        "--date",
        type=parse_date_arg,
        default=None,
        help="Scrape date folder (JST). Default: every YYYY-MMDD folder",
    )
    p.add_argument("--bucket", default=DEFAULT_BUCKET, help="GCS bucket name")
    p.add_argument("--dry-run", action="store_true", help="No GCS writes")
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip objects that already exist in GCS",
    )
    p.add_argument("--limit", type=int, default=None, help="Max articles to process")
    p.add_argument(
        "--local-out",
        type=Path,
        default=None,
        help="Optional local directory to write JSON copies",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)
    logger.info(
        "start dry_run=%s skip_existing=%s date=%s bucket=%s",
        args.dry_run,
        args.skip_existing,
        folder_name_for_date(args.date) if args.date else "(auto)",
        args.bucket,
    )
    try:
        stats, date_folder = process(
            repo_root=args.repo_root.resolve(),
            date=args.date,
            bucket_name=args.bucket,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            limit=args.limit,
            local_out=args.local_out,
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1

    logger.info(
        "done date=%s files=%d rows=%d uploaded=%d skipped=%d errors=%d",
        date_folder,
        stats["files"],
        stats["rows"],
        stats["uploaded"],
        stats["skipped"],
        stats["errors"],
    )
    write_github_output(stats, date_folder)
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
