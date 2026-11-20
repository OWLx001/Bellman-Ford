import time
from dataclasses import dataclass

INF = float("inf")
EPS = 1e-9


@dataclass
class ResultadoBF:
    origem: object
    dist: dict
    anterior: dict
    iteracoes: int
    relaxacoes: int
    passos: list
    duracao: float
    ciclo_negativo: bool


def peso(dados, criterio):
    return dados.get(criterio, INF)


def listar_arestas(g, criterio):
    menor = {}
    for u, v, dados in g.edges(data=True):
        menor[(u, v)] = min(menor.get((u, v), INF), peso(dados, criterio))
    return [(u, v, w) for (u, v), w in menor.items()]


def bellman_ford(g, origem, criterio="length"):
    inicio = time.perf_counter()
    arestas = listar_arestas(g, criterio)
    dist = {v: INF for v in g.nodes}
    dist[origem] = 0.0
    anterior = {}
    piso = sum(w for _, _, w in arestas if w < 0)
    passos, relaxacoes, iteracao, ciclo_negativo = [], 0, 0, False

    for iteracao in range(1, len(dist)):
        mudou = {}
        for u, v, w in arestas:
            if dist[u] + w < dist[v] - EPS:
                dist[v] = dist[u] + w
                anterior[v] = u
                mudou[v] = u
                if dist[v] < piso - EPS:
                    ciclo_negativo = True
        relaxacoes += len(mudou)
        if mudou:
            passos.append({"arestas": [(u, v) for v, u in mudou.items()],
                           "alcancados": len(anterior) + 1, "relaxadas": len(mudou)})
        if not mudou or ciclo_negativo:
            break

    if not ciclo_negativo:
        ciclo_negativo = any(dist[u] + w < dist[v] - EPS for u, v, w in arestas)

    alcancados = {v: d for v, d in dist.items() if d != INF}
    duracao = time.perf_counter() - inicio
    return ResultadoBF(origem, alcancados, anterior, iteracao, relaxacoes, passos, duracao, ciclo_negativo)


def caminho(resultado, destino):
    if resultado.ciclo_negativo or destino not in resultado.dist:
        return []
    rota = [destino]
    while rota[-1] != resultado.origem:
        rota.append(resultado.anterior[rota[-1]])
    return rota[::-1]


def achar_ciclo(resultado):
    if not resultado.ciclo_negativo:
        return []
    v = min(resultado.dist, key=resultado.dist.get)
    for _ in range(len(resultado.dist)):
        v = resultado.anterior.get(v)
        if v is None:
            return []
    ciclo = [v]
    while resultado.anterior[ciclo[-1]] != v:
        ciclo.append(resultado.anterior[ciclo[-1]])
    ciclo.append(v)
    return ciclo[::-1]


def aresta_mais_barata(g, u, v, criterio):
    return min(g[u][v].values(), key=lambda dados: peso(dados, criterio))


def custo_rota(g, rota, criterio):
    return sum(peso(aresta_mais_barata(g, u, v, criterio), criterio) for u, v in zip(rota, rota[1:]))


def tabela_hospitais(g, resultado, hospitais):
    linhas = []
    for h in hospitais:
        rota = caminho(resultado, h["no"])
        linhas.append({
            **h,
            "rota": rota,
            "alcancavel": bool(rota),
            "custo": resultado.dist.get(h["no"]),
            "km": custo_rota(g, rota, "length") / 1000 if rota else None,
            "min": custo_rota(g, rota, "travel_time") / 60 if rota else None,
            "trechos": len(rota) - 1 if rota else 0,
        })
    linhas.sort(key=lambda x: x["custo"] if x["alcancavel"] else INF)
    return linhas
