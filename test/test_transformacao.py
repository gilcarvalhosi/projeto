import duckdb
import pytest

from pipeline import transformacao


def _titulo(**alteracoes):
    valores = {
        "id": "tm-filme",
        "title": "Filme Inventado",
        "type": "MOVIE",
        "description": "Entrada criada pelo teste",
        "release_year": "2020",
        "age_certification": "PG",
        "runtime": "98",
        "genres": "['Drama']",
        "production_countries": "['BR']",
        "seasons": None,
        "imdb_id": "tt0000001",
        "imdb_score": "7.5",
        "imdb_votes": "12",
        "tmdb_popularity": "3.25",
        "tmdb_score": "7.2",
    }
    valores.update(alteracoes)
    return tuple(valores[coluna] for coluna in transformacao.MAPAS["titulo"])


def _preparar_banco(con, *, elenco=None, titulos=None):
    con.execute("CREATE SCHEMA raw")
    for tabela, mapa, linhas in (
        ("elenco", transformacao.MAPAS["elenco"], elenco or []),
        ("titulo", transformacao.MAPAS["titulo"], titulos or []),
    ):
        colunas = ", ".join(f'"{coluna}" VARCHAR' for coluna in mapa)
        con.execute(f"CREATE TABLE raw.{tabela} ({colunas})")
        if linhas:
            marcadores = ", ".join("?" for _ in mapa)
            con.executemany(
                f"INSERT INTO raw.{tabela} VALUES ({marcadores})",
                linhas,
            )


def _conectar_teste(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "transformacao.duckdb"
    monkeypatch.setattr(
        transformacao,
        "conectar",
        lambda: duckdb.connect(str(caminho_banco)),
    )
    return caminho_banco


def test_transforma_tipos_e_preserva_nulos_sem_apagar_linhas(
    tmp_path, monkeypatch, capsys
):
    caminho_banco = _conectar_teste(tmp_path, monkeypatch)
    con = duckdb.connect(str(caminho_banco))
    # O crédito normal exercita o cast de pessoa_id e a chave de elenco.
    linha_elenco = ("42", "tm-filme", "Atriz Inventada", "Heroina", "ACTOR")
    # A nota e a faixa etária nulas devem permanecer NULL, sem remover o filme.
    linha_titulo = _titulo(imdb_score=None, age_certification=None)
    _preparar_banco(con, elenco=[linha_elenco], titulos=[linha_titulo])
    con.close()

    transformacao.main()

    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute(
            "SELECT pessoa_id, elenco_id, nome_elenco, funcao FROM refined.elenco"
        ).fetchall() == [(42, "tm-filme", "Atriz Inventada", "ACTOR")]
        assert con.execute(
            "SELECT titulo_id, ano_lançamento, tempo_execucao, imdb_votos, "
            "imdb_pontuacao, imdb_popularidade, tmdb_pontuacao, "
            "faixa_etaria, temporadas FROM refined.titulo"
        ).fetchall() == [
            ("tm-filme", 2020, 98, 12, None, 3.25, 7.2, None, None)
        ]
        tipos = dict(
            con.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'refined' AND table_name = 'titulo'"
            ).fetchall()
        )
        assert tipos["titulo_id"] == "VARCHAR"
        assert tipos["ano_lançamento"] == "INTEGER"
        assert tipos["imdb_pontuacao"] == "DOUBLE"
        assert tipos["titulo"] == "VARCHAR"
        assert "refined.titulo" in capsys.readouterr().out
    finally:
        con.close()


def test_duplicata_exata_de_elenco_sai_e_e_contada(tmp_path, monkeypatch, capsys):
    caminho_banco = _conectar_teste(tmp_path, monkeypatch)
    con = duckdb.connect(str(caminho_banco))
    # A mesma participação aparece duas vezes para verificar deduplicação exata.
    credito = ("7", "tm-filme", "Atriz Inventada", "Heroina", "ACTOR")
    _preparar_banco(con, elenco=[credito, credito], titulos=[_titulo()])
    con.close()

    transformacao.main()

    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM refined.elenco").fetchone() == (1,)
        assert "(1 duplicatas)" in capsys.readouterr().out
    finally:
        con.close()


def test_valor_numerico_invalido_encerra_sem_fabricar_nulo(
    tmp_path, monkeypatch, capsys
):
    caminho_banco = _conectar_teste(tmp_path, monkeypatch)
    con = duckdb.connect(str(caminho_banco))
    # O texto inválido em imdb_score deve falhar em vez de virar NULL.
    _preparar_banco(
        con,
        titulos=[
            _titulo(id="tm-nulo", imdb_score=None),
            _titulo(id="tm-invalido", imdb_score="nota inválida"),
        ],
    )
    con.close()

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    saida = capsys.readouterr().out
    assert "tabela raw.titulo" in saida
    assert "imdb_score" in saida
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'refined'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_chave_conflitante_mostra_linhas_e_interrompe(tmp_path, monkeypatch, capsys):
    caminho_banco = _conectar_teste(tmp_path, monkeypatch)
    con = duckdb.connect(str(caminho_banco))
    # Mesmo conjunto de chave com nomes diferentes representa conteúdo conflitante.
    creditos = [
        ("9", "tm-filme", "Nome A", None, "ACTOR"),
        ("9", "tm-filme", "Nome B", None, "ACTOR"),
    ]
    _preparar_banco(con, elenco=creditos, titulos=[_titulo()])
    con.close()

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    saida = capsys.readouterr().out
    assert "Chave conflitante em raw.elenco" in saida
    assert "<NULL>" in saida
    assert "Nome A" in saida
    assert "Nome B" in saida


def test_coluna_raw_inesperada_encerra_sem_descartar_silenciosamente(
    tmp_path, monkeypatch, capsys
):
    caminho_banco = _conectar_teste(tmp_path, monkeypatch)
    con = duckdb.connect(str(caminho_banco))
    _preparar_banco(con, titulos=[_titulo()])
    con.execute("ALTER TABLE raw.titulo ADD COLUMN coluna_nova VARCHAR")
    con.close()

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    saida = capsys.readouterr().out
    assert "coluna_nova" in saida
    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'refined'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_tabela_raw_faltando_lista_entrada_e_encerra(tmp_path, monkeypatch, capsys):
    caminho_banco = _conectar_teste(tmp_path, monkeypatch)
    con = duckdb.connect(str(caminho_banco))
    con.execute("CREATE SCHEMA raw")
    con.execute('CREATE TABLE raw.elenco ("person_id" VARCHAR)')
    con.close()

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    assert "raw.titulo" in capsys.readouterr().out
