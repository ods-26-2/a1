"""Pinned shared taxonomy verification without ML, network or file mutation."""
import json
from pathlib import Path

import pytest

from scripts import verify_final_taxonomy as verifier


def package():
    manifest = verifier.strict_json(verifier.DEFAULT_MANIFEST.read_bytes())
    a1 = {role: (verifier.ROOT / entry["path"]).read_bytes() for role, entry in manifest["a1"]["files"].items()}
    # Synthetic model metadata for negative unit tests; never evidence of training.
    i8 = {role: b"synthetic-source-unit-test" for role in manifest["i8"]["files"]}
    i8["classifier"] = json.dumps({"artifact_version": "classifier-test", "product_id": "test",
        "taxonomy_version": manifest["expected_descriptor"]["artifact_version"],
        "classes": [item["defect_class"] for item in verifier.strict_json(a1["content"])["classes"]]}).encode()
    i8["policy"] = json.dumps({"classifier_version": "classifier-test", "product_id": "test",
        "taxonomy_version": manifest["expected_descriptor"]["artifact_version"]}).encode()
    for role, raw in i8.items(): manifest["i8"]["files"][role]["sha256"] = verifier.digest(raw)
    return manifest, a1, i8


def test_shared_package_requires_full_descriptor_and_publication():
    manifest, a1, i8 = package()
    result = verifier.verify_bytes(manifest, a1, i8)
    assert result["version"] == "defects-a1-1.0.0"
    assert result["descriptor"] == manifest["expected_descriptor"]
    assert result["content_sha256"] == "324476cf7bbef29de8583807c1eb7b4a3709ef269c2db317a670501da4f7440a"
    assert result["classes"] == ["AMASSADO", "FURADO", "FURADO_AMASSADO"]


@pytest.mark.parametrize("repo,role", [("a1", "content"), ("a1", "descriptor"), ("a1", "published"), ("i8", "loader"), ("i8", "contracts"), ("i8", "classifier"), ("i8", "policy")])
def test_any_pinned_bytes_change_is_rejected_without_normalization(repo, role):
    manifest, a1, i8 = package()
    (a1 if repo == "a1" else i8)[role] += b"\n"
    with pytest.raises(verifier.VerificationError, match="hash divergente"):
        verifier.verify_bytes(manifest, a1, i8)


@pytest.mark.parametrize("field,value", [("artifact_version", "different"), ("uri", "registry://other"), ("hash_sha256", "0"*64)])
def test_descriptor_identity_mismatch_is_rejected(field, value):
    manifest, a1, i8 = package()
    manifest["expected_descriptor"][field] = value
    with pytest.raises(verifier.VerificationError): verifier.verify_bytes(manifest, a1, i8)


@pytest.mark.parametrize("role,field,value", [
    ("classifier", "taxonomy_version", "other"), ("policy", "taxonomy_version", "other"),
    ("classifier", "classes", ["UNKNOWN"]), ("classifier", "classes", ["AMASSADO", "AMASSADO"]),
    ("policy", "classifier_version", "other"), ("policy", "product_id", "other"),
])
def test_model_metadata_cannot_claim_compatible_taxonomy_when_divergent(role, field, value):
    manifest, a1, i8 = package()
    data = verifier.strict_json(i8[role]); data[field] = value
    i8[role] = json.dumps(data).encode()
    manifest["i8"]["files"][role]["sha256"] = verifier.digest(i8[role])
    with pytest.raises(verifier.VerificationError): verifier.verify_bytes(manifest, a1, i8)


def test_published_payload_must_equal_entire_descriptor_even_with_updated_file_hash():
    manifest, a1, i8 = package()
    data = verifier.strict_json(a1["published"]); data["payload"]["uri"] = "registry://other"
    a1["published"] = json.dumps(data).encode()
    manifest["a1"]["files"]["published"]["sha256"] = verifier.digest(a1["published"])
    with pytest.raises(verifier.VerificationError): verifier.verify_bytes(manifest, a1, i8)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_ambiguous_or_nonfinite_json_never_passes(raw):
    with pytest.raises(verifier.VerificationError): verifier.strict_json(raw)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/absolute", "a\\b"])
def test_manifest_paths_cannot_escape_repository(path):
    with pytest.raises(verifier.VerificationError): verifier.safe_path(path)


def test_new_origin_main_requires_manifest_review(monkeypatch):
    manifest, _, _ = package()
    monkeypatch.setattr(verifier, "git", lambda *args: b"0"*40 if args[-1] == "origin/main" else b"unused")
    # Reach I8 without relying on A1 content using the same pinned local bytes.
    original = verifier.git
    def read(repo, *args):
        if args[0] == "show": return (verifier.ROOT / args[1].split(":", 1)[1]).read_bytes()
        return original(repo, *args)
    monkeypatch.setattr(verifier, "git", read)
    with pytest.raises(verifier.VerificationError, match="origin/main mudou"):
        verifier.verify(manifest, Path("unused"))


def test_missing_repository_fails_cli_without_success_output(capsys):
    assert verifier.main(["--i8-repo", str(verifier.ROOT / "missing-i8-taxonomy-test")]) == 1
    output = capsys.readouterr()
    assert "FALHOU_TAXONOMIA" in output.err
    assert "VERIFICADA" not in output.out


def test_real_pinned_i8_loader_accepts_exact_a1_package_without_torch():
    repo = verifier.ROOT.parent / "i8"
    if not (repo / ".git").exists(): pytest.skip("prova integrada requer repositório I8 local no commit do manifesto")
    manifest = verifier.strict_json(verifier.DEFAULT_MANIFEST.read_bytes())
    result = verifier.verify(manifest, repo)
    assert result["status"] == "VERIFICADA_REFERENCIA_COMPARTILHADA"
    assert result["i8_loader_executed"] and not result["torch_imported"]
    assert not result["deployment_verified"] and not result["historical_training_hash_proven"]
