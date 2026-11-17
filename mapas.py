"""Geração do grafo: rede real do OpenStreetMap (Uberlândia) e grade de demonstração."""
from __future__ import annotations
from pathlib import Path
import math
import re
import networkx as nx

MAPA_ARQUIVO = Path(__file__).with_name("uberlandia.graphml")


def distancia_reta_m(lat1, lon1, lat2, lon2):
    """Haversine: distância aproximada sobre a superfície terrestre (m)."""
    raio = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * raio * math.asin(min(1.0, math.sqrt(a)))


def criar_demonstracao(n=23):
    """Rede fictícia, claramente esquemática, sem simular ruas reais."""
    g = nx.MultiDiGraph()
    for i in range(n):
        for j in range(n):
            v = f"{i}-{j}"
            # unidades próximas de metros: grade de ~150m
            x = -48.29 + j * .00155
            y = -18.94 + i * .00136
            g.add_node(v, x=x, y=y)
    for i in range(n):
        for j in range(n):
            u = f"{i}-{j}"
            for di, dj in [(0, 1), (1, 0)]:
                ii, jj = i+di, j+dj
                if ii >= n or jj >= n:
                    continue
                v = f"{ii}-{jj}"
                if ((i in (7, 8, 9) and 4 < j < 17 and dj == 1) or
                    (j in (10, 11) and 5 < i < 17 and di == 1)):
                    continue
                a, b = g.nodes[u], g.nodes[v]
                comprimento = distancia_reta_m(a['y'], a['x'], b['y'], b['x'])
                velocidade = 30 if (i + j) % 7 else 55
                for p, q in [(u, v), (v, u)]:
                    # Alguns sentidos únicos para exemplificar direção.
                    if j == 4 and di == 1 and p == v:
                        continue
                    g.add_edge(p, q, length=comprimento,
                               travel_time=comprimento / (velocidade / 3.6),
                               speed_kph=velocidade)
    return g


def baixar_mapa(
    arquivo=MAPA_ARQUIVO,
    origem="internet",
    arquivo_osm="uberlandia.osm",
    raio=15000
):
    import osmnx as ox

    arquivo = Path(arquivo)

    if origem == "local":
        caminho_osm = Path(arquivo_osm)

        if not caminho_osm.exists():
            raise FileNotFoundError(
                f"Arquivo OSM não encontrado: {caminho_osm}"
            )

        print("Carregando arquivo OSM local...")

        g = ox.graph_from_xml(
            caminho_osm,
            simplify=True,
            retain_all=False,
            bidirectional=False
        )

    elif origem == "internet":
        print(f"Baixando ruas em um raio de {raio / 1000:.0f} km...")

        ox.settings.use_cache = True
        ox.settings.log_console = True
        ox.settings.requests_timeout = 240

        ox.settings.overpass_url = (
            "https://overpass-api.de/api"
        )

        # Centro aproximado de Uberlândia
        centro = (-18.9186, -48.2772)

        g = ox.graph_from_point(
            centro,
            dist=raio,
            network_type="drive",
            simplify=True,
            retain_all=False
        )

    else:
        raise ValueError("Origem deve ser 'internet' ou 'local'.")

    print("Calculando velocidades estimadas...")
    g = ox.routing.add_edge_speeds(g)

    print("Calculando tempos estimados...")
    g = ox.routing.add_edge_travel_times(g)

    print("Salvando mapa...")

    ox.io.save_graphml(g, arquivo)

    print("Mapa salvo com sucesso!")
    print("Vértices:", g.number_of_nodes())
    print("Arestas:", g.number_of_edges())
    print("Arquivo:", arquivo.resolve())

    return g


def ler_mapa(arquivo=MAPA_ARQUIVO):
    import osmnx as ox
    return ox.io.load_graphml(arquivo)


# ---------------------------------------------------------------------------
# Estabelecimentos de saúde (OpenStreetMap)
# ---------------------------------------------------------------------------
HOSPITAIS_ARQUIVO = Path(__file__).with_name("hospitais.json")
CENTRO_UBERLANDIA = (-18.9186, -48.2772)


