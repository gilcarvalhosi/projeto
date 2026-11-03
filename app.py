from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

BANCO = Path(__file__).resolve().parent / "netflix.duckdb"
MARTS = {
    "ator_maior_participacao": "01 · Atores com mais participações",
    "avaliacao_top_5": "02 · Filmes mais bem avaliados",
    "maior_elenco_e_avaliacao_top_5": "03 · Filmes com maiores elencos",
    "top_5_runtime": "04 · Filmes de maior duração",
    "top5_paises_e_avaliacoes_5": "05 · Países com mais produções",
}
COR = "#E50914"

st.set_page_config(
    page_title="Netflix · Filmes e Séries",
    page_icon="🎬",
    layout="wide",
)


@st.cache_data
def ler_marts(
    caminho_banco: str,
) -> tuple[dict[str, pd.DataFrame], list[str], str | None]:
    if not Path(caminho_banco).is_file():
        return {}, list(MARTS), None

    con = None
    dados = {}
    faltantes = []
    try:
        con = duckdb.connect(caminho_banco, read_only=True)
        for nome in MARTS:
            try:
                dados[nome] = con.execute(
                    f"SELECT * FROM marts.{nome}"
                ).df()
            except duckdb.CatalogException:
                faltantes.append(nome)
    except duckdb.Error as erro:
        return {}, [], str(erro)
    finally:
        if con is not None:
            con.close()
    return dados, faltantes, None


def grafico_barras(
    dataframe,
    *,
    x: str,
    y: str,
    titulo: str,
    rotulo_x: str,
    rotulo_y: str,
    horizontal: bool = False,
):
    if horizontal:
        figura = px.bar(
            dataframe,
            x=x,
            y=y,
            orientation="h",
            labels={x: rotulo_x, y: rotulo_y},
            title=titulo,
        )
    else:
        figura = px.bar(
            dataframe,
            x=x,
            y=y,
            labels={x: rotulo_x, y: rotulo_y},
            title=titulo,
        )
    figura.update_traces(marker_color=COR)
    figura.update_layout(showlegend=False)
    return figura


st.title("Netflix · Filmes e Séries")
st.caption("Indicadores e consultas materializadas a partir dos marts SQL.")

if st.button("Recarregar dados"):
    ler_marts.clear()

dados, faltantes, erro_leitura = ler_marts(str(BANCO))
if erro_leitura or faltantes:
    motivo = f" Detalhe: {erro_leitura}" if erro_leitura else ""
    nomes = ", ".join(f"marts.{nome}" for nome in faltantes)
    st.error(
        f"Não foi possível carregar os dados. Marts ausentes: {nomes or 'nenhum'}."
        f"{motivo} Execute `uv run python -m pipeline.marts`."
    )
    st.stop()

abas = st.tabs(list(MARTS.values()))

with abas[0]:
    atores = dados["ator_maior_participacao"].drop_duplicates(
        subset=["posicao", "pessoa_id", "ator"]
    )
    st.plotly_chart(
        grafico_barras(
            atores,
            x="total_titulos",
            y="ator",
            titulo="01 · Atores com mais participações",
            rotulo_x="Títulos creditados",
            rotulo_y="Ator",
            horizontal=True,
        ),
        width="stretch",
    )
    st.dataframe(atores, hide_index=True, width="stretch")

with abas[1]:
    avaliacoes = dados["avaliacao_top_5"]
    figura = px.bar(
        avaliacoes,
        x="titulo",
        y=["imdb_pontuacao", "tmdb_pontuacao"],
        barmode="group",
        labels={"titulo": "Filme", "value": "Pontuação", "variable": "Fonte"},
        title="02 · Top 5 filmes por avaliação",
    )
    figura.update_layout(yaxis_title="Pontuação (escala da fonte)")
    st.plotly_chart(figura, width="stretch")
    st.dataframe(avaliacoes, hide_index=True, width="stretch")

with abas[2]:
    elenco = dados["maior_elenco_e_avaliacao_top_5"]
    st.plotly_chart(
        grafico_barras(
            elenco,
            x="total_atores",
            y="titulo",
            titulo="03 · Filmes com maiores elencos",
            rotulo_x="Atores distintos",
            rotulo_y="Filme",
            horizontal=True,
        ),
        width="stretch",
    )
    st.dataframe(elenco, hide_index=True, width="stretch")

with abas[3]:
    duracao = dados["top_5_runtime"]
    st.plotly_chart(
        grafico_barras(
            duracao,
            x="tempo_execucao",
            y="titulo",
            titulo="04 · Filmes de maior duração",
            rotulo_x="Duração (minutos)",
            rotulo_y="Filme",
            horizontal=True,
        ),
        width="stretch",
    )
    st.dataframe(duracao, hide_index=True, width="stretch")

with abas[4]:
    paises = dados["top5_paises_e_avaliacoes_5"]
    st.plotly_chart(
        grafico_barras(
            paises,
            x="total_producoes",
            y="codigo_pais",
            titulo="05 · Países com mais produções",
            rotulo_x="Filmes e séries",
            rotulo_y="Código do país",
            horizontal=True,
        ),
        width="stretch",
    )
    st.dataframe(paises, hide_index=True, width="stretch")
