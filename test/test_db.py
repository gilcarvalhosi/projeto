import duckdb
import pandas as pd

from pipeline import db


def test_conectar_cria_banco_ao_lado_da_raiz_do_projeto(tmp_path, monkeypatch):
    pasta_pipeline = tmp_path / "pipeline"
    pasta_pipeline.mkdir()
    arquivo_modulo = pasta_pipeline / "db.py"
    arquivo_modulo.touch()
    monkeypatch.setattr(db, "__file__", str(arquivo_modulo))

    con = db.conectar()
    try:
        assert (tmp_path / "netflix.duckdb").is_file()
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_criar_schema_e_gravar_recriam_tabela_com_nomes_quotados(tmp_path):
    con = duckdb.connect(str(tmp_path / "unitario.duckdb"))
    try:
        db.criar_schema(con, "schema com espaço")
        db.criar_schema(con, "schema com espaço")
        primeira_versao = pd.DataFrame({"valor com espaço": [1, 2]})

        linhas_primeira_versao = db.gravar(
            con, primeira_versao, "schema com espaço", "tabela teste"
        )
        segunda_versao = pd.DataFrame({"valor com espaço": [3]})
        linhas_segunda_versao = db.gravar(
            con, segunda_versao, "schema com espaço", "tabela teste"
        )

        assert linhas_primeira_versao == 2
        assert linhas_segunda_versao == 1
        assert con.execute(
            'SELECT "valor com espaço" FROM "schema com espaço"."tabela teste"'
        ).fetchall() == [(3,)]
    finally:
        con.close()
