from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from backend.taxonomy import TaxonomyCatalog, TaxonomyError


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "shared" / "artifacts" / "defect-taxonomy"
POLICY = ROOT / "shared" / "policies" / "triage" / "defects-a1-1.0.0.json"


def test_catalog_resolves_labels_by_exact_version():
    catalog = TaxonomyCatalog()
    item = catalog.resolve("defects-a1-1.0.0", "AMASSADO")

    assert item["name"] == "Amassado"
    assert catalog.load("defects-a1-1.0.0").version == "defects-a1-1.0.0"


def test_unknown_version_and_class_are_explicit():
    catalog = TaxonomyCatalog()
    with pytest.raises(TaxonomyError, match="não encontrada"):
        catalog.load("defects-a1-9.9.9")
    with pytest.raises(TaxonomyError, match="não existe"):
        catalog.resolve("defects-a1-1.0.0", "DESCONHECIDO")


def test_changed_content_is_rejected_by_hash(tmp_path: Path):
    target_root = tmp_path / "taxonomy"
    shutil.copytree(ARTIFACT_ROOT, target_root)
    content = target_root / "defects-a1-1.0.0" / "content.json"
    content.write_text(content.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(TaxonomyError, match="hash SHA-256"):
        TaxonomyCatalog(target_root).load("defects-a1-1.0.0")


def test_duplicate_ids_are_rejected_semantically(tmp_path: Path):
    target_root = tmp_path / "taxonomy"
    shutil.copytree(ARTIFACT_ROOT, target_root)
    version_dir = target_root / "defects-a1-1.0.0"
    content_path = version_dir / "content.json"
    descriptor_path = version_dir / "descriptor.json"
    content = json.loads(content_path.read_text(encoding="utf-8"))
    content["classes"].append(dict(content["classes"][0]))
    content_path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["hash_sha256"] = hashlib.sha256(content_path.read_bytes()).hexdigest()
    descriptor_path.write_text(
        json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(TaxonomyError, match="duplicada"):
        TaxonomyCatalog(target_root).load("defects-a1-1.0.0")


def test_business_consequence_is_not_inside_taxonomy():
    taxonomy = json.loads(
        (ARTIFACT_ROOT / "defects-a1-1.0.0" / "content.json").read_text(
            encoding="utf-8"
        )
    )
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert all("consequence" not in item for item in taxonomy["classes"])
    assert policy["taxonomy_version"] == "defects-a1-1.0.0"
    assert {item["defect_class"] for item in policy["consequences"]} == {
        item["defect_class"] for item in taxonomy["classes"]
    }

