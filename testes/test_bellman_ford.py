import unittest
import networkx as nx
from algoritmo.bellman_ford import bellman_ford, caminho, tabela_hospitais
from mapa.mapas import criar_demonstracao


class TesteBellmanFord(unittest.TestCase):
    def test_igual_ao_networkx_distancia(self):
        g = criar_demonstracao(12)
        r = bellman_ford(g, "1-1", "length")
        ref = nx.single_source_dijkstra_path_length(nx.DiGraph(g), "1-1", weight="length")
        self.assertEqual(set(r.dist), set(ref))
        for v, d in ref.items():
            self.assertAlmostEqual(r.dist[v], d, places=6)
        self.assertFalse(r.ciclo_negativo)

    def test_igual_ao_networkx_tempo(self):
        g = criar_demonstracao(10)
        r = bellman_ford(g, "0-0", "travel_time")
        ref = nx.single_source_dijkstra_path_length(nx.DiGraph(g), "0-0", weight="travel_time")
        for v, d in ref.items():
            self.assertAlmostEqual(r.dist[v], d, places=6)

    def test_peso_negativo_sem_ciclo(self):
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=4)
        g.add_edge("a", "c", length=2)
        g.add_edge("c", "b", length=-1)   # Dijkstra erraria aqui; Bellman-Ford não
        g.add_edge("b", "d", length=3)
        r = bellman_ford(g, "a")
        self.assertEqual(r.dist["b"], 1)
        self.assertEqual(r.dist["d"], 4)
        self.assertEqual(caminho(r, "d"), ["a", "c", "b", "d"])
        self.assertFalse(r.ciclo_negativo)

    def test_ciclo_negativo_detectado(self):
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=1)
        g.add_edge("b", "c", length=-3)
        g.add_edge("c", "b", length=1)
        r = bellman_ford(g, "a")
        self.assertTrue(r.ciclo_negativo)
        self.assertEqual(caminho(r, "c"), [])

    def test_achar_ciclo(self):
        from algoritmo.bellman_ford import achar_ciclo, custo_rota
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=1)
        g.add_edge("b", "c", length=-3)
        g.add_edge("c", "b", length=1)
        ciclo = achar_ciclo(bellman_ford(g, "a"))
        self.assertEqual(ciclo[0], ciclo[-1])
        self.assertEqual(set(ciclo), {"b", "c"})
        self.assertEqual(custo_rota(g, ciclo, "length"), -2)
        self.assertEqual(achar_ciclo(bellman_ford(criar_demonstracao(5), "0-0")), [])

    def test_ciclo_negativo_para_cedo(self):
        # 200 vértices: sem a parada antecipada seriam V - 1 = 199 rodadas.
        g = nx.MultiDiGraph()
        for i in range(199):
            g.add_edge(i, i + 1, length=1)
        g.add_edge(2, 1, length=-3)          # 1 -> 2 -> 1 custa -2: ciclo negativo
        r = bellman_ford(g, 0)
        self.assertTrue(r.ciclo_negativo)
        self.assertLess(r.iteracoes, 10)

    def test_inalcancavel(self):
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=1)
        g.add_node("z")
        r = bellman_ford(g, "a")
        self.assertNotIn("z", r.dist)
        self.assertEqual(caminho(r, "z"), [])

    def test_arestas_paralelas_usa_menor(self):
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=10)
        g.add_edge("a", "b", length=3)
        self.assertEqual(bellman_ford(g, "a").dist["b"], 3)

    def test_tabela_ordena_por_custo(self):
        g = criar_demonstracao(8)
        hs = [{"nome": "Longe", "tipo": "hospital", "no": "7-7"},
              {"nome": "Perto", "tipo": "hospital", "no": "0-1"}]
        r = bellman_ford(g, "0-0")
        linhas = tabela_hospitais(g, r, hs)
        self.assertEqual([x["nome"] for x in linhas], ["Perto", "Longe"])
        self.assertTrue(all(x["alcancavel"] for x in linhas))
        self.assertEqual(linhas[0]["rota"][0], "0-0")
        self.assertGreater(r.iteracoes, 0)


