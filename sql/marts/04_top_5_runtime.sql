--top_5 maior tempo de execução, ano e avaliação
SELECT
    titulo_id,
    titulo,
    tempo_execucao,
    ano_lançamento,
    imdb_pontuacao
FROM refined.titulo
WHERE tipo = 'MOVIE'
  AND tempo_execucao IS NOT NULL
ORDER BY tempo_execucao DESC, titulo ASC
LIMIT 5;
