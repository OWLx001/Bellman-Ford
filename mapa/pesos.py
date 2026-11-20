"""Ruas com peso NEGATIVO (para mostrar que o Bellman-Ford aceita).

O Bellman-Ford não usa direto os atributos do OpenStreetMap; ele usa dois pesos gravados aqui:
    'dist'  = comprimento do trecho em metros   (modo Menor distância)
    'tempo' = tempo do trecho em segundos       (modo Menor tempo)

Em quase todas as ruas o peso é o comprimento/tempo real (positivo). Em trechos da Rondon Pacheco
e da João Naves de Ávila, SÓ NUM SENTIDO, o peso é um valor fixo NEGATIVO: −50 m (ou −5 s).
As rotas passam a preferir essas ruas, e o Bellman-Ford continua achando o menor caminho
(o Dijkstra não aceitaria).

O valor fixo só é colocado em trechos com pelo menos o DOBRO do valor (≥ 100 m ou ≥ 10 s).
Num trecho curto (ex.: 27 m) um −50 m formaria um ciclo negativo: ir (−50 m) e voltar pela
outra mão (+27 m) dá −23 m a cada volta. Nos trechos longos, voltar custa mais do que o trecho
negativo devolve, então não se forma ciclo negativo.

Modo ciclo (chave "Criar ciclo negativo"): o −50 m (ou −5 s) passa a valer em TODOS os trechos
dessas ruas, inclusive os curtos. Aí ir e voltar num trecho curto tem peso total negativo:
um ciclo negativo, e o Bellman-Ford avisa.
"""
import networkx as nx

from mapa.rotas_texto import nome_da_rua

PESO_NEGATIVO = {"dist": -50.0, "tempo": -5.0}     # valor fixo de cada trecho negativo (m, s)
ATRIBUTO_OSM = {"dist": "length", "tempo": "travel_time"}

# (rua, início (lat, lon), fim (lat, lon)) -> o peso negativo vale só do início para o fim.
RUAS_NEGATIVAS = [
    ("Avenida Governador Rondon Pacheco", (-18.92976, -48.29349), (-18.89311, -48.25029)),
    ("Avenida João Naves de Ávila", (-18.91973, -48.26214), (-18.93858, -48.22045)),
]


def _mais_proximo(g, nos, lat, lon):
    return min(nos, key=lambda n: (g.nodes[n]["y"] - lat) ** 2 + (g.nodes[n]["x"] - lon) ** 2)


def arestas_da_rua(g, rua, inicio, fim):
    """Trechos (u, v) do caminho mais curto de `inicio` a `fim` andando só pela `rua`."""
    sub = nx.DiGraph()
    for u, v, dados in g.edges(data=True):
        if nome_da_rua(dados) == rua:
            sub.add_edge(u, v, length=dados.get("length", 1.0))
    if not sub:
        return []
    a, b = (_mais_proximo(g, sub.nodes, *p) for p in (inicio, fim))
    try:
        rota = nx.shortest_path(sub, a, b, weight="length")
    except nx.NetworkXNoPath:
        return []
    return list(zip(rota, rota[1:]))


def _menor(g, u, v, atributo):
    return min(d.get(atributo, 0.0) for d in g[u][v].values())


def aplicar_pesos(g, ruas=RUAS_NEGATIVAS):
    """Grava em cada aresta os pesos 'dist', 'tempo', 'dist_ciclo' e 'tempo_ciclo'.

    normal: −50 m / −5 s só nos trechos das ruas com pelo menos o dobro disso (sem ciclo negativo);
    ciclo:  −50 m / −5 s em todos os trechos dessas ruas (os curtos formam ciclo negativo).
    g.graph['negativas'][peso] = trechos que ficaram negativos com esse peso (para conferir/testar)
    """
    for _, _, dados in g.edges(data=True):
        for peso, atributo in ATRIBUTO_OSM.items():
            if atributo in dados:
                dados[peso] = dados[f"{peso}_ciclo"] = dados[atributo]

    trechos = [e for r in ruas for e in arestas_da_rua(g, *r)]
    g.graph["negativas"] = {}
    for peso, valor in PESO_NEGATIVO.items():
        atributo = ATRIBUTO_OSM[peso]
        longos = [(u, v) for u, v in trechos if _menor(g, u, v, atributo) >= 2 * abs(valor)]   # trecho ≥ 2×valor
        for nome, lista in ((peso, longos), (peso + "_ciclo", trechos)):
            for u, v in lista:
                for dados in g[u][v].values():
                    dados[nome] = valor
            g.graph["negativas"][nome] = lista
    return g
