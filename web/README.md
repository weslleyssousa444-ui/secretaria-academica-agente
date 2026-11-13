# Página de chat do agente (publicada na Hostinger)

A interface web usada na demonstração: `index.html` (chat, histórico de conversas salvo no navegador, painel de alunos de teste, fontes e suficiência de cada resposta, diagnóstico de erro) e `api.php`, um repasse mínimo para a API do agente que deixa passar **só** `GET /saude` e `POST /mensagens` (as rotas da coordenação não ficam expostas). `config.php` guarda só a URL do servidor; **nenhuma chave** fica aqui: a da Groq está nas variáveis de ambiente do servidor (Render).

Para publicar: copie os três arquivos para `public_html` de um site com PHP e ajuste `BACKEND_URL` em `config.php`. A lista de alunos do painel espelha `src/dados.py`; se a base mudar, atualize `ALUNOS` e `DEBITO` em `index.html`.
