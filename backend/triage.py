"""Versioned A1 triage policy, with explicit confidence gates and explanations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .taxonomy import TaxonomyCatalog


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_DIR = ROOT / "shared" / "policies" / "triage"


class TriageError(ValueError):
    """Raised when no accepted policy covers the event."""


@dataclass(frozen=True)
class TriagePolicy:
    version: str
    taxonomy_version: str
    default_status: str
    consequences: dict[str, str]
    minimum_confidence: dict[str, float | None]


@dataclass(frozen=True)
class TriageDecision:
    status: str
    reason: str
    policy_version: str


class PolicyCatalog:
    def __init__(self, policy_dir: Path | str = DEFAULT_POLICY_DIR) -> None:
        self._by_taxonomy: dict[str, TriagePolicy] = {}
        for path in sorted(Path(policy_dir).glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            thresholds = raw.get("minimum_confidence", {})
            if set(thresholds) != {"CONFORMING", "NON_CONFORMING"}:
                raise TriageError("política deve declarar os dois limiares, ou null enquanto não calibrados")
            for value in thresholds.values():
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1):
                    raise TriageError("limiar de confiança deve ser null ou número finito entre 0 e 1")
            if raw["default_status"] not in {"REVIEW", "REJECTED"} or any(item["status"] not in {"REVIEW", "REJECTED"} for item in raw["consequences"]):
                raise TriageError("consequência de defeito deve ser REJECTED ou REVIEW")
            policy = TriagePolicy(
                version=raw["policy_version"],
                taxonomy_version=raw["taxonomy_version"],
                default_status=raw["default_status"],
                consequences={
                    item["defect_class"]: item["status"] for item in raw["consequences"]
                },
                minimum_confidence=dict(thresholds),
            )
            if policy.taxonomy_version in self._by_taxonomy:
                raise TriageError(
                    f"mais de uma política para a taxonomia {policy.taxonomy_version}"
                )
            self._by_taxonomy[policy.taxonomy_version] = policy

    def for_taxonomy(self, taxonomy_version: str) -> TriagePolicy:
        try:
            return self._by_taxonomy[taxonomy_version]
        except KeyError as exc:
            raise TriageError(
                f"nenhuma política de triagem aceita para {taxonomy_version}"
            ) from exc


class TriageService:
    def __init__(self, policies: PolicyCatalog, taxonomy: TaxonomyCatalog) -> None:
        self.policies = policies
        self.taxonomy = taxonomy

    def decide(self, payload: Mapping[str, Any]) -> TriageDecision:
        """Decide from a validated 6c payload. Unknown versions or classes raise."""

        taxonomy_version = payload["taxonomy_version"]
        self.taxonomy.load(taxonomy_version)
        policy = self.policies.for_taxonomy(taxonomy_version)
        result = payload["result"]
        if result not in {"CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN"}:
            raise TriageError("resultado I8 desconhecido")
        confidence = payload["confidence"]
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise TriageError("confiança I8 inválida")
        if result == "NON_CONFORMING":
            self.taxonomy.resolve(taxonomy_version, payload["defect_class"])
        if result in policy.minimum_confidence:
            threshold = policy.minimum_confidence[result]
            if threshold is None:
                return TriageDecision("REVIEW", f"{result}: limiar de confiança não calibrado em {policy.version}; revisão humana obrigatória.", policy.version)
            if confidence < threshold:
                return TriageDecision("REVIEW", f"{result}: confiança {confidence:g} abaixo do limiar {threshold:g} de {policy.version}.", policy.version)

        if result == "CONFORMING":
            return TriageDecision(
                "APPROVED",
                f"CONFORMING: confiança {confidence:g} atende ao limiar {policy.minimum_confidence[result]:g} de {policy.version}.",
                policy.version,
            )
        if result == "NON_CONFORMING":
            defect_class = payload["defect_class"]
            self.taxonomy.resolve(taxonomy_version, defect_class)
            if defect_class in policy.consequences:
                status = policy.consequences[defect_class]
                reason = (
                    f"Classe {defect_class} tem consequência {status} "
                    f"na política {policy.version}."
                )
            else:
                status = policy.default_status
                reason = (
                    f"Classe {defect_class} sem consequência própria na política "
                    f"{policy.version}; aplicado o padrão {status}."
                )
            return TriageDecision(status, reason, policy.version)
        if result == "ANOMALY":
            return TriageDecision(
                "REVIEW",
                "ANOMALY sem classe conhecida: revisão obrigatória pela política "
                "baseline; nenhuma classe foi atribuída.",
                policy.version,
            )
        return TriageDecision(
            "REVIEW",
            "UNCERTAIN: sem aprovação automática; encaminhada para revisão humana.",
            policy.version,
        )
