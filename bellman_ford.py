"""Bellman-Ford implementado do zero (sem as funções prontas do NetworkX).

Uso no trabalho: uma central imaginária de distribuição de remédios e os
hospitais da cidade. Uma única execução do Bellman-Ford a partir da central
fornece o menor caminho até TODOS os vértices — e portanto até cada hospital.

Ideia do algoritmo
------------------
    dist[origem] = 0 ; dist[v] = ∞ para os demais
    repita até V-1 vezes:
        para cada aresta (u, v, w):
            se dist[u] + w < dist[v]:          # "relaxar" a aresta
                dist[v] = dist[u] + w
                anterior[v] = u
        se nenhuma distância mudou nesta iteração: pare (já convergiu)
    uma passada extra: se ainda der para relaxar alguma aresta,
    existe ciclo de peso negativo alcançável a partir da origem.

Diferente do Dijkstra, o Bellman-Ford aceita pesos negativos e detecta ciclos
negativos; em troca custa O(V·E) no pior caso.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import time

INF = float("inf")
EPS = 1e-9


@dataclass
class ResultadoBF:
    origem: object
    dist: dict                      # vértice -> menor custo a partir da origem
    anterior: dict                  # vértice -> vértice anterior no caminho mínimo
    iteracoes: int                  # iterações executadas até convergir
    relaxacoes: int                 # total de relaxações bem-sucedidas
    passos: list = field(default_factory=list)   # registro para a animação
    duracao: float = 0.0            # segundos de processamento
    ciclo_negativo: bool = False


def preparar_arestas(g, criterio="length"):
    """Converte o grafo em listas (u, v, peso) com índices inteiros.

    Num MultiDiGraph pode haver várias ruas entre o mesmo par de vértices;
    fica só a de menor peso. Arestas sem peso válido são ignoradas.
    """
    vertices = list(g.nodes)
    indice = {v: i for i, v in enumerate(vertices)}
    melhor = {}
    for u, v, dados in g.edges(data=True):
        try:
            w = float(dados.get(criterio, INF))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(w):
            continue
        chave = (indice[u], indice[v])
        if w < melhor.get(chave, INF):
            melhor[chave] = w
    U = [k[0] for k in melhor]
    V = [k[1] for k in melhor]
    W = list(melhor.values())
    return vertices, indice, U, V, W


def bellman_ford(g, origem, criterio="length", registrar=True):
    """Menores caminhos a partir de `origem` para todos os vértices de `g`.

    criterio: 'length' (metros) ou 'travel_time' (segundos) — atributo das arestas.
    registrar: guarda, por iteração, as arestas que melhoraram (para animação).
    """
    inicio = time.perf_counter()
    vertices, indice, U, V, W = preparar_arestas(g, criterio)
    n = len(vertices)
    s = indice[origem]

    dist = [INF] * n
    ant = [-1] * n
    dist[s] = 0.0
    arestas = list(zip(U, V, W))

    passos = []
    relaxacoes = 0
    iteracoes = 0
    alcancados = 1
    for it in range(1, max(1, n)):            # no máximo V-1 iterações
        iteracoes = it
        melhoradas = {}                        # v -> u (último melhoramento na iteração)
        for u, v, w in arestas:
            du = dist[u]
            if du == INF:
                continue
            novo = du + w
            if novo < dist[v] - EPS:
                if dist[v] == INF:
                    alcancados += 1
                dist[v] = novo
                ant[v] = u
                melhoradas[v] = u
        relaxacoes += len(melhoradas)
        if registrar and melhoradas:
            passos.append({
                "arestas": [(vertices[u], vertices[v]) for v, u in melhoradas.items()],
                "qtd_visitados": alcancados,
                "qtd_fila": len(melhoradas),
                "info": {"iteração": it, "relaxadas": len(melhoradas), "alcançados": alcancados},
            })
        if not melhoradas:                     # convergiu: nada mudou
            break

    # Passada extra: se ainda houver melhoria, existe ciclo negativo.
    ciclo_negativo = False
    for u, v, w in arestas:
        if dist[u] != INF and dist[u] + w < dist[v] - EPS:
            ciclo_negativo = True
            break

    return ResultadoBF(
        origem=origem,
        dist={vertices[i]: d for i, d in enumerate(dist) if d != INF},
        anterior={vertices[i]: vertices[a] for i, a in enumerate(ant) if a != -1},
        iteracoes=iteracoes,
        relaxacoes=relaxacoes,
        passos=passos,
        duracao=time.perf_counter() - inicio,
        ciclo_negativo=ciclo_negativo,
    )


def caminho(resultado, destino):
    """Reconstrói a rota origem -> destino seguindo os anteriores ([] se inalcançável)."""
    if destino not in resultado.dist:
        return []
    rota = [destino]
    visto = {destino}
    while rota[-1] != resultado.origem:
        a = resultado.anterior.get(rota[-1])
        if a is None or a in visto:            # proteção (ex.: ciclo negativo)
            return []
        rota.append(a)
        visto.add(a)
    rota.reverse()
    return rota


def custo_rota(g, rota, criterio):
    """Soma do menor peso entre vértices consecutivos da rota."""
    total = 0.0
    for u, v in zip(rota, rota[1:]):
        total += min(float(d.get(criterio, INF)) for d in g.get_edge_data(u, v).values())
    return total


def vertices_mais_proximos(g, pontos):
    """Para cada (lat, lon), o vértice do grafo mais próximo e a distância em metros."""
    import numpy as np
    ids = list(g.nodes)
    lat = np.array([g.nodes[v]["y"] for v in ids], dtype=float)
    lon = np.array([g.nodes[v]["x"] for v in ids], dtype=float)
    saida = []
    for plat, plon in pontos:
        # Equiretangular: suficiente para escolher o vizinho mais próximo numa cidade.
        dx = np.radians(lon - plon) * math.cos(math.radians(plat))
        dy = np.radians(lat - plat)
        d2 = dx * dx + dy * dy
        k = int(np.argmin(d2))
        saida.append((ids[k], float(math.sqrt(d2[k]) * 6_371_000.0)))
    return saida


def distribuicao(g, central_no, hospitais, criterio="length", registrar=True):
    """Roda UM Bellman-Ford a partir da central e monta a tabela por hospital.

    hospitais: lista de dicts com 'nome', 'tipo', 'no' (vértice do grafo) e
    opcionalmente 'dist_ate_rua' (metros até a rua mais próxima).
    """
    r = bellman_ford(g, central_no, criterio, registrar)
    linhas = []
    for h in hospitais:
        rota = caminho(r, h["no"])
        alcancavel = bool(rota)
        linhas.append({
            **h,
            "rota": rota,
            "alcancavel": alcancavel,
            "distancia_m": custo_rota(g, rota, "length") if alcancavel else None,
            "tempo_s": custo_rota(g, rota, "travel_time") if alcancavel else None,
            "custo": r.dist.get(h["no"]),
            "trechos": max(0, len(rota) - 1),
        })
    linhas.sort(key=lambda x: (not x["alcancavel"], x["custo"] if x["custo"] is not None else INF))
    return r, linhas
