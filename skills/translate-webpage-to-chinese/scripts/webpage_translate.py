#!/usr/bin/env python3
"""Prepare, apply, and validate style-preserving webpage translations."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Comment, Doctype, NavigableString, ProcessingInstruction


SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "code",
    "pre",
    "kbd",
    "samp",
    "svg",
    "math",
    "textarea",
    "template",
}
TRANSLATABLE_ATTRIBUTES = ("alt", "aria-label", "placeholder", "title")
MARKER_RE = re.compile(r"__ZH_SEG_(\d{4})__")
NATURAL_LANGUAGE_RE = re.compile(r"[A-Za-z\u00C0-\u024F]")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/136 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def is_translatable(value: str) -> bool:
    core = value.strip()
    if not core or not NATURAL_LANGUAGE_RE.search(core):
        return False
    if CHINESE_RE.search(core):
        return False
    if re.fullmatch(r"[\w./:@#%+?&=~-]+", core) and (
        "/" in core or "@" in core or core.startswith(("http", "#", "--"))
    ):
        return False
    return True


def whitespace_parts(value: str) -> tuple[str, str, str]:
    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    end = len(value) - len(trailing) if trailing else len(value)
    return leading, value[len(leading) : end], trailing


def ensure_document_metadata(soup: BeautifulSoup, source_url: str) -> None:
    if soup.html is None:
        html_tag = soup.new_tag("html")
        html_tag.extend(list(soup.contents))
        soup.append(html_tag)
    soup.html["lang"] = "zh-CN"

    if soup.head is None:
        head = soup.new_tag("head")
        soup.html.insert(0, head)
    base = soup.head.find("base")
    if base is None:
        base = soup.new_tag("base", href=source_url)
        soup.head.insert(0, base)
    elif not base.get("href"):
        base["href"] = source_url

    static_policy = soup.head.find("meta", attrs={"data-translation-copy": "static"})
    if static_policy is None:
        static_policy = soup.new_tag("meta")
        static_policy["data-translation-copy"] = "static"
        static_policy["http-equiv"] = "Content-Security-Policy"
        soup.head.insert(1, static_policy)
    static_policy["content"] = "script-src 'none'"

    meta = soup.head.find("meta", attrs={"name": "translated-from"})
    if meta is None:
        meta = soup.new_tag("meta")
        meta["name"] = "translated-from"
        soup.head.append(meta)
    meta["content"] = source_url


def context_for(node: Any) -> str:
    parent = node.parent if isinstance(node, NavigableString) else node
    tags: list[str] = []
    for ancestor in list(parent.parents)[:4] if parent else []:
        if getattr(ancestor, "name", None):
            tags.append(ancestor.name)
    own = getattr(parent, "name", "text")
    return " > ".join(reversed(tags + [own]))


def prepare(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input_html:
        source_path = Path(args.input_html).resolve()
        source_html = read_text(source_path)
        source_url = args.source_url
        if not source_url:
            raise ValueError("--source-url is required with --input-html")
    else:
        source_url = args.url
        if not source_url:
            raise ValueError("--url or --input-html is required")
        try:
            source_html = fetch_html(source_url)
        except Exception as exc:
            raise RuntimeError(
                f"direct fetch failed for {source_url}: {exc}. "
                "Capture the rendered DOM with a browser and rerun with "
                "--input-html plus --source-url."
            ) from exc

    soup = BeautifulSoup(source_html, "html.parser")
    ensure_document_metadata(soup, source_url)

    segments: list[dict[str, str]] = []
    source_to_id: dict[tuple[str, str], str] = {}

    def marker_for(source: str, kind: str, context: str) -> str:
        key = (source, kind)
        segment_id = source_to_id.get(key)
        if segment_id is None:
            segment_id = f"seg-{len(segments) + 1:04d}"
            source_to_id[key] = segment_id
            segments.append(
                {
                    "id": segment_id,
                    "source": source,
                    "kind": kind,
                    "context": context,
                }
            )
        return f"__ZH_SEG_{int(segment_id.removeprefix('seg-')):04d}__"

    for node in list(soup.find_all(string=True)):
        if isinstance(node, (Comment, Doctype, ProcessingInstruction)) or node.parent is None:
            continue
        if node.parent.name in SKIP_TAGS or any(
            getattr(parent, "name", None) in SKIP_TAGS for parent in node.parents
        ):
            continue
        leading, core, trailing = whitespace_parts(str(node))
        if not is_translatable(core):
            continue
        marker = marker_for(core, "text", context_for(node))
        node.replace_with(NavigableString(f"{leading}{marker}{trailing}"))

    for tag in soup.find_all(True):
        if tag.name in SKIP_TAGS or any(
            getattr(parent, "name", None) in SKIP_TAGS for parent in tag.parents
        ):
            continue
        for attribute in TRANSLATABLE_ATTRIBUTES:
            value = tag.get(attribute)
            if not isinstance(value, str) or not is_translatable(value):
                continue
            tag[attribute] = marker_for(value, f"attribute:{attribute}", context_for(tag))

    marked_html = "<!DOCTYPE html>\n" + str(soup)
    write_text(output_dir / "source.html", source_html)
    write_text(output_dir / "page.marked.html", marked_html)
    write_text(
        output_dir / "segments.json",
        json.dumps(segments, ensure_ascii=False, indent=2) + "\n",
    )
    manifest = {
        "source_url": source_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "segment_count": len(segments),
        "source_bytes": len(source_html.encode("utf-8")),
    }
    write_text(
        output_dir / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    print(f"Prepared {len(segments)} unique translation segments in {output_dir}")


def load_translations(path: Path) -> dict[str, str]:
    value = json.loads(read_text(path))
    if isinstance(value, list):
        value = {item["id"]: item["translation"] for item in value}
    if not isinstance(value, dict):
        raise ValueError("translations must be a JSON object or a list of id/translation objects")
    translations: dict[str, str] = {}
    for key, translation in value.items():
        if not isinstance(key, str) or not isinstance(translation, str):
            raise ValueError("every translation ID and value must be a string")
        translations[key] = translation
    return translations


def apply(args: argparse.Namespace) -> None:
    work_dir = Path(args.work_dir).resolve()
    marked_html = read_text(work_dir / "page.marked.html")
    segments = json.loads(read_text(work_dir / "segments.json"))
    translations = load_translations(Path(args.translations).resolve())
    required = {segment["id"] for segment in segments}
    missing = sorted(required - translations.keys())
    extra = sorted(translations.keys() - required)
    if missing:
        raise ValueError(f"missing translations: {', '.join(missing[:12])}")
    if extra:
        raise ValueError(f"unknown translation IDs: {', '.join(extra[:12])}")

    output_html = marked_html
    for segment in segments:
        segment_id = segment["id"]
        number = int(segment_id.removeprefix("seg-"))
        marker = f"__ZH_SEG_{number:04d}__"
        translation = translations[segment_id]
        if not translation.strip():
            raise ValueError(f"empty translation: {segment_id}")
        escaped = html.escape(
            translation,
            quote=segment["kind"].startswith("attribute:"),
        )
        output_html = output_html.replace(marker, escaped)

    leftovers = MARKER_RE.findall(output_html)
    if leftovers:
        raise ValueError(f"unresolved markers remain: {len(leftovers)}")
    write_text(Path(args.output).resolve(), output_html)
    print(f"Wrote translated HTML to {Path(args.output).resolve()}")


def tag_signature(document: str) -> Counter[str]:
    soup = BeautifulSoup(document, "html.parser")
    return Counter(tag.name for tag in soup.find_all(True))


def validate(args: argparse.Namespace) -> None:
    work_dir = Path(args.work_dir).resolve()
    marked_html = read_text(work_dir / "page.marked.html")
    output_html = read_text(Path(args.output).resolve())
    segments = json.loads(read_text(work_dir / "segments.json"))
    translations = load_translations(Path(args.translations).resolve())

    errors: list[str] = []
    required = {segment["id"] for segment in segments}
    if set(translations) != required:
        errors.append("translation IDs do not exactly match segments.json")
    if MARKER_RE.search(output_html):
        errors.append("output contains unresolved translation markers")
    if tag_signature(marked_html) != tag_signature(output_html):
        errors.append("output DOM tag counts differ from the marked source")

    soup = BeautifulSoup(output_html, "html.parser")
    if soup.html is None or soup.html.get("lang") != "zh-CN":
        errors.append('output must declare html lang="zh-CN"')
    if soup.find("base", href=True) is None:
        errors.append("output is missing a base URL for relative assets")
    if soup.find("meta", attrs={"name": "translated-from"}) is None:
        errors.append("output is missing source provenance metadata")
    if not soup.find_all("link", rel=lambda value: value and "stylesheet" in value):
        errors.append("output contains no stylesheet links")

    unchanged = sum(
        translations.get(segment["id"], "") == segment["source"] for segment in segments
    )
    if unchanged:
        print(
            f"Notice: {unchanged}/{len(segments)} segments are unchanged; "
            "verify they are intentional terms or proper names."
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(
        f"Validation passed: {len(segments)} segments, "
        f"{sum(tag_signature(output_html).values())} DOM elements"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    source = prepare_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--input-html")
    prepare_parser.add_argument("--source-url")
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.set_defaults(handler=prepare)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--work-dir", required=True)
    apply_parser.add_argument("--translations", required=True)
    apply_parser.add_argument("--output", required=True)
    apply_parser.set_defaults(handler=apply)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--work-dir", required=True)
    validate_parser.add_argument("--translations", required=True)
    validate_parser.add_argument("--output", required=True)
    validate_parser.set_defaults(handler=validate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