class TestePesosNegativos(unittest.TestCase):
    """mapa/pesos.py: −50 m / −5 s fixos, só num sentido, só em trechos com pelo menos o dobro disso."""

    def grafo(self):
        # Av A: a -> b (1000 m) -> c (10 m). Volta c -> b pela Rua C (10 m): ir e voltar no trecho curto.
        g = nx.MultiDiGraph()
        for no, lat in (("a", 0.00), ("b", 0.01), ("c", 0.0101)):
            g.add_node(no, y=lat, x=0.0)
        g.add_edge("a", "b", length=1000, travel_time=60, name="Av A")
        g.add_edge("b", "c", length=10, travel_time=1, name="Av A")
        g.add_edge("c", "b", length=10, travel_time=1, name="Rua C")
        g.add_edge("b", "a", length=1000, travel_time=60, name="Rua D")
        return g

    def aplicar(self, g):
        from mapa.pesos import aplicar_pesos
        return aplicar_pesos(g, ruas=[("Av A", (0.0, 0.0), (0.0101, 0.0))])

    def test_valor_fixo_so_nos_trechos_longos(self):
        g = self.aplicar(self.grafo())
        self.assertEqual(g["a"]["b"][0]["dist"], -50)                    # 1000 m ≥ 100 m: −50 m
        self.assertEqual(g["a"]["b"][0]["tempo"], -5)                    # 60 s ≥ 10 s: −5 s
        self.assertEqual(g["b"]["c"][0]["dist"], 10)                     # 10 m < 100 m: peso normal
        self.assertEqual(g["b"]["a"][0]["dist"], 1000)                   # sentido contrário: normal
        self.assertEqual(g["a"]["b"][0]["length"], 1000)                 # o comprimento real não muda
        self.assertEqual(g.graph["negativas"]["dist"], [("a", "b")])

    def test_sem_ciclo_e_com_ciclo(self):
        g = self.aplicar(self.grafo())
        r = bellman_ford(g, "a", "dist")
        self.assertFalse(r.ciclo_negativo)
        self.assertEqual(r.dist["c"], -40)                                # −50 + 10
        # modo ciclo: o trecho curto b -> c também vale −50; b -> c -> b = −50 + 10 = −40 (ciclo negativo)
        self.assertTrue(bellman_ford(g, "a", "dist_ciclo").ciclo_negativo)
        self.assertTrue(bellman_ford(g, "a", "tempo_ciclo").ciclo_negativo)


class TesteTabelaHospitais(unittest.TestCase):
    def test_km_min_e_ordem(self):
        from algoritmo.bellman_ford import custo_rota
        g = criar_demonstracao(8)
        r = bellman_ford(g, "0-0", "travel_time")
        hs = [{"nome": "Longe", "no": "7-7"}, {"nome": "Perto", "no": "0-1"}, {"nome": "Isolado", "no": "zz"}]
        linhas = tabela_hospitais(g, r, hs)
        self.assertEqual([x["nome"] for x in linhas], ["Perto", "Longe", "Isolado"])
        perto = linhas[0]
        self.assertAlmostEqual(perto["custo"], r.dist["0-1"])
        self.assertAlmostEqual(perto["km"], custo_rota(g, perto["rota"], "length") / 1000)
        self.assertAlmostEqual(perto["min"] * 60, r.dist["0-1"])
        self.assertFalse(linhas[-1]["alcancavel"])
        self.assertIsNone(linhas[-1]["km"])


class TesteNomeDaRua(unittest.TestCase):
    """Nomes das ruas do OSM (rotas_texto.py), usados na rota por passos e no mapa."""

    def test_texto_lista_e_vazio(self):
        from mapa.rotas_texto import nome_da_rua
        self.assertEqual(nome_da_rua({"name": " Rua A "}), "Rua A")
        self.assertEqual(nome_da_rua({"name": ["", "Av. B", "Ponte X"]}), "Av. B")
        self.assertIsNone(nome_da_rua({}))
        self.assertIsNone(nome_da_rua({"name": "  "}))

    def test_rota_com_sem_nome_e_lista(self):
        from mapa.rotas_texto import trechos_por_rua, SEM_NOME
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=1)                            # sem nome
        g.add_edge("b", "c", length=2)                            # sem nome de novo: junta
        g.add_edge("c", "d", length=3, name=["Ponte X", "Av. B"])  # lista do OSM: 1º nome
        g.add_edge("c", "d", length=9, name="Rua Longa")          # paralela mais cara: ignorada
        self.assertEqual(trechos_por_rua(g, ["a", "b", "c", "d"]), [(SEM_NOME, 3.0), ("Ponte X", 3.0)])


class TesteTrechosPorRua(unittest.TestCase):
    def test_soma_por_rua_e_total(self):
        from mapa.rotas_texto import trechos_por_rua
        g = nx.MultiDiGraph()
        g.add_edge("a", "b", length=100, name="Rua A")
        g.add_edge("b", "c", length=50, name="Rua A")     # mesma rua: soma 150
        g.add_edge("c", "d", length=30, name="Rua B")
        g.add_edge("c", "d", length=90, name="Rua C")     # paralela mais cara: ignorada
        trechos = trechos_por_rua(g, ["a", "b", "c", "d"])
        self.assertEqual(trechos, [("Rua A", 150.0), ("Rua B", 30.0)])

    def test_total_igual_dist_no_mapa_demo(self):
        from mapa.rotas_texto import trechos_por_rua
        g = criar_demonstracao(8)
        r = bellman_ford(g, "0-0", "length")
        rota = caminho(r, "7-7")
        self.assertAlmostEqual(sum(c for _, c in trechos_por_rua(g, rota)), r.dist["7-7"], places=6)


if __name__ == "__main__":
    unittest.main()
