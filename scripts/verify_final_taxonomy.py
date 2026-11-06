"""Activity 26: verify pinned Git provenance and the shared A1/I8 package.

Read-only/offline; never uses the I8 checkout or imports ML runtimes. A mismatch
is an error, not a fallback to another taxonomy, branch or normalized hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.taxonomy import TaxonomyCatalog, _validate

DEFAULT_MANIFEST = ROOT / "shared/manifests/atividade-26-taxonomia.json"


class VerificationError(ValueError):
    pass


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise VerificationError(f"chave JSON duplicada: {key}")
            result[key] = value
        return result
    def invalid(value): raise VerificationError(f"número JSON inválido: {value}")
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or not value or ":" in value:
        raise VerificationError("caminho Git deve ser relativo e sem travessia")
    return path.as_posix()


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=20)
    if result.returncode:
        raise VerificationError(f"objeto/ref Git indisponível: {' '.join(args)}")
    return result.stdout


def verify_bytes(manifest, a1_files, i8_files):
    """Pure validation so negative tests need no Git checkout or temporary files."""
    if manifest.get("manifest_version") != "1.0" or manifest.get("activity") != 26:
        raise VerificationError("manifesto de verificação incompatível")
    for repo, files in (("a1", a1_files), ("i8", i8_files)):
        baseline = manifest[repo]
        if not re.fullmatch(r"[0-9a-f]{40}", baseline["commit"]):
            raise VerificationError("commit deve ser SHA completo fixo")
        for role, record in baseline["files"].items():
            safe_path(record["path"])
            if role not in files or digest(files[role]) != record["sha256"]:
                raise VerificationError(f"hash divergente em {repo}/{role}")
    descriptor = strict_json(a1_files["descriptor"])
    content = strict_json(a1_files["content"])
    published = strict_json(a1_files["published"])
    _validate("artifact-descriptor.schema.json", descriptor)
    _validate("defect-taxonomy.schema.json", content)
    _validate("artifact-published.schema.json", published)
    if descriptor != manifest["expected_descriptor"] or published["payload"] != descriptor:
        raise VerificationError("descritor/publicação não correspondem ao pacote esperado")
    if descriptor["owner"] != "A1" or descriptor["kind"] != "DEFECT_TAXONOMY" or digest(a1_files["content"]) != descriptor["hash_sha256"]:
        raise VerificationError("proprietário/tipo/hash da taxonomia divergente")
    classes = [item["defect_class"] for item in content["classes"]]
    if not classes or len(set(classes)) != len(classes):
        raise VerificationError("classes vazias ou duplicadas")
    classifier, policy = (strict_json(i8_files[key]) for key in ("classifier", "policy"))
    version = descriptor["artifact_version"]
    if any(item.get("taxonomy_version") != version for item in (classifier, policy)):
        raise VerificationError("artefatos históricos I8 usam outra versão de taxonomia")
    model_classes = classifier.get("classes")
    if not isinstance(model_classes, list) or not model_classes or any(not isinstance(item, str) for item in model_classes) or len(set(model_classes)) != len(model_classes) or not set(model_classes) <= set(classes):
        raise VerificationError("classificador contém classes ausentes/duplicadas")
    if policy.get("classifier_version") != classifier.get("artifact_version") or policy.get("product_id") != classifier.get("product_id"):
        raise VerificationError("política e classificador históricos incompatíveis")
    return {"version": version, "descriptor": descriptor, "content_sha256": digest(a1_files["content"]),
            "descriptor_file_sha256": digest(a1_files["descriptor"]), "classes": sorted(classes),
            "classifier_classes": sorted(model_classes)}


I8_RUNNER = r'''
import hashlib,json,sys,types
from pathlib import Path
request=json.load(sys.stdin)
package=types.ModuleType("src"); package.__path__=[]; sys.modules["src"]=package
for name in ("src.contracts","src.taxonomy"):
    module=types.ModuleType(name); module.__package__="src"; sys.modules[name]=module
    exec(compile(request["sources"][name], "i8@"+request["commit"]+":"+name, "exec"),module.__dict__)
loaded=sys.modules["src.taxonomy"].load_taxonomy(request["content"],request["descriptor"],expected_version=request["version"])
print(json.dumps({"version":loaded.version,"descriptor":dict(loaded.descriptor),"classes":sorted(loaded.classes),
    "content_sha256":hashlib.sha256(Path(request["content"]).read_bytes()).hexdigest(),
    "torch_imported":any(name=="torch" or name.startswith("torch.") for name in sys.modules)}))
'''


def run_i8_loader(i8_files, manifest, content_path, descriptor_path):
    request = {"sources": {"src.contracts": i8_files["contracts"].decode("utf-8"),
                           "src.taxonomy": i8_files["loader"].decode("utf-8")},
               "commit": manifest["i8"]["commit"], "content": str(content_path.resolve()),
               "descriptor": str(descriptor_path.resolve()), "version": manifest["expected_descriptor"]["artifact_version"]}
    # Only the two hash-checked modules from the pinned, user-owned I8 commit.
    result = subprocess.run([sys.executable, "-I", "-c", I8_RUNNER],
                            input=json.dumps(request).encode("utf-8"), capture_output=True, timeout=20)
    if result.returncode:
        raise VerificationError("loader I8 recusou o pacote ou não pôde executar isoladamente")
    return strict_json(result.stdout)


def verify(manifest, i8_repo, *, a1_root=ROOT):
    a1_files, i8_files = {}, {}
    for repo, location, output in (("a1", a1_root, a1_files), ("i8", i8_repo, i8_files)):
        baseline = manifest[repo]
        if not re.fullmatch(r"[0-9a-f]{40}", baseline["commit"]): raise VerificationError("commit não fixado")
        if repo == "i8" and git(location, "rev-parse", "origin/main").decode().strip() != baseline["commit"]:
            raise VerificationError("I8 origin/main mudou; revisar manifesto antes da nova validação")
        for role, record in baseline["files"].items():
            path = safe_path(record["path"])
            output[role] = git(location, "show", baseline["commit"] + ":" + path)
            if repo == "a1" and (a1_root / path).read_bytes() != output[role]:
                raise VerificationError(f"pacote A1 de trabalho diverge do commit fixado: {role}")
    expected = verify_bytes(manifest, a1_files, i8_files)
    content_path = a1_root / manifest["a1"]["files"]["content"]["path"]
    descriptor_path = a1_root / manifest["a1"]["files"]["descriptor"]["path"]
    loaded = TaxonomyCatalog(content_path.parent.parent).load(expected["version"])
    if loaded.descriptor != expected["descriptor"] or sorted(loaded.classes) != expected["classes"]:
        raise VerificationError("catálogo A1 não corresponde ao manifesto")
    observed = run_i8_loader(i8_files, manifest, content_path, descriptor_path)
    for key in ("version", "descriptor", "classes", "content_sha256"):
        if observed.get(key) != expected[key]: raise VerificationError(f"loader I8 diverge em {key}")
    if observed.get("torch_imported") is not False: raise VerificationError("isolamento ML não comprovado")
    for role, record in manifest["a1"]["files"].items():
        if (a1_root / record["path"]).read_bytes() != a1_files[role]: raise VerificationError("pacote mudou durante verificação")
    return {"status": "VERIFICADA_REFERENCIA_COMPARTILHADA", "activity": 26,
            "a1_commit": manifest["a1"]["commit"], "i8_commit": manifest["i8"]["commit"],
            **expected, "i8_loader_executed": True, "torch_imported": False,
            "i8_taxonomy_copy_claimed": False, "deployment_verified": False,
            "historical_training_hash_proven": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--i8-repo", type=Path, default=ROOT.parent / "i8")
    args = parser.parse_args(argv)
    try:
        result = verify(strict_json(args.manifest.read_bytes()), args.i8_repo)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"FALHOU_TAXONOMIA: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
