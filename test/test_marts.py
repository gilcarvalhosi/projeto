from pathlib import Path

import duckdb
import pytest

from pipeline import marts


def _preparar_pipeline(tmp_path, monkeypatch, *, mart_existente=False):
    caminho_banco = tmp_path / "unitario.duckdb"
    pasta_sql = tmp_path / "sql_marts"
    pasta_sql.mkdir()
    con = duckdb.connect(str(caminho_banco))
    con.execute("CREATE SCHEMA refined")
    con.execute("CREATE TABLE refined.elenco (id INTEGER)")
    con.execute("CREATE TABLE refined.titulo (id INTEGER)")
    if mart_existente:
        con.execute("CREATE SCHEMA marts")
        con.execute("CREATE TABLE marts.anterior AS SELECT 77 AS valor")
    con.close()

    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)
    monkeypatch.setattr(
        marts,
        "conectar",
        lambda: duckdb.connect(str(caminho_banco)),
    )
    return caminho_banco, pasta_sql


def test_arquivo_apagado_remove_mart_na_execucao_seguinte(
    tmp_path, monkeypatch, capsys
):
    caminho_banco, pasta_sql = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )
    # O SELECT simples cria um mart de teste com uma linha persistida.
    arquivo = pasta_sql / "00_teste.sql"
    arquivo.write_text("SELECT 1 AS x;", encoding="utf-8")

    marts.main()

    con = duckdb.connect(str(caminho_banco))
    try:
        assert con.execute("SELECT x FROM marts.teste").fetchall() == [(1,)]
    finally:
        con.close()
    assert "marts.teste" in capsys.readouterr().out

    # Substituir o arquivo simula a remoção do mart antigo na próxima geração.
    arquivo.unlink()
    (pasta_sql / "01_novo.sql").write_text("SELECT 2 AS x", encoding="utf-8")
    marts.main()

    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        nomes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts'"
            ).fetchall()
        }
        assert nomes == {"novo"}
        assert con.execute("SELECT x FROM marts.novo").fetchall() == [(2,)]
    finally:
        con.close()


def test_arquivo_sem_prefixo_interrompe_antes_de_executar_sql(
    tmp_path, monkeypatch, capsys
):
    caminho_banco, pasta_sql = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )
    # O SQL seria válido; o nome inválido deve ser detectado antes da execução.
    (pasta_sql / "teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    assert "teste.sql" in capsys.readouterr().out
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchall() == [(77,)]
    finally:
        con.close()


def test_pasta_sem_arquivos_sql_encerra_sem_substituir_schema(
    tmp_path, monkeypatch, capsys
):
    caminho_banco, _ = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    assert "Nenhum arquivo .sql" in capsys.readouterr().out
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchall() == [(77,)]
    finally:
        con.close()


def test_arquivos_com_nome_de_tabela_duplicado_encerra(
    tmp_path, monkeypatch, capsys
):
    caminho_banco, pasta_sql = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )
    # Consultas válidas com prefixos distintos colidem no mesmo nome de saída.
    (pasta_sql / "01_repetido.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    (pasta_sql / "02_repetido.sql").write_text("SELECT 2 AS x", encoding="utf-8")

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    assert "01_repetido.sql" in capsys.readouterr().out
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchall() == [(77,)]
    finally:
        con.close()


def test_tabela_refined_ausente_encerra_antes_de_executar_sql(
    tmp_path, monkeypatch, capsys
):
    caminho_banco, pasta_sql = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )
    con = duckdb.connect(str(caminho_banco))
    con.execute("DROP TABLE refined.titulo")
    con.close()
    # Esta consulta é válida, mas a tabela de entrada ausente deve impedir sua execução.
    (pasta_sql / "00_nao_executar.sql").write_text(
        "SELECT 1 AS x", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    assert "refined.titulo" in capsys.readouterr().out
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchall() == [(77,)]
    finally:
        con.close()


def test_mart_vazio_faz_rollback_do_schema_anterior(tmp_path, monkeypatch, capsys):
    caminho_banco, pasta_sql = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )
    # Este mart inicial tem uma linha e seria criado antes do vazio.
    (pasta_sql / "00_valido.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    # O resultado vazio deve cancelar toda a transação, incluindo o mart válido.
    (pasta_sql / "01_vazio.sql").write_text(
        "SELECT 2 AS x WHERE FALSE", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    assert "01_vazio.sql" in capsys.readouterr().out
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        nomes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts'"
            ).fetchall()
        }
        assert nomes == {"anterior"}
        assert con.execute("SELECT valor FROM marts.anterior").fetchall() == [(77,)]
    finally:
        con.close()


