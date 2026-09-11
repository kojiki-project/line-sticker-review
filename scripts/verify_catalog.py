#!/usr/bin/env python3
"""Deterministically validate the static LINE sticker catalog."""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel", "data"}


class URLCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"href", "src", "poster"} and value:
                self.urls.append((f"{tag}[{key}]", value))


def png_info(path: Path) -> tuple[int, int, set[bytes]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE) or len(data) < 33:
        raise ValueError("not a valid PNG")
    width, height = struct.unpack(">II", data[16:24])
    chunks: set[bytes] = set()
    offset = 8
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk = data[offset + 4 : offset + 8]
        chunks.add(chunk)
        offset += 12 + length
        if chunk == b"IEND":
            break
    return width, height, chunks


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def is_external(url: str) -> bool:
    return urlsplit(url).scheme.lower() in EXTERNAL_SCHEMES or url.startswith("//")


def local_target(root: Path, base: Path, url: str) -> Path | None:
    clean = unquote(urlsplit(url).path)
    if not clean or clean.startswith("#") or is_external(url):
        return None
    return (base / clean).resolve()


def verify(root: Path, expected_products: int, expected_items: int) -> list[str]:
    errors: list[str] = []
    checks = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(message)

    required_root = ["index.html", "styles.css", "app.js", ".nojekyll", "README.md"]
    for rel in required_root:
        require((root / rel).is_file(), f"missing required file: {rel}")

    index_path = root / "data/products/index.json"
    require(index_path.is_file(), "missing data/products/index.json")
    if not index_path.is_file():
        print(f"FAIL: {len(errors)} error(s) after {checks} checks")
        return errors

    try:
        product_index = load_json(index_path)
    except Exception as exc:
        errors.append(f"invalid data/products/index.json: {exc}")
        return errors

    products = product_index.get("products", []) if isinstance(product_index, dict) else []
    require(len(products) == expected_products, f"expected {expected_products} product, found {len(products)}")

    for entry in products:
        data_url = entry.get("data", "")
        require(bool(data_url), "product index entry has no data path")
        data_path = (root / data_url).resolve()
        require(root.resolve() in data_path.parents, f"product data escapes root: {data_url}")
        require(data_path.is_file(), f"missing product data: {data_url}")
        if not data_path.is_file():
            continue
        try:
            product = load_json(data_path)
        except Exception as exc:
            errors.append(f"invalid product data {data_url}: {exc}")
            continue

        for field in ("slug", "title", "description", "status_note", "assets", "downloads", "qa", "items"):
            require(bool(product.get(field)), f"{data_url}: missing product field {field}")
        items = product.get("items", [])
        require(len(items) == expected_items, f"{data_url}: expected {expected_items} items, found {len(items)}")
        ids = [item.get("id") for item in items]
        require(len(ids) == len(set(ids)), f"{data_url}: duplicate item id")

        product_asset_fields = ["main", "tab", "preview_video", "contact_sheet", "start_end_sheet", "character_sheet"]
        for field in product_asset_fields:
            rel = product.get("assets", {}).get(field, "")
            require(bool(rel), f"{data_url}: missing assets.{field}")
            require((root / rel).is_file(), f"{data_url}: missing asset {rel}")

        line_zip = product.get("downloads", {}).get("line_upload", {}).get("url", "")
        complete_url = product.get("downloads", {}).get("complete_delivery", {}).get("url", "")
        require(bool(line_zip) and not is_external(line_zip), f"{data_url}: LINE upload ZIP must be a local URL")
        require((root / line_zip).is_file(), f"{data_url}: missing LINE upload ZIP {line_zip}")
        require(complete_url.startswith("https://github.com/kojiki-project/line-sticker-review/releases/download/"), f"{data_url}: unexpected complete-delivery URL")

        for item in items:
            item_id = item.get("id", "?")
            for field in ("text", "character", "character_label", "intended_use", "start", "end"):
                value = item.get(field)
                require(isinstance(value, str) and bool(value.strip()), f"item {item_id}: missing label {field}")
            for field in ("animation", "start_image", "end_image"):
                rel = item.get(field, "")
                require(bool(rel), f"item {item_id}: missing {field}")
                path = root / rel
                require(path.is_file(), f"item {item_id}: missing file {rel}")
                if path.is_file() and field == "animation":
                    try:
                        width, height, chunks = png_info(path)
                        expected = item.get("dimensions")
                        require(b"acTL" in chunks, f"item {item_id}: animation has no APNG acTL chunk")
                        if expected:
                            require([width, height] == expected, f"item {item_id}: expected {expected}, found {[width, height]}")
                    except Exception as exc:
                        errors.append(f"item {item_id}: invalid PNG/APNG: {exc}")

    html_path = root / "index.html"
    if html_path.is_file():
        parser = URLCollector()
        parser.feed(html_path.read_text(encoding="utf-8"))
        for where, url in parser.urls:
            target = local_target(root, root, url)
            if target is not None:
                require(root.resolve() in target.parents or target == root.resolve(), f"index.html {where} escapes root: {url}")
                require(target.is_file(), f"index.html {where} missing target: {url}")

    css_path = root / "styles.css"
    if css_path.is_file():
        css = css_path.read_text(encoding="utf-8")
        for url in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", css):
            target = local_target(root, root, url)
            if target is not None:
                require(root.resolve() in target.parents or target == root.resolve(), f"styles.css URL escapes root: {url}")
                require(target.is_file(), f"styles.css missing target: {url}")

    forbidden_zip = list(root.rglob("*complete_delivery*.zip"))
    require(not forbidden_zip, f"complete-delivery ZIP must not be copied into catalog: {forbidden_zip}")

    if errors:
        print(f"FAIL: {len(errors)} error(s) after {checks} checks")
    else:
        print(f"PASS: {checks} checks")
        print(f"  products: {expected_products}")
        print(f"  sticker items: {expected_items}")
        print("  APNG acTL and dimensions: verified")
        print("  internal relative URLs and required downloads: verified")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected-products", type=int, default=1)
    parser.add_argument("--expected-items", type=int, default=16)
    args = parser.parse_args()
    errors = verify(args.root.resolve(), args.expected_products, args.expected_items)
    for error in errors:
        print(f"  - {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
