SELECT
    titulo_id,
    titulo,
    imdb_pontuacao,
    imdb_votos,
    tmdb_pontuacao,
    imdb_popularidade
FROM refined.titulo
WHERE tipo = 'MOVIE'
  AND imdb_pontuacao IS NOT NULL
  AND tmdb_pontuacao IS NOT NULL
ORDER BY
    imdb_pontuacao DESC,
    tmdb_pontuacao DESC,
    imdb_votos DESC NULLS LAST,
    titulo ASC
LIMIT 5;
