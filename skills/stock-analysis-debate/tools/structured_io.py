"""JSON 数据模型的 TOON/JSON 文件编解码入口。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


# 修改为 "json" 即可恢复 JSON 文件输出；默认使用 TOON。
STRUCTURED_OUTPUT_FORMAT = "toon"
SUPPORTED_STRUCTURED_FORMATS = frozenset({"json", "toon"})


def _format(value: str | None = None) -> str:
    selected = (value or STRUCTURED_OUTPUT_FORMAT).strip().lower()
    if selected not in SUPPORTED_STRUCTURED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_STRUCTURED_FORMATS))
        raise ValueError(
            f"unsupported structured output format: {selected!r}; "
            f"expected one of: {supported}"
        )
    return selected


def _normalize_json_data(value: Any) -> Any:
    """转换为严格 JSON 数据模型，并拒绝 NaN/Infinity。"""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        allow_nan=False,
    )
    return json.loads(encoded)


def _toon_codec():
    try:
        from toon_format import decode, encode
        from toon_format.types import DecodeOptions
    except ImportError as exc:
        raise RuntimeError(
            "TOON output requires the pinned toon_format dependency; "
            "run: pip install -r tools/requirements.txt"
        ) from exc
    return encode, decode, DecodeOptions


def json_to_toon(json_data: Any) -> str:
    """将 JSON 文本或兼容 JSON 的 Python 值无损编码为 TOON 文本。"""
    value = json.loads(json_data) if isinstance(json_data, (str, bytes)) else json_data
    normalized = _normalize_json_data(value)
    encode, decode, decode_options = _toon_codec()
    toon_text = encode(normalized)
    decoded = decode(toon_text, decode_options(strict=True))
    if decoded != normalized:
        raise ValueError("TOON round-trip validation failed; output was not written")
    return toon_text


def toon_to_json_data(toon_text: str) -> Any:
    """严格解码 TOON，并返回标准 JSON 数据模型。"""
    _, decode, decode_options = _toon_codec()
    return _normalize_json_data(
        decode(toon_text, decode_options(strict=True))
    )


def structured_path(
    path: str | os.PathLike[str],
    output_format: str | None = None,
) -> Path:
    """把逻辑结构化文件路径转换为所选格式的真实路径。"""
    selected = _format(output_format)
    target = Path(path)
    if target.suffix.lower() in {".json", ".toon"}:
        return target.with_suffix(f".{selected}")
    return target.with_name(f"{target.name}.{selected}")


def resolve_structured_path(
    path: str | os.PathLike[str],
    input_format: str | None = None,
) -> Path:
    """优先读取配置格式；缺失时兼容同名 JSON/TOON 历史文件。"""
    preferred = structured_path(path, input_format)
    candidates = [preferred]
    for alternate_format in ("toon", "json"):
        candidate = structured_path(path, alternate_format)
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    expected = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"structured data file not found; tried: {expected}")


def read_structured_file(
    path: str | os.PathLike[str],
    input_format: str | None = None,
) -> Any:
    """读取 TOON 或 JSON 文件，默认优先当前配置格式。"""
    actual_path = resolve_structured_path(path, input_format=input_format)
    text = actual_path.read_text(encoding="utf-8")
    if actual_path.suffix.lower() == ".toon":
        return toon_to_json_data(text)
    return _normalize_json_data(json.loads(text))


def _serialize(value: Any, output_format: str) -> str:
    normalized = _normalize_json_data(value)
    if output_format == "toon":
        return json_to_toon(normalized)
    return json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"


def write_structured_file(
    path: str | os.PathLike[str],
    value: Any,
    output_format: str | None = None,
    *,
    remove_alternate: bool = True,
) -> Path:
    """原子写入 TOON/JSON；成功后删除同名的另一格式，避免读取陈旧数据。"""
    selected = _format(output_format)
    target = structured_path(path, selected)
    text = _serialize(value, selected)
    target.parent.mkdir(parents=True, exist_ok=True)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        dir=target.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    if remove_alternate:
        alternate_format = "json" if selected == "toon" else "toon"
        alternate = structured_path(path, alternate_format)
        if alternate != target:
            alternate.unlink(missing_ok=True)
    return target
