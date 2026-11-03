"""Módulo de conexão compartilhado pelas etapas do pipeline.

O caminho do banco e da pasta raw é relativo a este arquivo, não ao diretório
de execução, para que chamadas feitas de outra pasta não criem um banco no
lugar errado. Este módulo expõe somente a pasta raw e as três operações
genéricas previstas: abrir a conexão, criar um schema e recriar uma tabela.
Ele não decide regras de negócio, não transforma dados e não mantém conexão
global, pois cada etapa deve controlar suas próprias decisões e fechamento.
A gravação retorna a contagem consultada no banco para conferir o que foi
persistido, e a consulta é feita após CREATE OR REPLACE para que reexecuções
não acumulem linhas nem deixem objetos temporários para trás.
"""

from pathlib import Path

import duckdb
import pandas as pd

PASTA_RAW = Path(__file__).resolve().parent.parent / "raw"


def conectar() -> duckdb.DuckDBPyConnection:
    """Abre o banco localizado na raiz do projeto."""
    caminho_banco = Path(__file__).resolve().parent.parent / "netflix.duckdb"
    return duckdb.connect(str(caminho_banco))


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    """Cria o schema se ele ainda não existir."""
    identificador = '"' + nome.replace('"', '""') + '"'
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {identificador}")


def gravar(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    schema: str,
    tabela: str,
) -> int:
    """Recria uma tabela a partir do DataFrame e devolve sua contagem no banco."""
    identificador_schema = '"' + schema.replace('"', '""') + '"'
    identificador_tabela = '"' + tabela.replace('"', '""') + '"'
    destino = f"{identificador_schema}.{identificador_tabela}"
    con.execute(f"CREATE OR REPLACE TABLE {destino} AS SELECT * FROM df")
    return con.execute(f"SELECT count(*) FROM {destino}").fetchone()[0]
