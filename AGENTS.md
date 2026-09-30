# AGENTS.md — Pipeline + Dashboard de Indicadores do Banco Central

## Objetivo
Construir um projeto de portfólio: coletar séries da API SGS do Banco Central (sem chave), transformar e validar, exportar CSV/Parquet e exibir num dashboard interativo. Priorize simples, legível e funcionando.

## Stack (não trocar sem pedir)
Python 3.11+, `uv` (ou `pip` + `venv`), `httpx`, `pandas`, `pyarrow`, `streamlit`, `plotly`, `pytest`, `ruff`, GitHub Actions.

## Fonte de dados
- `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{CODIGO}/dados?formato=json&dataInicial=dd/MM/yyyy&dataFinal=dd/MM/yyyy`
- Resposta: `[{"data": "dd/MM/yyyy", "valor": "texto numérico"}]`
- Séries: 432 (meta Selic), 433 (IPCA mensal %), 1 (dólar venda). **Confirme códigos, formato e limites com uma chamada real antes de codar.**
- Séries diárias podem limitar a janela de datas por consulta: consulte em janelas.

## Estrutura
```
src/bcb_pipeline/  config.py, extract.py, transform.py, validate.py, load.py, cli.py
app/dashboard.py
data/raw/ (não versionar)   data/processed/
tests/ (com fixtures)       .github/workflows/ci.yml, refresh.yml
```
Fluxo: `extract → transform → validate → load → dashboard`. O dashboard só lê `data/processed/`, nunca chama a API.

## Comandos esperados
- Pipeline: `python -m bcb_pipeline.cli run`
- Dashboard: `streamlit run app/dashboard.py`
- Testes: `pytest`
- Lint: `ruff check . && ruff format --check .`

## Requisitos
- **Transform:** tipos corretos, sem duplicatas, colunas derivadas (IPCA acumulado 12m, média móvel do dólar, tabela mensal unificada).
- **Validate:** sem datas duplicadas ou nulos, faixas plausíveis, aviso se dados estiverem defasados.
- **Dashboard:** filtro de período e indicadores, gráficos Plotly, KPIs, tabela com botão de download de CSV, `st.cache_data`.

## Fases (uma por vez; pare e aguarde meu "ok" ao fim de cada)
0. Setup: repo, `pyproject.toml`, ruff, estrutura.
1. Extração: timeout, retry com backoff, janelas de datas, testes com fixtures.
2. Transformação e validação, com testes.
3. Carga e CLI (CSV + Parquet).
4. Dashboard.
5. CI, refresh semanal agendado e README (diagrama, screenshot, como rodar, decisões técnicas).

## Regras
1. Antes de cada fase, descreva o plano em poucas linhas.
2. Verifique a API real; não presuma formatos.
3. Testes nunca acessam a rede: use fixtures.
4. Mudanças pequenas, commits frequentes (Conventional Commits).
5. Sem segredos no repositório.
6. Sem complexidade extra (Docker, Airflow, banco de dados) sem aprovação.
7. Código e nomes em inglês; textos do dashboard e README em português.
8. Erros devem ter mensagens claras e acionáveis.
9. Ao fim de cada fase, informe o que foi feito, como verificar e o que ficou pendente.
10. Em caso de dúvida relevante, pergunte antes de assumir.

## Pronto quando
Pipeline roda com um comando, CSV/Parquet são gerados, dashboard funciona com download, testes e CI passam e o README permite rodar o projeto em menos de 5 minutos.
