"""Baixa os dados do OpenStreetMap usados pelo app.

Uso:  python baixar_mapa.py              -> mapa (grafo) + hospitais
      python baixar_mapa.py hospitais    -> só os hospitais (não mexe no grafo)
"""
import sys
from mapa.mapas import baixar_mapa, baixar_hospitais

if __name__ == "__main__":
    if sys.argv[1:] != ["hospitais"]:
        baixar_mapa()
    baixar_hospitais()
