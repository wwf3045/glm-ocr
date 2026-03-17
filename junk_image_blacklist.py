from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from clean_junk_images import IMAGE_EXTS


def runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DEFAULT_BLACKLIST_PATH = runtime_base_dir() / "junk_image_blacklist.json"
DEFAULT_BLACKLIST_GALLERY = runtime_base_dir() / "blacklist_gallery"


@dataclass(frozen=True)
class ImageSignature:
    width: int
    height: int
    ahash: int
    dhash: int


DEFAULT_FAMILIES = [
    {
        "id": "builtin_sjtu_square_logo",
        "name": "sjtu_square_logo",
        "notes": "SJTU square watermark/logo",
        "source": "builtin",
        "created_at": "2026-03-15 10:46:00",
        "threshold": 10,
        "max_aspect_diff": 0.22,
        "max_width_ratio": 2.6,
        "max_height_ratio": 2.6,
        "samples": [
            {
                "width": 150,
                "height": 152,
                "ahash": 18150493454499693559,
                "dhash": 16764883468265777384,
            }
        ],
    },
    {
        "id": "builtin_sjtu_banner_watermark",
        "name": "sjtu_banner_watermark",
        "notes": "SJTU banner watermark",
        "source": "builtin",
        "created_at": "2026-03-15 10:46:00",
        "threshold": 10,
        "max_aspect_diff": 0.30,
        "max_width_ratio": 2.8,
        "max_height_ratio": 2.8,
        "samples": [
            {
                "width": 596,
                "height": 164,
                "ahash": 13780491630198857791,
                "dhash": 11508302015949023922,
            }
        ],
    },
]


def ensure_registry(path: Path = DEFAULT_BLACKLIST_PATH) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_gallery_dir(DEFAULT_BLACKLIST_GALLERY)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("families"), list):
                migrate_registry(payload)
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    payload = {
        "version": 1,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "families": DEFAULT_FAMILIES,
    }
    migrate_registry(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def save_registry(payload: dict[str, Any], path: Path = DEFAULT_BLACKLIST_PATH) -> None:
    payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    migrate_registry(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_gallery_dir(path: Path = DEFAULT_BLACKLIST_GALLERY) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    readme_path = path / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            "# 拉黑图集\n\n"
            "这里每个废图族只保留一张代表图，用来做人工复核和后续相似匹配。\n",
            encoding="utf-8",
        )
    return path


def safe_name(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text.strip())
    text = text.strip("._")
    return text[:80] or "family"


def stable_family_token(family_name: str, family_id: str | None = None) -> str:
    slug = safe_name(family_name)
    if family_id and family_id.strip():
        suffix = safe_name(family_id)[:40] or hashlib.sha1(family_id.encode("utf-8")).hexdigest()[:10]
    else:
        suffix = hashlib.sha1(family_name.encode("utf-8")).hexdigest()[:10]
    return f"{slug}__{suffix}"


def representative_target_path(
    family_name: str,
    sample_path: Path | None,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
    family_id: str | None = None,
    suffix: str | None = None,
) -> Path:
    ensure_gallery_dir(gallery_dir)
    resolved_suffix = suffix or ((sample_path.suffix.lower() or ".png") if sample_path is not None else ".png")
    return gallery_dir / f"{stable_family_token(family_name, family_id=family_id)}{resolved_suffix}"


def copy_representative_image(
    sample_path: Path,
    family_name: str,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
    family_id: str | None = None,
) -> Path:
    target = representative_target_path(family_name, sample_path, gallery_dir, family_id=family_id)
    shutil.copy2(sample_path, target)
    return target


def migrate_registry(payload: dict[str, Any]) -> None:
    ensure_gallery_dir(DEFAULT_BLACKLIST_GALLERY)
    families = payload.get("families", [])
    if not isinstance(families, list):
        return
    for family in families:
        if not isinstance(family, dict):
            continue
        family.setdefault("notes", "")
        family.setdefault("source", "unknown")
        family.setdefault("samples", [])
        family.setdefault("representative_image", None)
        family.setdefault("representative_source", None)
        family.setdefault("id", f"manual_{hashlib.sha1(str(family.get('name', '')).encode('utf-8')).hexdigest()[:10]}")

        representative_image = family.get("representative_image")
        representative_source = family.get("representative_source")
        source_path = None
        if representative_source:
            candidate = Path(str(representative_source))
            if candidate.exists() and candidate.is_file():
                source_path = candidate
        current_rep_path = None
        if representative_image:
            candidate = Path(str(representative_image))
            if candidate.exists() and candidate.is_file():
                current_rep_path = candidate
        sample_path = source_path or current_rep_path
        suffix = (sample_path.suffix.lower() if sample_path is not None else None) or ".png"
        desired_path = representative_target_path(
            str(family.get("name", "")),
            sample_path,
            gallery_dir=DEFAULT_BLACKLIST_GALLERY,
            family_id=str(family.get("id", "")),
            suffix=suffix,
        )
        if current_rep_path is not None and current_rep_path.resolve() != desired_path.resolve():
            if not desired_path.exists():
                current_rep_path.rename(desired_path)
            family["representative_image"] = str(desired_path)
        elif source_path is not None and not desired_path.exists():
            shutil.copy2(source_path, desired_path)
            family["representative_image"] = str(desired_path)
        elif current_rep_path is None and desired_path.exists():
            family["representative_image"] = str(desired_path)
        elif source_path is None and current_rep_path is None:
            family["representative_image"] = None


def average_hash_int(image: Image.Image, size: int = 8) -> int:
    sample = image.resize((size, size))
    pixels = list(sample.getdata())
    avg = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= avg)
    return value


