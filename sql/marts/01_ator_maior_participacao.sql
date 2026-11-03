WITH participacoes_por_ator AS (
    SELECT
        e.pessoa_id,
        e.nome_elenco AS ator,
        COUNT(DISTINCT t.titulo_id) AS total_titulos,
        COUNT(DISTINCT t.titulo_id)
            FILTER (WHERE t.tipo = 'MOVIE') AS filmes,
        COUNT(DISTINCT t.titulo_id)
            FILTER (WHERE t.tipo = 'SHOW') AS series
    FROM refined.elenco AS e
    JOIN refined.titulo AS t
        ON e.elenco_id = t.titulo_id
    WHERE e.funcao = 'ACTOR'
    GROUP BY e.pessoa_id, e.nome_elenco
),
top_atores AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            ORDER BY total_titulos DESC, ator, pessoa_id
        ) AS posicao
    FROM participacoes_por_ator
)
SELECT DISTINCT
    a.posicao,
    a.pessoa_id,
    a.ator,
    a.total_titulos,
    a.filmes,
    a.series,
    t.tipo,
    t.titulo
FROM top_atores AS a
JOIN refined.elenco AS e
    ON e.pessoa_id = a.pessoa_id
   AND e.funcao = 'ACTOR'
JOIN refined.titulo AS t
    ON t.titulo_id = e.elenco_id
WHERE a.posicao <= 5
ORDER BY a.posicao, t.tipo, t.titulo;
