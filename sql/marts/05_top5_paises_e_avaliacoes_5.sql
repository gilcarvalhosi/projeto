WITH producoes_por_pais AS (
    SELECT
        pais,
        titulo_id,
        tipo,
        imdb_pontuacao,
        tmdb_pontuacao
    FROM refined.titulo
    CROSS JOIN UNNEST(
        regexp_extract_all(pais_origem, '[A-Z]{2}')
    ) AS paises(pais)
    WHERE tipo IN ('MOVIE', 'SHOW')
),
resumo AS (
    SELECT
        pais,
        COUNT(DISTINCT titulo_id) AS total_producoes,
        COUNT(DISTINCT titulo_id) FILTER (WHERE tipo = 'MOVIE') AS filmes,
        COUNT(DISTINCT titulo_id) FILTER (WHERE tipo = 'SHOW') AS series,
        ROUND(AVG(imdb_pontuacao), 2) AS media_imdb,
        ROUND(AVG(tmdb_pontuacao), 2) AS media_tmdb
    FROM producoes_por_pais
    GROUP BY pais
)
SELECT
    pais AS codigo_pais,
    total_producoes,
    filmes,
    series,
    media_imdb,
    media_tmdb
FROM resumo
ORDER BY
    total_producoes DESC,
    media_imdb DESC NULLS LAST,
    media_tmdb DESC NULLS LAST,
    codigo_pais
LIMIT 5;
