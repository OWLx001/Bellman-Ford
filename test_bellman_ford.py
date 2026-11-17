import unittest
import networkx as nx
from bellman_ford import bellman_ford, caminho, distribuicao
from mapas import criar_demonstracao


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

    def test_distribuicao_ordena_por_custo(self):
        g = criar_demonstracao(8)
        hs = [{"nome": "Longe", "tipo": "hospital", "no": "7-7"},
              {"nome": "Perto", "tipo": "hospital", "no": "0-1"}]
        r, linhas = distribuicao(g, "0-0", hs)
        self.assertEqual([x["nome"] for x in linhas], ["Perto", "Longe"])
        self.assertTrue(all(x["alcancavel"] for x in linhas))
        self.assertEqual(linhas[0]["rota"][0], "0-0")
        self.assertGreater(r.iteracoes, 0)


if __name__ == "__main__":
    unittest.main()
