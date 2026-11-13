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
COPY src/agente.py src/dados.py src/api.py src/chat.py src/coordenacao.py \
     src/chunking.py src/memoria_semantica.py src/memoria_procedural.py ./src/
COPY src/triagem/ ./src/triagem/
# agente.py ainda lê a v1 (laço da Parte 1, motor das ferramentas); o grafo lê a v3 (13/11/2026).
COPY src/prompts/triagem-v1.txt src/prompts/triagem-v3.txt ./src/prompts/
# O Regimento simulado, fonte do RAG (src/triagem/regimento.py).
COPY dados/regimento_dados.py ./dados/

# ---------------------------------------------------------------- 5
# O commit entra como argumento do build (a imagem não tem .git): é o que o
# trace carrega em `agente.versao` (docs/observabilidade.md §2).
ARG COMMIT=desconhecido
ENV ACADEMICO_DB=/dados/academico.db \
    LOGS_DIR=/dados/logs \
    TRIAGEM_CHECKPOINT=/dados/triagem.sqlite \
    TRIAGEM_MEMORIA_DIR=/dados/memoria \
    TRIAGEM_TRACES_DIR=/dados/traces \
    AGENTE_COMMIT=$COMMIT
USER agente
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=2)"]
CMD ["uvicorn", "api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
