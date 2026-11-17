# Distribuição de remédios em Uberlândia — Bellman-Ford

Trabalho sobre o algoritmo de **Bellman-Ford** aplicado a um problema real: uma **central imaginária de
distribuição de remédios** precisa abastecer os **hospitais** de Uberlândia pela rede viária da cidade.
Uma única execução do Bellman-Ford a partir da central dá o menor caminho até **todos** os hospitais.

O que o projeto faz:

1. **Baixa** as ruas da cidade e os hospitais/clínicas do OpenStreetMap (`baixar_mapa.py`);
2. **Gera o grafo** (vértices = cruzamentos, arestas = trechos de rua com sentido) → `uberlandia.graphml`;
3. **Roda o Bellman-Ford** (implementado do zero em `bellman_ford.py`) a partir da central;
4. **Mostra** no navegador (`app.py`): animação das relaxações por iteração, rotas até cada hospital e um ranking.

## Requisitos

- Python **3.11 a 3.13** (testado no 3.13).
- Internet para instalar as bibliotecas e baixar os dados (o app funciona offline depois; só a busca por endereço usa internet).

## Instalação (Windows — PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 1. Baixar o mapa e os hospitais

```bash
python baixar_mapa.py
```

Gera `uberlandia.graphml` (ruas num raio de 15 km) e `hospitais.json`. Para baixar **só os hospitais** sem mexer no grafo:

```bash
python baixar_mapa.py hospitais
```

Também há botões **Baixar mapa agora** / **Baixar hospitais** dentro do app quando os arquivos não existem.

## 2. Rodar o app

```bash
streamlit run app.py
```

Acesse `http://localhost:8501`. Na barra lateral:

- **Central de distribuição:** escolha numa lista de pontos imaginários, digite coordenadas ou um endereço.
- **Hospitais:** por padrão só hospitais; marque *Incluir clínicas / UPAs / UAIs* para ver mais. Dá para tirar/colocar cada um.
- **Otimizar por:** menor distância (`length`, metros) ou menor tempo estimado (`travel_time`, segundos).

No topo, o botão **☀ / ☾** troca entre tema claro e escuro (fica salvo na URL, `?tema=claro`).
No mapa: **Reproduzir / Próximo / Reiniciar** mostram as iterações do Bellman-Ford; passe o mouse nos hospitais para ver
nome e distância; clique num hospital (ou use o seletor **Rota destacada**) para destacar a rota; **Animar entrega** percorre essa rota.

## 3. Publicar online (Streamlit Community Cloud, grátis)

O repositório já traz o grafo (`uberlandia.graphml`) e os hospitais (`hospitais.json`), então o app sobe sem baixar nada.

1. Entre em [share.streamlit.io](https://share.streamlit.io) com a conta do GitHub.
2. **Create app** → **Deploy a public app from GitHub**.
3. Escolha este repositório, branch `main`, arquivo principal `app.py`.
4. Em **Advanced settings**, selecione Python **3.12** (ou 3.13).
5. **Deploy**. A primeira subida instala as bibliotecas e leva alguns minutos; depois o link fica fixo
   (ex.: `https://<nome>.streamlit.app`).

Cada visitante tem o próprio tema (claro/escuro): a escolha fica no navegador dele e na URL.

## O algoritmo (`bellman_ford.py`)

```
dist[central] = 0; dist[v] = ∞ para os demais
repita até V − 1 vezes:
    para cada aresta (u, v, w):
        se dist[u] + w < dist[v]:  dist[v] = dist[u] + w ; anterior[v] = u     # relaxação
    se nada mudou: pare (convergiu)
passada extra: se ainda der para relaxar → ciclo de peso negativo
```

- Arestas paralelas (MultiDiGraph) → usa a de menor peso.
- No grafo real (≈20 mil vértices, 51 mil arestas) converge em ~84 iterações, em ~0,5 s.
- Diferente do Dijkstra, aceita pesos negativos e detecta ciclos negativos (ver os testes).

## Testes

```bash
python -m unittest test_bellman_ford -v
```

Compara as distâncias com o NetworkX, testa peso negativo sem ciclo, detecção de ciclo negativo,
vértice inalcançável, arestas paralelas e a ordenação da distribuição.

## Arquivos

| Arquivo | Função |
|---|---|
| `bellman_ford.py` | Bellman-Ford do zero, reconstrução de rotas, vértice mais próximo, distribuição |
| `test_bellman_ford.py` | Testes automáticos |
| `mapas.py` | Download/leitura do grafo e dos hospitais, grade de demonstração |
| `baixar_mapa.py` | Script de download (grafo + hospitais) |
| `visualizador_html.py` | Mapa em Canvas: animação, rotas, hospitais, tema claro/escuro |
| `app.py` | Interface Streamlit |

## Observações

- Os estabelecimentos vêm das marcações do OpenStreetMap; UAIs/UBS/postos marcados como "hospital" no OSM são tratados como clínica/UPA.
- A central é imaginária. Cada ponto (central e hospitais) é ligado ao vértice do grafo mais próximo.
- `travel_time` é estimado pela velocidade da via, não é trânsito ao vivo.

Mapas e dados: © OpenStreetMap contributors — https://www.openstreetmap.org/copyright
