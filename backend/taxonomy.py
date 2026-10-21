"""Versioned DEFECT_TAXONOMY catalog owned by A1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "shared" / "schemas" / "6c"
DEFAULT_ARTIFACT_ROOT = ROOT / "shared" / "artifacts" / "defect-taxonomy"


class TaxonomyError(ValueError):
    """Raised when a taxonomy artifact is invalid or unavailable."""


@dataclass(frozen=True)
class LoadedTaxonomy:
    version: str
    descriptor: dict[str, Any]
    classes: dict[str, dict[str, str]]

    def resolve(self, defect_class: str) -> dict[str, str]:
        try:
            return dict(self.classes[defect_class])
        except KeyError as exc:
            raise TaxonomyError(
                f"classe {defect_class!r} não existe em {self.version}"
            ) from exc


def _read_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _validate(schema_name: str, value: Any) -> None:
    validator = Draft202012Validator(
        _read_schema(schema_name), format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        raise TaxonomyError(f"{location}: {error.message}")


class TaxonomyCatalog:
    """Load immutable taxonomy versions and resolve historical labels."""

    def __init__(self, artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT) -> None:
        self.artifact_root = Path(artifact_root)
        self._cache: dict[str, LoadedTaxonomy] = {}

    def load(self, version: str) -> LoadedTaxonomy:
        if version in self._cache:
            return self._cache[version]

        version_dir = self.artifact_root / version
        content_path = version_dir / "content.json"
        descriptor_path = version_dir / "descriptor.json"
        if not content_path.is_file() or not descriptor_path.is_file():
            raise TaxonomyError(f"versão de taxonomia não encontrada: {version}")

        content_bytes = content_path.read_bytes()
        try:
            content = json.loads(content_bytes.decode("utf-8"))
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TaxonomyError(f"artefato {version} contém JSON inválido") from exc

        _validate("defect-taxonomy.schema.json", content)
        _validate("artifact-descriptor.schema.json", descriptor)

        if descriptor["artifact_version"] != version:
            raise TaxonomyError("descriptor e diretório usam versões diferentes")
        if descriptor["kind"] != "DEFECT_TAXONOMY" or descriptor["owner"] != "A1":
            raise TaxonomyError("descritor não pertence ao DEFECT_TAXONOMY de A1")

        digest = hashlib.sha256(content_bytes).hexdigest()
        if digest != descriptor["hash_sha256"]:
            raise TaxonomyError("hash SHA-256 do conteúdo não corresponde ao descritor")

        classes: dict[str, dict[str, str]] = {}
        for item in content["classes"]:
            class_id = item["defect_class"]
            if class_id in classes:
                raise TaxonomyError(f"defect_class duplicada: {class_id}")
            classes[class_id] = dict(item)

        loaded = LoadedTaxonomy(version, descriptor, classes)
        self._cache[version] = loaded
        return loaded

    def resolve(self, version: str, defect_class: str) -> dict[str, str]:
        """Resolve the label using the exact version stored with an inspection."""

        return self.load(version).resolve(defect_class)

