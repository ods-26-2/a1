# Comandos publicados — atividade 31

## Regressão e logs

```bash
bash fechamento-sprint3/regressao.sh
```

Resultado e log resumido: `docs/evidencias/atividade-29/resultado.json` e
`docs/evidencias/atividade-29/resumo.log`. XML e logs integrais:
[execução 42218589659](https://github.com/ods-26-2/a1/actions/runs/42218589659).

## Latência, memória e ambiente

```bash
bash fechamento-sprint3/medir.sh
```

Resultado e log resumido: `docs/evidencias/atividade-30/resultado.json` e
`docs/evidencias/atividade-30/resumo.log`. Dados brutos e logs:
[execução 42219871217](https://github.com/ods-26-2/a1/actions/runs/42219871217).

## Capturas e vídeo

```bash
node scripts/capture_sprint3_closure.mjs /caminho/google-chrome /caminho/ffmpeg docs/evidencias/atividade-31
python scripts/build_closure_manifest.py
python scripts/verify_closure_evidence.py
```

O navegador usa `?api=fake` de forma explícita. Os dados da demonstração
não persistem e não substituem os logs Docker das atividades 29 e 30.
