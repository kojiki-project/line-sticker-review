#!/usr/bin/env python3
"""Add or refresh a LINE sticker product from a finished source package."""
from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

CHARACTER_SPECIES = {"dog": "いぬ", "cat": "ねこ", "bunny": "うさぎ"}


def read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def png_size(path: Path) -> list[int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not PNG: {path}")
    return list(struct.unpack(">II", data[16:24]))


def copy_required(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def relative_asset(slug: str, *parts: str) -> str:
    return "/".join(("assets", "products", slug, *parts))


def sanitize_local_paths(value, source: Path):
    """Keep QA evidence public while removing machine-specific absolute paths."""
    if isinstance(value, dict):
        return {key: sanitize_local_paths(item, source) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_local_paths(item, source) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        try:
            return str(Path(value).relative_to(source))
        except ValueError:
            return "[local-path-removed]"
    return value


def build(source: Path, output: Path, slug: str, complete_url: str) -> Path:
    manifest = read_json(source / "docs/manifest.json")
    machine = read_json(source / "qa/all_machine.json")
    browser = read_json(source / "qa/all_browser.json")
    video = read_json(source / "qa/video.json")
    package = read_json(source / "qa/package.json")
    characters = read_json(source / "assets/masters/characters.json")

    sticker_count = len(manifest.get("stickers", []))
    if sticker_count == 0 or manifest.get("count") != sticker_count:
        raise ValueError("manifest count must match a non-empty stickers array")
    names = {entry["id"]: entry["name"] for entry in characters["characters"]}

    product_root = output / "assets/products" / slug
    for name in ("main.png", "tab.png"):
        copy_required(source / "release/line" / name, product_root / name)
    for sticker in manifest["stickers"]:
        item_id = sticker["id"]
        copy_required(source / "release/line" / f"{item_id}.png", product_root / "stickers" / f"{item_id}.png")
        copy_required(source / "build/frames" / item_id / "00.png", product_root / "stills" / f"{item_id}-start.png")
        copy_required(source / "build/frames" / item_id / "15.png", product_root / "stills" / f"{item_id}-end.png")

    review_files = ["contact_sheet.png", "start_end.png", "character_sheet.png", "preview.mp4"]
    for name in review_files:
        copy_required(source / "review" / name, product_root / "review" / name)
    qa_files = ["all_machine.json", "all_browser.json", "video.json", "package.json"]
    for name in qa_files:
        destination = product_root / "qa" / name
        copy_required(source / "qa" / name, destination)
        sanitized = sanitize_local_paths(read_json(destination), source)
        destination.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    line_archive = package["archives"]["line_upload"]
    line_zip_source = source / line_archive["path"]
    copy_required(line_zip_source, product_root / "downloads" / line_zip_source.name)

    # Shared local font: copy once. Its full OFL/debian copyright file stays beside it.
    copy_required(source / "assets/fonts/ReviewSans.otf", output / "assets/fonts/ReviewSans.otf")
    copy_required(source / "assets/fonts/LICENSE.txt", output / "assets/fonts/LICENSE.txt")

    def character_label(character_id: str) -> str:
        if character_id == "trio":
            return "こむぎ・すみれ・みるく / 3匹"
        return f"{names[character_id]} / {CHARACTER_SPECIES[character_id]}"

    items = []
    for sticker in manifest["stickers"]:
        item_id = sticker["id"]
        items.append(
            {
                "id": item_id,
                "text": sticker["text"],
                "character": sticker["character"],
                "character_label": character_label(sticker["character"]),
                "intended_use": sticker["use"],
                "start": sticker["start"],
                "end": sticker["end"],
                "motion": sticker["motion"],
                "frames": sticker["frames"],
                "frame_ms": sticker["frame_ms"],
                "loops": sticker["loops"],
                "dimensions": png_size(source / "release/line" / f"{item_id}.png"),
                "animation": relative_asset(slug, "stickers", f"{item_id}.png"),
                "start_image": relative_asset(slug, "stills", f"{item_id}-start.png"),
                "end_image": relative_asset(slug, "stills", f"{item_id}-end.png"),
            }
        )

    product = {
        "schema_version": 1,
        "slug": slug,
        "title": manifest["title"],
        "description": manifest["description"],
        "status_note": "LINE Creators Marketへの申請・審査・販売・価格決定は未実施です。",
        "item_count": len(items),
        "featured_item_ids": [items[index]["id"] for index in dict.fromkeys((0, min(2, len(items) - 1), len(items) - 1))],
        "assets": {
            "main": relative_asset(slug, "main.png"),
            "tab": relative_asset(slug, "tab.png"),
            "preview_video": relative_asset(slug, "review", "preview.mp4"),
            "contact_sheet": relative_asset(slug, "review", "contact_sheet.png"),
            "start_end_sheet": relative_asset(slug, "review", "start_end.png"),
            "character_sheet": relative_asset(slug, "review", "character_sheet.png"),
        },
        "downloads": {
            "line_upload": {
                "label": "LINEアップロード用ZIPを保存",
                "url": relative_asset(slug, "downloads", line_zip_source.name),
                "bytes": line_archive["bytes"],
                "sha256": line_archive["sha256"],
                "file_count": line_archive["file_count"],
            },
            "complete_delivery": {
                "label": "完全版デリバリーZIPを保存",
                "url": complete_url,
                "bytes": package["archives"]["complete_delivery"]["bytes"],
                "sha256": package["archives"]["complete_delivery"]["sha256"],
                "file_count": package["archives"]["complete_delivery"]["file_count"],
                "availability_note": "提出用ZIPは緑、制作データ一式は完全版を選んでください。",
            },
        },
        "qa": [
            {
                "label": "機械QA",
                "status": "PASS" if machine.get("all_pass") else "FAIL",
                "detail": f"LINE画像 {len(machine.get('files', []))}点を検査",
                "source": relative_asset(slug, "qa", "all_machine.json"),
            },
            {
                "label": "Chromium実再生QA",
                "status": "PASS" if browser.get("all_pass") else "FAIL",
                "detail": f"APNG再生 {len(browser.get('files', []))}点を確認",
                "source": relative_asset(slug, "qa", "all_browser.json"),
            },
            {
                "label": "動画QA",
                "status": "PASS" if video.get("pass") else "FAIL",
                "detail": f"{video['codec'].upper()}・{video['size'][0]}×{video['size'][1]}・{int(video['duration'])}秒",
                "source": relative_asset(slug, "qa", "video.json"),
            },
            {
                "label": "梱包QA",
                "status": "PASS" if package.get("pass") else "FAIL",
                "detail": f"LINE用ZIP {line_archive['file_count']}ファイルを検査",
                "source": relative_asset(slug, "qa", "package.json"),
            },
        ],
        "items": items,
    }

    products_dir = output / "data/products"
    products_dir.mkdir(parents=True, exist_ok=True)
    data_path = products_dir / f"{slug}.json"
    data_path.write_text(json.dumps(product, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    index_path = products_dir / "index.json"
    index = read_json(index_path) if index_path.is_file() else {"schema_version": 1, "products": []}
    new_entry = {
        "slug": slug,
        "title": manifest["title"],
        "description": manifest["description"],
        "thumbnail": relative_asset(slug, "main.png"),
        "data": f"data/products/{slug}.json",
    }
    index["products"] = [entry for entry in index.get("products", []) if entry.get("slug") != slug]
    index["products"].append(new_entry)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="finished sticker package root")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--slug", required=True, help="stable URL-safe product key")
    parser.add_argument("--complete-url", required=True, help="external complete-delivery release URL")
    args = parser.parse_args()
    data_path = build(args.source.resolve(), args.output.resolve(), args.slug, args.complete_url)
    print(f"Built product data: {data_path}")


if __name__ == "__main__":
    main()