def difference_hash_int(image: Image.Image, size: int = 8) -> int:
    sample = image.resize((size + 1, size))
    pixels = list(sample.getdata())
    value = 0
    width = size + 1
    for row in range(size):
        offset = row * width
        for col in range(size):
            value = (value << 1) | int(pixels[offset + col] >= pixels[offset + col + 1])
    return value


def build_signature(path: Path) -> ImageSignature:
    with Image.open(path) as image:
        return build_signature_from_image(image)


def build_signature_from_image(image: Image.Image) -> ImageSignature:
    width, height = image.size
    gray = image.convert("L")
    return ImageSignature(
        width=width,
        height=height,
        ahash=average_hash_int(gray),
        dhash=difference_hash_int(gray),
    )


def signature_key(signature: ImageSignature) -> tuple[int, int, int, int]:
    return signature.width, signature.height, signature.ahash, signature.dhash


def normalize_family_name(name: str | None) -> str:
    if name and name.strip():
        return name.strip()
    return f"manual_junk_{time.strftime('%Y%m%d_%H%M%S')}"


def add_or_update_family(
    sample_paths: list[str | Path],
    family_name: str | None = None,
    path: Path = DEFAULT_BLACKLIST_PATH,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
    notes: str = "",
    source: str = "reviewer",
) -> dict[str, Any]:
    registry = ensure_registry(path)
    resolved_paths = [Path(item).resolve() for item in sample_paths]

    signatures: list[ImageSignature] = []
    for sample_path in resolved_paths:
        try:
            signatures.append(build_signature(sample_path))
        except (OSError, UnidentifiedImageError):
            continue

    if not signatures:
        raise ValueError("没有可用于学习黑名单的样本图片。")

    family_name = normalize_family_name(family_name)
    family = next((item for item in registry["families"] if item["name"] == family_name), None)
    if family is None:
        family = {
            "id": f"manual_{time.strftime('%Y%m%d_%H%M%S')}",
            "name": family_name,
            "notes": notes,
            "source": source,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "threshold": 10,
            "max_aspect_diff": 0.30,
            "max_width_ratio": 2.8,
            "max_height_ratio": 2.8,
            "samples": [],
            "representative_image": None,
            "representative_source": None,
        }
        registry["families"].append(family)

    existing = {
        (
            sample["width"],
            sample["height"],
            sample["ahash"],
            sample["dhash"],
        )
        for sample in family.get("samples", [])
    }
    for signature in signatures:
        key = signature_key(signature)
        if key in existing:
            continue
        family["samples"].append(
            {
                "width": signature.width,
                "height": signature.height,
                "ahash": signature.ahash,
                "dhash": signature.dhash,
            }
        )
        existing.add(key)

    representative_source = resolved_paths[0]
    representative_target = copy_representative_image(
        representative_source,
        family_name,
        gallery_dir=gallery_dir,
        family_id=str(family.get("id", "")),
    )
    family["representative_image"] = str(representative_target)
    family["representative_source"] = str(representative_source)

    save_registry(registry, path)
    return family


