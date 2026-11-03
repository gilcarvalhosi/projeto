"""Materialização atômica dos arquivos SQL em tabelas do schema marts.

Todos os arquivos .sql da pasta sql/marts são processados em ordem alfabética,
pois a ordem previsível facilita reproduzir e comparar execuções. Cada arquivo
origina uma tabela com o mesmo nome sem o prefixo numérico; manter a consulta
integral no próprio arquivo deixa a regra de negócio no SQL, sem reescrita pelo
Python. O schema marts é recriado para remover resultados de arquivos que
tenham sido apagados. A recriação e todas as tabelas ficam numa única
transação, assim uma falha restaura o schema da última execução bem-sucedida.
Arquivos vazios, nomes inválidos ou nomes de destino repetidos são recusados
antes de executar consultas, evitando mudanças parciais ou ambíguas. A
verificação das tabelas refined evita iniciar uma execução sem suas entradas.
Marts vazios são tratados como erro para não publicar resultados que possam
parecer válidos, mas estejam sem dados. As contagens são consultadas no banco,
formatadas com separador de milhar por ponto, e stdout usa UTF-8.

Foi confirmado para este projeto que as tabelas de entrada esperadas são
refined.elenco e refined.titulo.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import conectar

PASTA_MARTS = Path(__file__).resolve().parent.parent / "sql" / "marts"
TABELAS_REFINED = ("elenco", "titulo")
PADRAO_ARQUIVO = re.compile(r"^\d{2}_(.+)\.sql$")


def _identificador(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _formatar_quantidade(quantidade: int) -> str:
    return f"{quantidade:,}".replace(",", ".")


def _carregar_arquivos() -> list[tuple[Path, str, str]]:
    arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda caminho: caminho.name)
    if not arquivos:
        print(f"Nenhum arquivo .sql encontrado em {PASTA_MARTS}.")
        raise SystemExit(1)

    nomes: dict[str, list[str]] = {}
    for arquivo in arquivos:
        correspondencia = PADRAO_ARQUIVO.fullmatch(arquivo.name)
        if correspondencia is None:
            continue
        nomes.setdefault(correspondencia.group(1), []).append(arquivo.name)

    duplicados = {
        nome: arquivos_nome
        for nome, arquivos_nome in nomes.items()
        if len(arquivos_nome) > 1
    }
    detalhes = "; ".join(
            f"{nome}: {', '.join(arquivos_nome)}"
            for nome, arquivos_nome in sorted(duplicados.items())
    )
    invalidos = [
        arquivo.name
        for arquivo in arquivos
        if PADRAO_ARQUIVO.fullmatch(arquivo.name) is None
    ]
    if invalidos or duplicados:
        if invalidos:
            print(f"Arquivos sem prefixo NN_: {', '.join(invalidos)}.")
        if duplicados:
            print(f"Arquivos com o mesmo nome de tabela: {detalhes}.")
        raise SystemExit(1)

    carregados = []
    for arquivo in arquivos:
        correspondencia = PADRAO_ARQUIVO.fullmatch(arquivo.name)
        if correspondencia is None:
            continue
        try:
            sql = arquivo.read_text(encoding="utf-8").strip()
        except OSError as erro:
            print(f"Não foi possível ler {arquivo.name}: {erro}")
            raise SystemExit(1) from erro
        if sql.endswith(";"):
            sql = sql[:-1].rstrip()
        carregados.append((arquivo, correspondencia.group(1), sql))
    return carregados


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        existentes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'refined' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        faltantes = [tabela for tabela in TABELAS_REFINED if tabela not in existentes]
        if faltantes:
            nomes = ", ".join(f"refined.{tabela}" for tabela in faltantes)
            print(
                f"Tabelas refined ausentes: {nomes}. "
                'Execute "uv run python -m pipeline.transformacao".'
            )
            raise SystemExit(1)

        arquivos = _carregar_arquivos()
        con.execute("BEGIN TRANSACTION").fetchall()
        try:
            con.execute("DROP SCHEMA IF EXISTS marts CASCADE").fetchall()
            con.execute("CREATE SCHEMA marts").fetchall()

            resultados: list[tuple[str, int]] = []
            for arquivo, tabela, sql in arquivos:
                try:
                    con.execute(
                        f"CREATE TABLE marts.{_identificador(tabela)} AS {sql}"
                    ).fetchall()
                    quantidade = con.execute(
                        f"SELECT count(*) FROM marts.{_identificador(tabela)}"
                    ).fetchone()[0]
                except duckdb.Error as erro:
                    print(f"Erro em {arquivo.name}: {erro}")
                    raise SystemExit(1) from erro

                if quantidade == 0:
                    print(f"Mart vazio: {arquivo.name} (marts.{tabela}).")
                    raise SystemExit(1)
                resultados.append((tabela, quantidade))

            con.execute("COMMIT").fetchall()
        except BaseException:
            con.execute("ROLLBACK").fetchall()
            raise

        total_linhas = 0
        largura_nome = max(len(f"marts.{tabela}") for tabela, _ in resultados)
        for tabela, quantidade in resultados:
            nome = f"marts.{tabela}"
            print(
                f"✓ {nome:<{largura_nome}} "
                f"{_formatar_quantidade(quantidade)} linhas"
            )
            total_linhas += quantidade
        print(
            f"Total: {len(resultados)} marts, "
            f"{_formatar_quantidade(total_linhas)} linhas"
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
