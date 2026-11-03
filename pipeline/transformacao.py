"""Transformação de raw para refined, conforme a spec do pipeline.

Esta etapa lê somente raw.elenco e raw.titulo e grava em refined, sem alterar
as fontes, para manter visível a fronteira entre dado recebido e tratado.
O mapa renomeia todas as colunas para preservar o vocabulário de JOINs da aula;
colunas omitidas ou inesperadas são erro, para não descartar dados em silêncio.
Tipos numéricos são convertidos com CAST (sem conversão tolerante), pois um
nulo criado por falha não pode ser confundido com um nulo original. As
conversões incompatíveis informam tabela, coluna e amostra e encerram a etapa.
Duplicatas de linha inteira são removidas e contadas; chaves repetidas com
conteúdo diferente interrompem a execução, pois escolher uma linha seria uma
decisão silenciosa. Nulos nunca removem linhas nem são preenchidos: sua
contagem é mostrada no resultado final.
As tabelas são recriadas com CREATE OR REPLACE para tornar a reexecução
idempotente. A verificação das entradas ocorre antes da transformação para
evitar uma execução parcial quando uma tabela não foi ingerida.

As confirmações específicas desta execução usam netflix.duckdb, somente as
duas tabelas existentes e as grafias corrigidas do mapa. Para elenco, a chave
foi expandida para incluir funcao e nome_personagem: a chave originalmente
proposta conflita com participações distintas de uma mesma pessoa no mesmo
título, enquanto esta chave distingue as linhas existentes. Os tipos numéricos
foram ajustados aos valores reais do dataset: IDs textuais, classificações
etárias e imdb_id permanecem VARCHAR; notas e popularidades fracionárias são
DOUBLE. Não há coluna de data nesta fonte, portanto não há uso de strptime.
"""

import sys
from collections.abc import Mapping

import duckdb
import pandas as pd

from pipeline.db import conectar, criar_schema

MAPAS: dict[str, dict[str, str]] = {
    "elenco": {
        "person_id": "pessoa_id",
        "id": "elenco_id",
        "name": "nome_elenco",
        "character": "nome_personagem",
        "role": "funcao",
    },
    "titulo": {
        "id": "titulo_id",
        "title": "titulo",
        "type": "tipo",
        "description": "descricao",
        "release_year": "ano_lançamento",
        "age_certification": "faixa_etaria",
        "runtime": "tempo_execucao",
        "genres": "genero",
        "production_countries": "pais_origem",
        "seasons": "temporadas",
        "imdb_id": "imdb_id",
        "imdb_score": "imdb_pontuacao",
        "imdb_votes": "imdb_votos",
        "tmdb_popularity": "imdb_popularidade",
        "tmdb_score": "tmdb_pontuacao",
    },
}

TIPOS: dict[str, str] = {
    "pessoa_id": "INTEGER",
    "ano_lançamento": "INTEGER",
    "tempo_execucao": "INTEGER",
    "temporadas": "INTEGER",
    "imdb_votos": "INTEGER",
    "imdb_pontuacao": "DOUBLE",
    "imdb_popularidade": "DOUBLE",
    "tmdb_pontuacao": "DOUBLE",
}

CHAVES: dict[str, tuple[str, ...]] = {
    "elenco": ("pessoa_id", "elenco_id", "funcao", "nome_personagem"),
    "titulo": ("titulo_id",),
}


