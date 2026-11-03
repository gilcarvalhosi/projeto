"""Abre a interface web do DuckDB sobre um banco já existente.

O script verifica o arquivo antes de conectar para que um banco vazio não
mascare a ausência da ingestão. A extensão ui fornece a exploração no
navegador; a conexão é mantida viva para servir a interface e só é fechada
quando Ctrl+C encerra o processo, liberando o lock do arquivo para a próxima
execução do pipeline. A saída é reconfigurada para UTF-8 para preservar os
acentos no Prompt de Comando do Windows.
"""

import sys
import time
from pathlib import Path

import duckdb


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    caminho_banco = Path(__file__).resolve().parent / "netflix.duckdb"
    if not caminho_banco.is_file():
        print(
            f"Banco não encontrado: {caminho_banco}. "
            "É preciso rodar a ingestão antes."
        )
        sys.exit(1)

    con = duckdb.connect(str(caminho_banco))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print("Interface disponível em http://localhost:4213")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        con.close()


if __name__ == "__main__":
    main()
