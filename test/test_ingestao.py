import gzip

import duckdb
import pytest

from pipeline import ingestao


def test_csv_gz_vira_tabelas_com_linhas_e_nulos_preservados(
    tmp_path, monkeypatch, capsys
):
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    caminho_banco = tmp_path / "unitario.duckdb"
    monkeypatch.setattr(
        ingestao,
        "conectar",
        lambda: duckdb.connect(str(caminho_banco)),
    )

    # Uma linha de elenco representa um crédito normal.
    # A linha seguinte mantém o crédito mesmo sem personagem conhecido.
    with gzip.open(pasta_raw / "credits.csv.gz", "wt", encoding="utf-8") as arquivo:
        arquivo.write(
            "person_id,id,name,character,role\n"
            "10,t1,Atriz Inventada,Heroina,ACTOR\n"
            "11,t1,Diretor Inventado,,DIRECTOR\n"
        )
    with gzip.open(pasta_raw / "credits.csv.gz", "rt", encoding="utf-8") as origem:
        (pasta_raw / "credits.csv").write_text(origem.read(), encoding="utf-8")
    # Um filme e uma série garantem que a ingestão preserve os dois tipos.
    with gzip.open(pasta_raw / "titles.csv.gz", "wt", encoding="utf-8") as arquivo:
        arquivo.write(
            "id,title,type\n"
            "t1,Filme Inventado,MOVIE\n"
            "t2,Série Inventada,SHOW\n"
        )
    with gzip.open(pasta_raw / "titles.csv.gz", "rt", encoding="utf-8") as origem:
        (pasta_raw / "titles.csv").write_text(origem.read(), encoding="utf-8")

    ingestao.main()
    saida = capsys.readouterr().out

    con = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert con.execute(
            "SELECT person_id, id, name, character, role FROM raw.elenco ORDER BY person_id"
        ).fetchall() == [
            ("10", "t1", "Atriz Inventada", "Heroina", "ACTOR"),
            ("11", "t1", "Diretor Inventado", None, "DIRECTOR"),
        ]
        assert con.execute(
            "SELECT id, title, type FROM raw.titulo ORDER BY id"
        ).fetchall() == [
            ("t1", "Filme Inventado", "MOVIE"),
            ("t2", "Série Inventada", "SHOW"),
        ]
        assert "raw.elenco: 2" in saida
        assert "raw.titulo: 2" in saida
        assert "Total: 4" in saida
    finally:
        con.close()


def test_arquivo_faltando_encerra_antes_de_abrir_o_banco(
    tmp_path, monkeypatch, capsys
):
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    caminho_banco = tmp_path / "nao_criar.duckdb"
    monkeypatch.setattr(
        ingestao,
        "conectar",
        lambda: duckdb.connect(str(caminho_banco)),
    )
    # Somente titles existe; credits está ausente e deve interromper a ingestão.
    with gzip.open(pasta_raw / "titles.csv.gz", "wt", encoding="utf-8") as arquivo:
        arquivo.write("id,title,type\nt1,Título Inventado,MOVIE\n")

    with pytest.raises(SystemExit) as erro:
        ingestao.main()

    assert erro.value.code == 1
    assert "credits.csv" in capsys.readouterr().out
    assert not caminho_banco.exists()
