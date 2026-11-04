# Netflix Analytics

Este projeto implementa um pipeline de dados para analisar o catálogo de filmes e séries da Netflix usando Python, DuckDB e SQL. A solução organiza a ingestão dos dados brutos, a padronização em camadas refinadas e a materialização de indicadores em tabelas de negócio (`marts`) para visualização em dashboard.

## Visão geral

O projeto trata dois arquivos de origem:

- `raw/credits.csv` — informações de elenco e participação
- `raw/titles.csv` — dados dos títulos (filmes e séries)

A arquitetura segue o fluxo:

1. `raw` — dados originais ingeridos fielmente
2. `refined` — transformação e normalização para uso analítico
3. `marts` — consultas materializadas para visualização e relatórios
4. `app.py` — dashboard em Streamlit com indicadores principais

## Objetivo

A análise tem como foco responder perguntas de negócio como:

- Quem são os atores com maior número de participações?
- Quais filmes possuem as melhores avaliações?
- Que produções têm os maiores elencos?
- Quais filmes têm maior duração?
- Quais países concentram mais produções?

## Estrutura do projeto

```text
projeto/
├── app.py                  # Dashboard principal em Streamlit
├── ui.py                  # Interface gráfica do DuckDB
├── netflix.duckdb         # Banco de dados DuckDB gerado pelo pipeline
├── pyproject.toml         # Configuração do projeto e dependências
├── raw/
│   ├── credits.csv
│   └── titles.csv
├── pipeline/
│   ├── db.py
│   ├── ingestao.py
│   ├── transformacao.py
│   └── marts.py
├── sql/
│   └── marts/
│       ├── 01_ator_maior_participacao.sql
│       ├── 02_avaliacao_top_5.sql
│       ├── 03_maior_elenco_e_avaliacao_top_5.sql
│       ├── 04_top_5_runtime.sql
│       └── 05_top5_paises_e_avaliacoes_5.sql
├── test/
│   └── ...
├── uv.lock
└── README.md
```

## Tecnologias utilizadas

- Python 3.14+
- DuckDB para armazenamento e consultas analíticas
- Pandas para leitura e manipulação de dados
- SQL para materialização dos indicadores
- Streamlit para dashboard interativo
- Plotly para gráficos

## Fluxo de trabalho do pipeline

### 1. Ingestão

O módulo `pipeline/ingestao.py` lê os arquivos CSV diretamente da pasta `raw/` e salva as tabelas no schema `raw` do banco `netflix.duckdb`.

Funções principais:

- leitura com `utf-8`
- preservação de texto original
- conversão dos campos vazios para `NULL`
- recriação das tabelas em cada execução

### 2. Transformação

O módulo `pipeline/transformacao.py` realiza a etapa de refinamento (`refined`), normalizando nomes de colunas e validando a integridade dos dados.

Principais regras:

- validação de colunas esperadas
- remoção de duplicatas em linhas inteiras
- verificação de chaves conflitantes
- conversão explícita de tipos numéricos
- criação de tabelas refinadas com `CREATE OR REPLACE`

### 3. Materialização de marts

O módulo `pipeline/marts.py` lê todos os arquivos `.sql` em `sql/marts/` em ordem alfabética e cria as tabelas do schema `marts`.

A aplicação verifica que as tabelas `refined.elenco` e `refined.titulo` existam antes de continuar, para evitar execução parcial.

## Marts disponíveis

### 01. Atores com maior participação

Indicador que calcula os atores com mais títulos creditados e separa participação por filmes e séries.

### 02. Top 5 filmes por avaliação

Lista os filmes com melhor pontuação em IMDb e TMDB, ordenados por avaliação e volume de votos.

### 03. Filmes com maiores elencos

Relaciona títulos com maior quantidade de atores distintos e suas avaliações.

### 04. Filmes de maior duração

Mostra os filmes com maior tempo de execução em minutos.

### 05. Países com mais produções

Agrupa produções por país de origem e calcula total de produções, média de avaliações e divisão por tipo (filme/série).

## Como executar o projeto

### Pré-requisitos

- Python 3.14 ou superior
- [uv](https://docs.astral.sh/uv/) para gerenciamento de dependências

### Instalação

```bash
uv sync
```

### Executar a ingestão

```bash
uv run python -m pipeline.ingestao
```

### Executar a transformação para refined

```bash
uv run python -m pipeline.transformacao
```

### Gerar os marts

```bash
uv run python -m pipeline.marts
```

### Iniciar o dashboard

```bash
uv run streamlit run app.py
```

### Abrir a interface do DuckDB

```bash
uv run python ui.py
```

## Observações

- O banco SQLite de desenvolvimento foi substituído por um banco DuckDB, mais adequado para análise analítica.
- Todas as etapas do pipeline são idempotentes, ou seja, podem ser executadas novamente sem acumular resíduos.
- A estrutura do projeto foi pensada para separar claramente fonte, tratamento e apresentação dos dados.

## Resultados esperados

Ao final da execução, o dashboard exibirá visualizações para:

- atores mais frequentes
- melhores avaliações de filmes
- elenco mais numeroso
- produções mais longas
- países com maior volume de conteúdo

## Licença

Este projeto foi desenvolvido para fins de estudo e análise de dados, sem uma licença comercial específica definida no repositório.