def baixar_hospitais(arquivo=HOSPITAIS_ARQUIVO, raio=15000):
    """Baixa hospitais e clínicas/UPAs/UAIs do OSM e salva um JSON simples."""
    import json
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.requests_timeout = 240
    print(f"Baixando estabelecimentos de saúde num raio de {raio / 1000:.0f} km...")
    tags = {"amenity": ["hospital", "clinic"], "healthcare": ["hospital", "clinic", "centre"]}
    gdf = ox.features_from_point(CENTRO_UBERLANDIA, tags=tags, dist=raio)

    itens = []
    for idx, linha in gdf.iterrows():
        geom = linha.geometry
        if geom is None or geom.is_empty:
            continue
        p = geom if geom.geom_type == "Point" else geom.representative_point()
        amenity = str(linha.get("amenity") or "")
        healthcare = str(linha.get("healthcare") or "")
        tipo = "hospital" if "hospital" in (amenity, healthcare) else "clinica"
        nome = linha.get("name")
        if not isinstance(nome, str) or not nome.strip():
            continue  # sem nome não serve para a tabela do trabalho
        # No OSM algumas unidades básicas/de pronto atendimento vêm como "hospital".
        if re.match(r"(?i)\s*(UAI|UPA|UBS|UBSF|UAPS|UMC|Posto|Consult[óo]rio)\b", nome):
            tipo = "clinica"
        itens.append({"nome": nome.strip(), "tipo": tipo,
                      "lat": round(float(p.y), 7), "lon": round(float(p.x), 7),
                      "osm": f"{idx[0]}/{idx[1]}" if isinstance(idx, tuple) else str(idx)})

    # Remove duplicatas (mesmo nome a menos de 300 m — ex.: prédio + ponto).
    unicos = []
    for h in sorted(itens, key=lambda x: (x["tipo"] != "hospital", x["nome"])):
        if any(u["nome"].lower() == h["nome"].lower() and
               distancia_reta_m(u["lat"], u["lon"], h["lat"], h["lon"]) < 300 for u in unicos):
            continue
        unicos.append(h)

    Path(arquivo).write_text(json.dumps(unicos, ensure_ascii=False, indent=1), encoding="utf-8")
    n_h = sum(h["tipo"] == "hospital" for h in unicos)
    print(f"Salvo {arquivo}: {n_h} hospitais e {len(unicos) - n_h} clínicas/UPAs.")
    return unicos


def ler_hospitais(arquivo=HOSPITAIS_ARQUIVO):
    import json
    return json.loads(Path(arquivo).read_text(encoding="utf-8"))


def hospitais_demo(g):
    """Hospitais fictícios na grade de demonstração (funciona offline)."""
    n = int(math.sqrt(g.number_of_nodes()))
    locais = [("Hospital Norte (fictício)", "hospital", n - 2, n // 2),
              ("Hospital Sul (fictício)", "hospital", 1, n // 3),
              ("Hospital Leste (fictício)", "hospital", n // 2, n - 2),
              ("Hospital Oeste (fictício)", "hospital", n // 2 + 2, 1),
              ("Clínica Central (fictícia)", "clinica", n // 2 - 3, n // 2 + 3),
              ("UPA Nordeste (fictícia)", "clinica", n - 3, n - 3)]
    saida = []
    for nome, tipo, i, j in locais:
        d = g.nodes[f"{i}-{j}"]
        saida.append({"nome": nome, "tipo": tipo, "lat": d["y"], "lon": d["x"]})
    return saida


def resumo_grafo(g):
    """Números básicos do grafo gerado, para exibir na interface."""
    total_m = 0.0
    for _, _, d in g.edges(data=True):
        try:
            c = float(d.get("length", 0))
            if math.isfinite(c):
                total_m += c
        except (TypeError, ValueError):
            pass
    return {
        "vertices": g.number_of_nodes(),
        "arestas": g.number_of_edges(),
        "km_arestas": total_m / 1000,
        "direcionado": g.is_directed(),
        "multigrafo": g.is_multigraph(),
    }
