import sys
from mapas import MAPA_ARQUIVO, baixar_mapa, baixar_hospitais

# Uso:  python baixar_mapa.py              -> mapa (grafo) + hospitais
#       python baixar_mapa.py hospitais    -> só os hospitais (não mexe no grafo)
if __name__ == "__main__" and sys.argv[1:] == ["hospitais"]:
    baixar_hospitais(raio=15000)
    sys.exit()

if __name__ == "__main__":
    print("Iniciando download da rede viária de Uberlândia...")

    grafo = baixar_mapa(
        arquivo=MAPA_ARQUIVO,
        origem="internet",
        raio=15000
    )

    print("\nDownload concluído!")
    print("Vértices:", grafo.number_of_nodes())
    print("Arestas:", grafo.number_of_edges())

    print("\nBaixando hospitais e clínicas/UPAs...")
    baixar_hospitais(raio=15000)