def list_families(path: Path = DEFAULT_BLACKLIST_PATH) -> list[dict[str, Any]]:
    return ensure_registry(path).get("families", [])


def find_family(
    family_name: str,
    path: Path = DEFAULT_BLACKLIST_PATH,
) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, dict[str, Any]]:
    registry = ensure_registry(path)
    family = next((item for item in registry.get("families", []) if item.get("name") == family_name), None)
    return family, registry


def delete_family(
    family_name: str,
    path: Path = DEFAULT_BLACKLIST_PATH,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
) -> dict[str, Any]:
    family, registry = find_family(family_name, path)
    if family is None:
        raise ValueError(f"找不到废图族：{family_name}")

    representative = family.get("representative_image")
    registry["families"] = [
        item for item in registry.get("families", [])
        if item.get("name") != family_name
    ]
    if representative:
        representative_path = Path(representative)
        if representative_path.exists() and representative_path.is_file():
            representative_path.unlink()
    save_registry(registry, path)
    return {
        "deleted_family": family_name,
        "deleted_representative": representative,
        "family_count": len(registry.get("families", [])),
        "gallery_path": str(gallery_dir),
    }


def rename_family(
    family_name: str,
    new_family_name: str,
    path: Path = DEFAULT_BLACKLIST_PATH,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
) -> dict[str, Any]:
    target_name = normalize_family_name(new_family_name)
    if target_name == family_name:
        family, _ = find_family(family_name, path)
        if family is None:
            raise ValueError(f"找不到废图族：{family_name}")
        return {
            "family_name": family_name,
            "new_family_name": target_name,
            "representative_image": family.get("representative_image"),
        }

    family, registry = find_family(family_name, path)
    if family is None:
        raise ValueError(f"找不到废图族：{family_name}")
    if any(item.get("name") == target_name for item in registry.get("families", []) if item is not family):
        raise ValueError(f"已存在同名废图族：{target_name}")

    old_representative = family.get("representative_image")
    family["name"] = target_name
    if old_representative:
        old_path = Path(old_representative)
        if old_path.exists() and old_path.is_file():
            new_path = representative_target_path(
                target_name,
                old_path,
                gallery_dir=gallery_dir,
                family_id=str(family.get("id", "")),
            )
            if new_path.resolve() != old_path.resolve():
                if new_path.exists():
                    new_path.unlink()
                old_path.rename(new_path)
            family["representative_image"] = str(new_path)
    save_registry(registry, path)
    return {
        "family_name": family_name,
        "new_family_name": target_name,
        "representative_image": family.get("representative_image"),
    }