def test_sql_invalido_mostra_arquivo_e_restaura_schema(
    tmp_path, monkeypatch, capsys
):
    caminho_banco, pasta_sql = _preparar_pipeline(
        tmp_path, monkeypatch, mart_existente=True
    )
    (pasta_sql / "00_quebrado.sql").write_text("SELECT FROM", encoding="utf-8")

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    saida = capsys.readouterr().out
    assert "00_quebrado.sql" in saida
    assert "syntax" in saida.lower() or "parser" in saida.lower()
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchall() == [(77,)]
    finally:
        con.close()


def test_sql_de_participacoes_conta_titulo_distinto_e_filtra_funcao(tmp_path):
    con = duckdb.connect(str(tmp_path / "consultas.duckdb"))
    try:
        con.execute("CREATE SCHEMA refined")
        con.execute(
            "CREATE TABLE refined.titulo "
            "(titulo_id VARCHAR, titulo VARCHAR, tipo VARCHAR, "
            "imdb_pontuacao DOUBLE, tmdb_pontuacao DOUBLE)"
        )
        con.execute(
            "CREATE TABLE refined.elenco "
            "(pessoa_id INTEGER, nome_elenco VARCHAR, elenco_id VARCHAR, funcao VARCHAR)"
        )
        # Os três títulos cobrem filme, série e um título sem papel de ator.
        con.executemany(
            "INSERT INTO refined.titulo VALUES (?, ?, ?, ?, ?)",
            [
                ("t1", "Filme Um", "MOVIE", 8.0, 7.0),
                ("t2", "Série Dois", "SHOW", 7.0, 6.0),
                ("t3", "Filme Três", "MOVIE", 6.0, 5.0),
            ],
        )
        # O ator 1 tem duas linhas no mesmo filme, mas esse título conta uma vez.
        # A segunda aparição em série deve entrar no total e no tipo correto.
        # O ator 2 participa do mesmo filme como ator independente.
        # A última linha é de diretor e não deve ser contada como ator.
        con.executemany(
            "INSERT INTO refined.elenco VALUES (?, ?, ?, ?)",
            [
                (1, "Atriz Um", "t1", "ACTOR"),
                (1, "Atriz Um", "t1", "ACTOR"),
                (1, "Atriz Um", "t2", "ACTOR"),
                (2, "Ator Dois", "t1", "ACTOR"),
                (3, "Diretor Três", "t3", "DIRECTOR"),
            ],
        )
        sql = (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "marts"
            / "01_ator_maior_participacao.sql"
        ).read_text(encoding="utf-8")

        linhas = con.execute(sql).fetchall()

        atriz = [linha for linha in linhas if linha[2] == "Atriz Um"]
        assert len(atriz) == 2
        assert all(linha[3:6] == (2, 1, 1) for linha in atriz)
        assert all(linha[2] != "Diretor Três" for linha in linhas)
    finally:
        con.close()


def test_sql_de_maior_elenco_conta_atores_distintos_e_exclui_series(tmp_path):
    con = duckdb.connect(str(tmp_path / "elencos.duckdb"))
    try:
        con.execute("CREATE SCHEMA refined")
        con.execute(
            "CREATE TABLE refined.titulo "
            "(titulo_id VARCHAR, titulo VARCHAR, tipo VARCHAR, "
            "imdb_pontuacao DOUBLE, tmdb_pontuacao DOUBLE)"
        )
        con.execute(
            "CREATE TABLE refined.elenco "
            "(pessoa_id INTEGER, elenco_id VARCHAR, funcao VARCHAR)"
        )
        # Um filme com duas pessoas atuando e uma linha de diretor.
        # Uma série é incluída para provar que o mart só retorna filmes.
        con.executemany(
            "INSERT INTO refined.titulo VALUES (?, ?, ?, ?, ?)",
            [
                ("f1", "Filme Elenco", "MOVIE", 8.2, 7.8),
                ("s1", "Série Elenco", "SHOW", 9.0, 9.0),
            ],
        )
        # A repetição da pessoa 1 representa créditos múltiplos e conta uma vez.
        # A segunda pessoa é um ator distinto; o diretor não entra na contagem.
        # Créditos da série devem ser excluídos pela condição de tipo.
        con.executemany(
            "INSERT INTO refined.elenco VALUES (?, ?, ?)",
            [
                (1, "f1", "ACTOR"),
                (1, "f1", "ACTOR"),
                (2, "f1", "ACTOR"),
                (3, "f1", "DIRECTOR"),
                (4, "s1", "ACTOR"),
            ],
        )
        sql = (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "marts"
            / "03_maior_elenco_e_avaliacao_top_5.sql"
        ).read_text(encoding="utf-8")

        linhas = con.execute(sql).fetchall()

        assert linhas == [("f1", "Filme Elenco", 2, 8.2, 7.8)]
    finally:
        con.close()