def _identificador(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _exibir_valor(valor: object) -> str:
    if pd.isna(valor):
        return "<NULL>"
    return repr(valor)


def _validar_cast(
    con: duckdb.DuckDBPyConnection,
    dataframe: pd.DataFrame,
    tabela: str,
    coluna_origem: str,
    tipo: str,
    relacao: str,
) -> None:
    coluna = _identificador(coluna_origem)
    try:
        con.execute(f"SELECT CAST({coluna} AS {tipo}) FROM {_identificador(relacao)}").fetchall()
    except duckdb.ConversionException:
        for valor in dataframe[coluna_origem]:
            if pd.isna(valor):
                continue
            try:
                con.execute(f"SELECT CAST(? AS {tipo})", [valor]).fetchone()
            except duckdb.ConversionException:
                print(
                    f"Erro de conversão: tabela raw.{tabela}, coluna "
                    f"{coluna_origem}, valor {_exibir_valor(valor)} não converte "
                    f"para {tipo}."
                )
                sys.exit(1)
        raise


def _verificar_duplicatas(
    dataframe: pd.DataFrame,
    tabela: str,
    mapa: Mapping[str, str],
) -> tuple[pd.DataFrame, int]:
    quantidade_original = len(dataframe)
    sem_repeticoes = dataframe.drop_duplicates(keep="first").reset_index(drop=True)
    duplicatas = quantidade_original - len(sem_repeticoes)
    chaves_origem = [coluna for coluna, nome in mapa.items() if nome in CHAVES[tabela]]

    for valores_chave, grupo in sem_repeticoes.groupby(
        chaves_origem, dropna=False, sort=False
    ):
        if len(grupo) < 2:
            continue
        if not isinstance(valores_chave, tuple):
            valores_chave = (valores_chave,)
        chave = {
            mapa[coluna]: _exibir_valor(valor)
            for coluna, valor in zip(chaves_origem, valores_chave, strict=True)
        }
        print(f"Chave conflitante em raw.{tabela}: {chave}")
        print("Linhas conflitantes:")
        print(grupo.to_string(index=False))
        sys.exit(1)

    return sem_repeticoes, duplicatas


def _preparar_tabela(
    con: duckdb.DuckDBPyConnection, tabela: str
) -> tuple[pd.DataFrame, int, int]:
    mapa = MAPAS[tabela]
    nome_relacao = f"entrada_{tabela}"
    resultado = con.execute(f"SELECT * FROM raw.{_identificador(tabela)}")
    dataframe = pd.DataFrame(
        resultado.fetchall(), columns=[descricao[0] for descricao in resultado.description]
    )

    colunas_faltantes = [coluna for coluna in mapa if coluna not in dataframe.columns]
    colunas_inesperadas = [coluna for coluna in dataframe.columns if coluna not in mapa]
    if colunas_faltantes or colunas_inesperadas:
        print(
            f"Colunas incompatíveis em raw.{tabela}: "
            f"faltando={colunas_faltantes}, inesperadas={colunas_inesperadas}."
        )
        sys.exit(1)

    quantidade_entrada = len(dataframe)
    dataframe, duplicatas = _verificar_duplicatas(dataframe, tabela, mapa)
    con.register(nome_relacao, dataframe)
    try:
        for coluna_origem, coluna_destino in mapa.items():
            tipo = TIPOS.get(coluna_destino)
            if tipo is not None:
                _validar_cast(
                    con,
                    dataframe,
                    tabela,
                    coluna_origem,
                    tipo,
                    nome_relacao,
                )
    finally:
        con.unregister(nome_relacao)

    return dataframe, quantidade_entrada, duplicatas


def _criar_tabela(
    con: duckdb.DuckDBPyConnection,
    tabela: str,
    dataframe: pd.DataFrame,
) -> int:
    mapa = MAPAS[tabela]
    nome_relacao = f"entrada_{tabela}"
    con.register(nome_relacao, dataframe)
    try:
        selecoes = []
        for coluna_origem, coluna_destino in mapa.items():
            origem = _identificador(coluna_origem)
            destino = _identificador(coluna_destino)
            tipo = TIPOS.get(coluna_destino)
            expressao = f"CAST({origem} AS {tipo})" if tipo else origem
            selecoes.append(f"{expressao} AS {destino}")
        con.execute(
            f"CREATE OR REPLACE TABLE refined.{_identificador(tabela)} "
            f"AS SELECT {', '.join(selecoes)} FROM {_identificador(nome_relacao)}"
        ).fetchall()
    finally:
        con.unregister(nome_relacao)
    return con.execute(
        f"SELECT count(*) FROM refined.{_identificador(tabela)}"
    ).fetchall()[0][0]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    tabelas = tuple(MAPAS)
    con = conectar()
    try:
        existentes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'raw' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        faltantes = [tabela for tabela in tabelas if tabela not in existentes]
        if faltantes:
            nomes = ", ".join(f"raw.{tabela}" for tabela in faltantes)
            print(
                f"Tabelas de entrada ausentes: {nomes}. "
                'Execute "uv run python -m pipeline.ingestao".'
            )
            sys.exit(1)

        preparados = {
            tabela: _preparar_tabela(con, tabela)
            for tabela in tabelas
        }
        criar_schema(con, "refined")

        total_final = 0
        for tabela in tabelas:
            dataframe, quantidade_entrada, duplicatas = preparados[tabela]
            quantidade_final = _criar_tabela(con, tabela, dataframe)
            total_final += quantidade_final
            print(
                f"refined.{tabela:<18} {quantidade_entrada:>7,} -> "
                f"{quantidade_final:>7,} linhas  ({duplicatas} duplicatas)"
                .replace(",", ".")
            )

            colunas = [nome for nome in MAPAS[tabela].values()]
            nulos = []
            for coluna in colunas:
                quantidade_nulos = con.execute(
                    f"SELECT count(*) FROM refined.{_identificador(tabela)} "
                    f"WHERE {_identificador(coluna)} IS NULL"
                ).fetchall()[0][0]
                if quantidade_nulos:
                    nulos.append((coluna, quantidade_nulos))
            for coluna, quantidade in nulos:
                print(f"  nulos mantidos: {coluna}: {quantidade:,}".replace(",", "."))

        print(f"Total refined: {total_final:,} linhas".replace(",", "."))
    finally:
        con.close()


if __name__ == "__main__":
    main()
