# Reutiliza a imagem construída pelo Dockerfile.p2 do I8 fixado.
FROM ver1-composicao-p2-base:local
# O ensaio executa sem root; os pesos oficiais já baixados ficam legíveis.
ENV TORCH_HOME=/opt/torch
RUN mkdir -p /opt/torch && cp -a /root/.cache/torch/. /opt/torch/ && chmod -R a+rX /opt/torch
COPY composicao-ver1/p2/pipeline.py /lab/pipeline.py
ENTRYPOINT ["python", "/lab/pipeline.py"]
