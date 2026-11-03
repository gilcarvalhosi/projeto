"""Ingestão fiel dos CSVs originais para o schema raw.

Os arquivos são lidos diretamente de raw/, sem extração de ZIP, porque a
fronteira entre o dado recebido e qualquer tratamento deve permanecer visível
para a etapa refined. UTF-8 e dtype=str evitam adivinhação de encoding e
inferência de tipos; somente campos vazios viram nulos, sem alterar nomes,
valores ou linhas. A verificação de todos os arquivos antes de abrir o banco
evita uma ingestão parcial por fonte ausente. As tabelas são recriadas em cada
execução, e a saída mostra contagens consultadas no banco para conferir o
resultado persistido.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    arquivos = (("credits.csv", "elenco"), ("titles.csv", "titulo"))
    faltantes = [nome for nome, _ in arquivos if not (PASTA_RAW / nome).is_file()]
    if faltantes:
        print(
            f"Arquivos ausentes: {', '.join(faltantes)}. "
            f"Pasta verificada: {PASTA_RAW}"
        )
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, "raw")
        total = 0
        for arquivo, tabela in arquivos:
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                encoding="utf-8",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
                skip_blank_lines=False,
            )
            quantidade = gravar(con, df, "raw", tabela)
            total += quantidade
            print(f"raw.{tabela}: {quantidade:,}".replace(",", "."))
        print(f"Total: {total:,}".replace(",", "."))
    finally:
        con.close()


if __name__ == "__main__":
    main()
