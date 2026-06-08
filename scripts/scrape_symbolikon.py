#!/usr/bin/env python3
"""Scrape symbol data from symbolikon.com via WordPress REST API."""

import json
import re
import time
import html
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://symbolikon.com"
JINA_PROXY = "https://r.jina.ai/"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
SYMBOLS_FILE = OUTPUT_DIR / "symbols.json"
CATEGORIES_FILE = OUTPUT_DIR / "categories.json"
TAGS_FILE = OUTPUT_DIR / "tags.json"

def sanitize_json_string(s: str) -> str:
    result = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            result.append(ch)
            escape = False
            continue
        if ch == "\\":
            result.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch in "\n\r\t":
            result.append(" ")
            continue
        result.append(ch)
    return "".join(result)


SKIP_TITLE_KEYWORDS = (
    "pdf booklet",
    "color palette",
    "poster",
    "all access pass",
    "subscription",
    "font",
    "pass",
    "bundle",
    "booklet",
)


def fetch_json(url: str, retries: int = 6) -> list | dict:
    proxy_url = JINA_PROXY + url
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                proxy_url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            text = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace").strip()
            if text.startswith("{"):
                outer = json.loads(text)
                if isinstance(outer.get("data"), dict) and outer["data"].get("content"):
                    inner = outer["data"]["content"]
                    if isinstance(inner, str):
                        cleaned = sanitize_json_string(inner)
                        start = cleaned.find("[") if "[" in cleaned else cleaned.find("{")
                        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
                        return obj
                    return inner

            match = re.search(r"Markdown Content:\s*\n", text)
            if not match:
                preview = text[:200].replace("\n", " ")
                raise ValueError(f"No markdown section in response for {url}: {preview}")
            content = sanitize_json_string(text[match.end() :])
            start = content.find("[") if "[" in content else content.find("{")
            if start < 0:
                raise ValueError(f"No JSON payload in response for {url}")
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(content[start:])
            return obj
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_description(content_html: str) -> tuple[str, str]:
    text = strip_html(content_html)
    description = ""
    general_info = ""

    desc_match = re.search(
        r"Description of [^:]+?\s+(.+?)(?=Style Variations|General .+ description|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if desc_match:
        description = desc_match.group(1).strip()

    general_match = re.search(
        r"General .+? description\s+(.+?)(?=Style Variations|Bold – Light|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if general_match:
        general_info = general_match.group(1).strip()

    if not description and text:
        description = text[:2000]

    return description, general_info


def tags_from_class_list(class_list: list[str]) -> list[str]:
    tags = []
    for cls in class_list:
        if cls.startswith("download_tag-"):
            tags.append(cls.replace("download_tag-", "").replace("-", " "))
    return sorted(set(tags))


def categories_from_class_list(class_list: list[str]) -> list[str]:
    cats = []
    for cls in class_list:
        if cls.startswith("download_category-"):
            cats.append(cls.replace("download_category-", "").replace("-", " "))
    return sorted(set(cats))


def is_symbol_item(title: str, slug: str) -> bool:
    lower = title.lower()
    slug_lower = slug.lower()
    if any(kw in lower for kw in SKIP_TITLE_KEYWORDS):
        return False
    if any(kw in slug_lower for kw in ("booklet", "palette", "poster", "subscription", "pass", "font")):
        return False
    return True


def get_image_url(item: dict, media_map: dict[int, str]) -> str:
    embedded = item.get("_embedded", {})
    media = embedded.get("wp:featuredmedia", [])
    if media:
        return media[0].get("source_url", "")
    media_id = item.get("featured_media")
    if media_id:
        return media_map.get(media_id, "")
    return ""


def fetch_media_map(media_ids: list[int]) -> dict[int, str]:
    media_map: dict[int, str] = {}
    unique_ids = sorted({mid for mid in media_ids if mid})
    for i in range(0, len(unique_ids), 100):
        chunk = unique_ids[i : i + 100]
        include = ",".join(str(mid) for mid in chunk)
        url = f"{BASE_URL}/wp-json/wp/v2/media?include={include}&per_page=100&_fields=id,source_url"
        print(f"Fetching media batch {i // 100 + 1} ({len(chunk)} ids)...")
        try:
            batch = fetch_json(url)
            for item in batch:
                media_map[item["id"]] = item.get("source_url", "")
        except Exception as exc:
            print(f"  media batch failed: {exc}")
        time.sleep(0.5)
    return media_map


def transform_download(
    item: dict, category_map: dict, tag_map: dict, media_map: dict[int, str]
) -> dict | None:
    title = strip_html(item.get("title", {}).get("rendered", ""))
    slug = item.get("slug", "")
    if not title or not is_symbol_item(title, slug):
        return None

    content_html = item.get("content", {}).get("rendered", "")
    description, general_info = parse_description(content_html)
    if not description and not general_info:
        return None

    class_list = item.get("class_list", [])
    category_ids = item.get("edd-categories", [])
    tag_ids = item.get("edd-tags", [])

    categories = [category_map.get(cid, categories_from_class_list(class_list)[0] if categories_from_class_list(class_list) else "") for cid in category_ids]
    categories = [c for c in categories if c]
    if not categories:
        categories = categories_from_class_list(class_list)

    tags = [tag_map.get(tid, "") for tid in tag_ids]
    tags = [t for t in tags if t]
    if not tags:
        tags = tags_from_class_list(class_list)

    culture = categories[0] if categories else ""
    region = ""

    return {
        "id": slug,
        "name": title,
        "slug": slug,
        "url": item.get("link", ""),
        "culture": culture,
        "region": region,
        "description": description,
        "general_info": general_info,
        "tags": tags,
        "categories": categories,
        "image_url": get_image_url(item, media_map),
        "source_id": item.get("id"),
        "featured_media": item.get("featured_media"),
    }


def fetch_paginated(endpoint: str, fields: str | None = None) -> list:
    all_items = []
    page = 1
    while True:
        params = f"per_page=100&page={page}"
        if fields:
            params += f"&_fields={fields}"
        url = f"{BASE_URL}{endpoint}?{params}"
        print(f"Fetching {url}")
        batch = fetch_json(url)
        if not batch:
            break
        all_items.extend(batch)
        print(f"  got {len(batch)} (total {len(all_items)})")
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.5)
    return all_items


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching categories...")
    categories_raw = fetch_paginated(
        "/wp-json/wp/v2/edd-categories",
        fields="id,name,slug,count,link",
    )
    category_map = {c["id"]: c["name"] for c in categories_raw}
    categories_out = [
        {
            "id": c["id"],
            "name": c["name"],
            "slug": c["slug"],
            "count": c.get("count", 0),
            "description": strip_html(c.get("description", "")),
            "url": c.get("link", ""),
        }
        for c in categories_raw
    ]
    CATEGORIES_FILE.write_text(json.dumps(categories_out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Fetching tags...")
    tags_raw = fetch_paginated("/wp-json/wp/v2/edd-tags", fields="id,name,slug,count")
    tag_map = {t["id"]: t["name"] for t in tags_raw}
    tags_out = [{"id": t["id"], "name": t["name"], "slug": t["slug"], "count": t.get("count", 0)} for t in tags_raw]
    TAGS_FILE.write_text(json.dumps(tags_out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Fetching downloads...")
    symbols: list[dict] = []
    seen_slugs: set[str] = set()
    raw_items: list[dict] = []
    failed_pages: list[int] = []
    page = 1
    per_page = 50
    fields = "id,slug,title,link,class_list,edd-categories,edd-tags,content,featured_media"
    empty_pages = 0

    while empty_pages < 2:
        url = f"{BASE_URL}/wp-json/wp/v2/edd-downloads?per_page={per_page}&page={page}&_fields={fields}"
        print(f"Fetching page {page}...")
        try:
            batch = fetch_json(url)
        except Exception as exc:
            print(f"  page {page} failed: {exc}")
            failed_pages.append(page)
            page += 1
            time.sleep(2)
            continue
        if not batch:
            empty_pages += 1
            page += 1
            continue
        empty_pages = 0
        raw_items.extend(batch)
        print(f"  got {len(batch)} items ({len(raw_items)} raw total)")
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(0.75)

    media_map = fetch_media_map([item.get("featured_media", 0) for item in raw_items])

    for item in raw_items:
        symbol = transform_download(item, category_map, tag_map, media_map)
        if symbol and symbol["slug"] not in seen_slugs:
            seen_slugs.add(symbol["slug"])
            symbol.pop("featured_media", None)
            symbols.append(symbol)

    symbols.sort(key=lambda s: (s.get("culture", "").lower(), s.get("name", "").lower()))
    SYMBOLS_FILE.write_text(json.dumps(symbols, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"\nSaved {len(symbols)} symbols, {len(categories_out)} categories, {len(tags_out)} tags"
        + (f" ({len(failed_pages)} failed pages)" if failed_pages else "")
    )


if __name__ == "__main__":
    main()