def merge_families(
    source_family_names: list[str],
    target_family_name: str,
    path: Path = DEFAULT_BLACKLIST_PATH,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
) -> dict[str, Any]:
    normalized_sources = [name for name in dict.fromkeys(source_family_names) if name]
    if len(normalized_sources) < 2:
        raise ValueError("至少需要两个废图族才能合并。")

    registry = ensure_registry(path)
    families = registry.get("families", [])
    family_map = {item.get("name"): item for item in families}
    missing = [name for name in normalized_sources if name not in family_map]
    if missing:
        raise ValueError(f"找不到废图族：{', '.join(missing)}")

    target_name = normalize_family_name(target_family_name)
    target_family = family_map.get(target_name)
    merging_families = [family_map[name] for name in normalized_sources]

    if target_family is None:
        target_family = {
            "id": f"manual_{time.strftime('%Y%m%d_%H%M%S')}",
            "name": target_name,
            "notes": "merged in blacklist gallery",
            "source": "reviewer",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "threshold": max(int(family.get("threshold", 10)) for family in merging_families),
            "max_aspect_diff": max(float(family.get("max_aspect_diff", 0.30)) for family in merging_families),
            "max_width_ratio": max(float(family.get("max_width_ratio", 2.8)) for family in merging_families),
            "max_height_ratio": max(float(family.get("max_height_ratio", 2.8)) for family in merging_families),
            "samples": [],
            "representative_image": None,
            "representative_source": None,
        }
        families.append(target_family)

    existing = {
        (
            sample["width"],
            sample["height"],
            sample["ahash"],
            sample["dhash"],
        )
        for sample in target_family.get("samples", [])
    }
    representative_source = None
    notes = []
    for family in merging_families:
        if family.get("notes"):
            notes.append(str(family["notes"]))
        for sample in family.get("samples", []):
            key = (
                sample["width"],
                sample["height"],
                sample["ahash"],
                sample["dhash"],
            )
            if key in existing:
                continue
            target_family.setdefault("samples", []).append(sample)
            existing.add(key)
        representative_source = representative_source or family.get("representative_source")
        if target_family.get("representative_image") is None and family.get("representative_image"):
            source_path = Path(family["representative_image"])
            if source_path.exists() and source_path.is_file():
                new_path = representative_target_path(
                    target_name,
                    source_path,
                    gallery_dir=gallery_dir,
                    family_id=str(target_family.get("id", "")),
                )
                if new_path.exists():
                    new_path.unlink()
                shutil.copy2(source_path, new_path)
                target_family["representative_image"] = str(new_path)
                target_family["representative_source"] = family.get("representative_source")

    if representative_source and target_family.get("representative_image") is None:
        source_path = Path(representative_source)
        if source_path.exists() and source_path.is_file():
            new_path = representative_target_path(
                target_name,
                source_path,
                gallery_dir=gallery_dir,
                family_id=str(target_family.get("id", "")),
            )
            if new_path.exists():
                new_path.unlink()
            shutil.copy2(source_path, new_path)
            target_family["representative_image"] = str(new_path)
            target_family["representative_source"] = str(source_path)

    if notes:
        target_family["notes"] = " | ".join(dict.fromkeys(notes))

    for family_name in normalized_sources:
        if family_name == target_name:
            continue
        family = family_map[family_name]
        representative = family.get("representative_image")
        if representative:
            representative_path = Path(representative)
            if representative_path.exists() and representative_path.is_file():
                representative_path.unlink()
        registry["families"] = [
            item for item in registry.get("families", [])
            if item.get("name") != family_name
        ]

    save_registry(registry, path)
    return {
        "target_family_name": target_name,
        "merged_families": normalized_sources,
        "sample_count": len(target_family.get("samples", [])),
        "representative_image": target_family.get("representative_image"),
        "family_count": len(registry.get("families", [])),
    }


def iter_images(root: Path):
    for image_path in root.rglob("*"):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTS:
            yield image_path


def matches_family(signature: ImageSignature, family: dict[str, Any]) -> bool:
    entry_aspect = signature.width / max(signature.height, 1)
    samples = family.get("samples", [])
    threshold = int(family.get("threshold", 10))
    max_aspect_diff = float(family.get("max_aspect_diff", 0.30))
    max_width_ratio = float(family.get("max_width_ratio", 2.8))
    max_height_ratio = float(family.get("max_height_ratio", 2.8))

    for sample in samples:
        sample_aspect = sample["width"] / max(sample["height"], 1)
        if abs(entry_aspect - sample_aspect) > max_aspect_diff:
            continue

        width_ratio = max(signature.width, sample["width"]) / max(1, min(signature.width, sample["width"]))
        height_ratio = max(signature.height, sample["height"]) / max(1, min(signature.height, sample["height"]))
        if width_ratio > max_width_ratio or height_ratio > max_height_ratio:
            continue

        distance = (signature.ahash ^ sample["ahash"]).bit_count() + (signature.dhash ^ sample["dhash"]).bit_count()
        if distance <= threshold:
            return True

    return False


def scan_blacklist_matches(root: Path, path: Path = DEFAULT_BLACKLIST_PATH) -> dict[str, list[str]]:
    registry = ensure_registry(path)
    matches: dict[str, list[str]] = {family["name"]: [] for family in registry.get("families", [])}
    for image_path in iter_images(root):
        try:
            signature = build_signature(image_path)
        except (OSError, UnidentifiedImageError):
            continue
        for family in registry.get("families", []):
            if matches_family(signature, family):
                matches[family["name"]].append(str(image_path.resolve()))
                break
    return matches


def blacklist_summary(
    path: Path = DEFAULT_BLACKLIST_PATH,
    gallery_dir: Path = DEFAULT_BLACKLIST_GALLERY,
) -> dict[str, Any]:
    families = list_families(path)
    return {
        "path": str(path),
        "gallery_path": str(gallery_dir),
        "family_count": len(families),
        "families": [
            {
                "name": family["name"],
                "source": family.get("source", "unknown"),
                "sample_count": len(family.get("samples", [])),
                "notes": family.get("notes", ""),
                "representative_image": family.get("representative_image"),
            }
            for family in families
        ],
    }
