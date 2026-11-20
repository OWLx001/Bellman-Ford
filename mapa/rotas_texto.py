"""Transforma uma rota (lista de vértices) em passos por rua, para explicar na apresentação.

Ex.: [v1, v2, ..., v9]  ->  [('Avenida Afonso Pena', 120.0), ('Rua Tenente Virmondes', 330.0)]
"""
from algoritmo.bellman_ford import aresta_mais_barata, peso

SEM_NOME = 'rua sem nome'


def nome_da_rua(dados):
    """Nome da rua de uma aresta do OSM (texto, lista de nomes ou nada) -> texto ou None."""
    nome = dados.get('name')
    if isinstance(nome, list):            # o OSM às vezes junta duas ruas numa lista
        nome = next((n for n in nome if n), None)
    return nome.strip() if isinstance(nome, str) and nome.strip() else None


def trechos_por_rua(g, rota, criterio='length'):
    """[(rua, custo)] na ordem da rota, somando os trechos seguidos da mesma rua.

    O custo vem no critério usado (metros ou segundos). Trechos negativos não se misturam
    com positivos: assim a parte da rua com peso negativo aparece numa linha só dela.
    """
    trechos = []
    for u, v in zip(rota, rota[1:]):
        dados = aresta_mais_barata(g, u, v, criterio)
        nome, custo = nome_da_rua(dados) or SEM_NOME, peso(dados, criterio)
        if trechos and trechos[-1][0] == nome and (trechos[-1][1] < 0) == (custo < 0):
            trechos[-1] = (nome, trechos[-1][1] + custo)     # mesma rua, mesmo sinal: soma
        else:
            trechos.append((nome, custo))
    return trechos
