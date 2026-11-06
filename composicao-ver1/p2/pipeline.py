"""Ensaio sintético: preparar artefatos reais e chamar o replay canônico I8."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

DIRECTORY = Path('/evidencias')
TAXONOMY = Path('/taxonomies/defects-a1-1.0.0')
ENGINE = 'i8-resnet18-imagenet-1.0.0'
MODELS = {
    'normal-model': Path('/repo/models/normal_caixa_papelao_normal-csv-001.json'),
    'classifier': Path('/repo/models/classifier-caixa_papelao-classifier-csv-001.json'),
    'policy': Path('/repo/models/policy-caixa_papelao-policy-csv-001.json'),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def arguments(engine=ENGINE):
    args = ['--input', str(DIRECTORY/'frames.jsonl'), '--output', str(DIRECTORY/'eventos.jsonl')]
    for flag, path in MODELS.items():
        args += ['--'+flag, str(path)]
    return args + ['--taxonomy', str(TAXONOMY/'content.json'),
        '--taxonomy-descriptor', str(TAXONOMY/'descriptor.json'),
        '--taxonomy-version', 'defects-a1-1.0.0', '--artifact-version', engine+'-fp32',
        '--p2-engine', engine, '--kafka']


def prepare():
    import numpy as np
    import torch
    from PIL import Image
    from feature_extractor import FeatureExtractor
    from scripts.export_p2_extractor import export_package
    from scripts.replay import load_pipeline
    from p2.cli.build import main as build
    from src.taxonomy import load_taxonomy

    if (DIRECTORY/'preparacao.json').exists() or (DIRECTORY/'eventos.jsonl').exists():
        raise RuntimeError('Diretório de prova já utilizado; preserve ou arquive as evidências antes de repetir')
    official = FeatureExtractor('cpu')
    metadata = export_package(DIRECTORY/'package', extractor=official)
    assert build([str(DIRECTORY/'package'), '--cpu-only', '--engine-dir', str(DIRECTORY/'engines')]) == 0
    taxonomy = load_taxonomy(TAXONOMY/'content.json', TAXONOMY/'descriptor.json',
                             expected_version='defects-a1-1.0.0')
    # Mesmo pipeline, artefatos e pré-processamento; somente o executor difere.
    config = argparse.Namespace(normal_model=MODELS['normal-model'],classifier=MODELS['classifier'],
        policy=MODELS['policy'],p2_engine=None,artifact_version=ENGINE+'-fp32')
    baseline = load_pipeline(config, taxonomy)
    session = str(uuid4())
    rows, predictions = [], []
    for index, seed in enumerate([1, 2, 3]):
        rng = np.random.default_rng(seed)
        image = Image.fromarray(rng.integers(0,256,size=(254,310,3),dtype=np.uint8))
        path = DIRECTORY/f'synthetic-{seed}.png'
        image.save(path)
        crop = image.crop((0,0,224,224))
        result = baseline.infer(crop)
        row = dict(source_id='p2-synthetic-proof',session_id=session,frame_index=index+1,
            detection_id=0,captured_at=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),
            bbox=[0,0,224,224],frame_path=path.name)
        rows.append(row)
        predictions.append(dict(frame_index=index+1, image=path.name, image_sha256=digest(path),
                                seed=seed, expected=asdict(result)))
    (DIRECTORY/'frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    files = {str(path.relative_to('/repo')):digest(path) for path in MODELS.values()}
    files.update({'taxonomy/'+path.name:digest(path) for path in [TAXONOMY/'content.json',TAXONOMY/'descriptor.json']})
    for name in ['manifest.json','metadata.json','resnet18.onnx']:
        files['engines/'+ENGINE+'/'+name] = digest(DIRECTORY/'engines'/ENGINE/name)
    write_json(DIRECTORY/'preparacao.json',dict(
        scope='Inferência real P2 FP32/CPU com imagens sintéticas e modelos históricos; não comprova acurácia industrial',
        synthetic_images=True,real_inference=True,real_industrial_images=False,shared_broker=False,
        engine_version=ENGINE+'-fp32',backend='ort',precision='FP32',
        frames_sha256=digest(DIRECTORY/'frames.jsonl'),samples=predictions,artifact_hashes=files,
        exported_model_sha256=metadata['hash_sha256'],torch=torch.__version__,numpy=np.__version__,
        limits=['Não demonstra quatro resultados reais do dataset','Não executa captura P4/I1/P6 ou Jetson/TensorRT',
                'S4/S5/P7 reais desativados; broker compartilhado não acessado',
                'Modelos históricos não são novo treino, calibração ou aceite industrial']
    ))
    print(json.dumps({'prepared_images':len(rows),'engine':ENGINE,'synthetic_images':True}))


def infer(*, missing=False):
    # O CLI I8 executa correlação, inferência P2, journal e Kafka de fato.
    subprocess.run([sys.executable,'-m','scripts.replay',*arguments('missing-engine' if missing else ENGINE)],check=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['preparar','inferir','engine-ausente'])
    phase=parser.parse_args().phase
    if phase=='preparar':prepare()
    else:infer(missing=phase=='engine-ausente')
