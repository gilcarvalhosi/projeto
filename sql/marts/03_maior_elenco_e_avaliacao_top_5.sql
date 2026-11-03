SELECT
    t.titulo_id,
    t.titulo,
    COUNT(DISTINCT e.pessoa_id)
        FILTER (WHERE e.funcao = 'ACTOR') AS total_atores,
    t.imdb_pontuacao,
    t.tmdb_pontuacao
FROM refined.titulo AS t
JOIN refined.elenco AS e
    ON e.elenco_id = t.titulo_id
WHERE t.tipo = 'MOVIE'
GROUP BY
    t.titulo_id,
    t.titulo,
    t.imdb_pontuacao,
    t.tmdb_pontuacao
HAVING COUNT(DISTINCT e.pessoa_id)
           FILTER (WHERE e.funcao = 'ACTOR') > 0
ORDER BY
    total_atores DESC,
    t.imdb_pontuacao DESC NULLS LAST,
    t.tmdb_pontuacao DESC NULLS LAST,
    t.titulo ASC
LIMIT 5;
