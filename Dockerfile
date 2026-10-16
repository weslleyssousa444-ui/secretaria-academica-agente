# Imagem do agente de triagem — Exercício 13. Decisões em
# docs/empacotamento.md; a imagem roda a API (src/api.py) por padrão e o
# chat de terminal com `docker run -it ... python src/chat.py`.
#
# Fica FORA da imagem: o segredo (OPENAI_API_KEY, via --env-file em tempo de
# execução), o modelo (Groq, pela rede) e o estado (banco e registros, no
# volume montado em /dados).

# ---------------------------------------------------------------- 1
# Base fixada até o patch: python:3.11-slim é etiqueta móvel.
FROM python:3.11.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# ---------------------------------------------------------------- 2
# Dependências antes do código: a camada cara só é refeita quando elas mudam.
COPY requirements-agente.txt .
RUN pip install --no-cache-dir -r requirements-agente.txt

# ---------------------------------------------------------------- 3
# Usuário sem privilégio, e o diretório do estado já com o dono certo — um
# volume nomeado novo montado em /dados herda esse dono.
RUN useradd --create-home --uid 10001 agente \
    && mkdir -p /dados/logs \
    && chown -R agente:agente /dados

# ---------------------------------------------------------------- 4
# Só os arquivos que o agente usa, por nome — segunda barreira contra o .env,
# além do .dockerignore.
COPY src/agente.py src/dados.py src/api.py src/chat.py ./src/
COPY prompts/triagem-v1.txt ./prompts/

# ---------------------------------------------------------------- 5
ENV ACADEMICO_DB=/dados/academico.db \
    LOGS_DIR=/dados/logs
USER agente
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=2)"]
CMD ["uvicorn", "api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
