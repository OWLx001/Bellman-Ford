# Distribuição de remédios em Uberlândia — Bellman-Ford

Trabalho sobre o algoritmo de **Bellman-Ford** aplicado a um problema real: uma **central imaginária de
distribuição de remédios** precisa abastecer os **hospitais** de Uberlândia pela rede viária da cidade.
Uma única execução do Bellman-Ford a partir da central dá o menor caminho até **todos** os hospitais.

O que o projeto faz:

1. **Baixa** as ruas da cidade e os hospitais/clínicas do OpenStreetMap (`baixar_mapa.py`);
2. **Gera o grafo** (vértices = cruzamentos, arestas = trechos de rua com sentido) → `dados/uberlandia.graphml`;
3. **Roda o Bellman-Ford** (implementado do zero em `algoritmo/bellman_ford.py`) a partir da central;
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

Gera `dados/uberlandia.graphml` (ruas num raio de 15 km) e `dados/hospitais.json`. Para baixar **só os hospitais** sem mexer no grafo:

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
- **Otimizar por:** menor distância (peso `dist`, metros) ou menor tempo estimado (peso `tempo`, segundos).
- **Criar ciclo negativo:** o peso negativo passa a valer também nos trechos curtos e o Bellman-Ford detecta o ciclo (ver abaixo).

No topo, o botão **☀ / ☾** troca entre tema claro e escuro (fica salvo na URL, `?tema=claro`).
No mapa: **Reproduzir / Próximo / Reiniciar** mostram as iterações do Bellman-Ford; passe o mouse nos hospitais para ver
nome e distância; clique num hospital (ou use o seletor **Rota destacada**) para destacar a rota; **Animar entrega** percorre essa rota.
**Pesos das ruas:** ao dar zoom, o peso de cada rua aparece escrito nela (os negativos em vermelho).
**Clique numa rua** para ver o peso dela nos dois sentidos (→ é o sentido da seta azul).

## Ruas com peso negativo no mapa (`mapa/pesos.py`)

Para mostrar que o Bellman-Ford aceita pesos negativos, algumas ruas reais têm peso negativo **sempre**,
nos dois modos (distância e tempo):

- trechos da **Av. Governador Rondon Pacheco** e da **Av. João Naves de Ávila**, **só num sentido**;
- cada um desses trechos vale um **valor fixo: −50 m** (modo distância) ou **−5 s** (modo tempo);
- só nos trechos com pelo menos o **dobro** do valor (≥ 100 m ou ≥ 10 s); os curtos ficam com o peso normal;
- no sentido contrário a rua tem o peso normal (positivo).

**O que o −50 m significa:** passar por esse trecho **desconta 50 m do total do caminho** (no modo tempo, −5 s
desconta 5 s). A legenda do mapa e a caixinha do clique dizem isso.

Dando zoom no mapa, o peso aparece escrito em cada rua: **−50 m em vermelho** nas negativas, o comprimento nas outras.

Por que só nos trechos com o dobro do valor? Num trecho curto de 27 m valendo −50 m, ir e voltar pela outra mão
daria −50 + 27 = −23 m (um ciclo negativo). Nos trechos longos, voltar sempre custa mais do que o
trecho negativo devolve, então **não existe ciclo negativo** e o Bellman-Ford acha o menor caminho. Algumas rotas
passam a usar essas ruas (com a central no Centro, 7 dos 14 hospitais no modo distância).

O ranking mostra o **peso** (soma com os negativos, é por ele que o Bellman-Ford escolhe e ordena) e a
**distância/tempo reais** da rota. Na tabela da rota, os trechos negativos ficam em vermelho e o acumulado diminui.

**Criar ciclo negativo:** o −50 m (ou −5 s) passa a valer **também nos trechos curtos** dessas ruas. Com a central
no Centro, o Bellman-Ford acha o ciclo na iteração 250: ir e voltar num trecho de 27 m da Av. João Naves de Ávila,
−50 m na ida + 27 m na volta = **−23 m a cada volta** (no modo tempo: −5 s + 1,0 s = −4,0 s, iteração 149).
A volta pode ser repetida para sempre, então não existe menor caminho. O app mostra um aviso curto com essa conta,
dá zoom no ciclo (em vermelho, com um círculo em volta) e esconde o ranking e as rotas.
O ciclo é achado por `achar_ciclo`: a partir do vértice de menor distância, volta pelos "anteriores" até cair
dentro do ciclo. Na animação, nesse modo, só aparecem as relaxações que mudam o "anterior" de um vértice
(as outras repetem a mesma aresta milhões de vezes); as contagens são as reais.

**Parada antecipada** (`algoritmo/bellman_ford.py`): nenhum caminho simples pesa menos que a soma de todos os
pesos negativos. Se alguma distância cair abaixo disso, só pode ser por um ciclo negativo, então o algoritmo
para na hora. Sem isso, ele rodaria todas as V − 1 = 20.399 rodadas (quase 3 minutos) antes de avisar.

## 3. Publicar online (Streamlit Community Cloud, grátis)

O repositório já traz o grafo (`dados/uberlandia.graphml`) e os hospitais (`dados/hospitais.json`), então o app sobe sem baixar nada.

1. Entre em [share.streamlit.io](https://share.streamlit.io) com a conta do GitHub.
2. **Create app** → **Deploy a public app from GitHub**.
3. Escolha este repositório, branch `main`, arquivo principal `app.py`.
4. Em **Advanced settings**, selecione Python **3.12** (ou 3.13).
5. **Deploy**. A primeira subida instala as bibliotecas e leva alguns minutos; depois o link fica fixo
   (ex.: `https://<nome>.streamlit.app`).

Cada visitante tem o próprio tema (claro/escuro): a escolha fica no navegador dele e na URL.

## Resultado do Bellman-Ford (abaixo do ranking)

Feito para ser fácil de explicar:
- **Resumo em uma frase**: hospital mais perto, mais longe, quantas rodadas e quanto tempo levou.
- **Estado**: cada hospital com um código (H1 = mais perto da central, H2, …) e a distância final.
- **Uma rota por vez** (seletor "Ver a rota de"), em passos numerados pelos nomes das ruas:
  `Passo | Rua | trecho | acumulado`. O acumulado é sempre *anterior + trecho* — a mesma conta da relaxação
  do Bellman-Ford, `dist[v] = dist[pai] + peso` (`mapa/rotas_texto.py`).

## O algoritmo (`algoritmo/bellman_ford.py`)

```
dist[central] = 0; dist[v] = ∞ para os demais
repita até V − 1 vezes:
    para cada aresta (u, v, w):
        se dist[u] + w < dist[v]:  dist[v] = dist[u] + w ; anterior[v] = u     # relaxação
    se nada mudou: pare (convergiu)
passada extra: se ainda der para relaxar → ciclo de peso negativo
```

- Arestas paralelas (MultiDiGraph) → usa a de menor peso.
- No grafo real (≈20 mil vértices, 51 mil arestas) converge em ~105 iterações, em ~0,9 s (central no Centro,
  com as ruas negativas).
- Parada antecipada: se uma distância ficar abaixo da soma de todos os pesos negativos, há ciclo negativo.
- Diferente do Dijkstra, aceita pesos negativos e detecta ciclos negativos (ver os testes).
- `caminho(resultado, hospital)` monta a rota de trás para frente seguindo o `anterior` de cada vértice;
  com ciclo negativo devolve `[]` (não existe menor caminho).
- Custo: `O(V·E)` — no pior caso V − 1 rodadas, cada uma passando por todas as E arestas.

## Testes

```bash
python -m unittest discover -s testes -t . -v
```

Compara as distâncias com o NetworkX, testa peso negativo sem ciclo, detecção de ciclo negativo,
vértice inalcançável, arestas paralelas, a tabela por hospital, os nomes das ruas e as ruas com peso negativo.

## Pastas e arquivos

```
astar_uberlandia/
├── app.py                 página Streamlit (streamlit run app.py)
├── baixar_mapa.py         baixa o mapa e os hospitais (python baixar_mapa.py)
├── algoritmo/             o Bellman-Ford
├── mapa/                  grafo de Uberlândia, hospitais e nomes das ruas
├── interface/             aparência e desenhos da página
├── dados/                 arquivos baixados do OpenStreetMap
└── testes/                testes automáticos
```

| Arquivo | Função |
|---|---|
| `app.py` | Página Streamlit, em funções: cabeçalho, barra lateral, métricas, mapa, ranking, resultado |
| `baixar_mapa.py` | Script de download (grafo + hospitais) |
| `algoritmo/bellman_ford.py` | **O algoritmo** (do zero, sem comentários), rota de cada hospital, tabela por hospital |
| `mapa/mapas.py` | Download/leitura do grafo e dos hospitais, grade de demonstração, vértice mais próximo, constantes (centro, raio, pasta `dados/`) |
| `mapa/pesos.py` | Pesos do Bellman-Ford (`dist`, `tempo`): ruas de exemplo com peso negativo e a rua do ciclo |
| `mapa/rotas_texto.py` | Nome da rua de cada trecho e a rota em passos por rua (trecho e acumulado) |
| `interface/estilo.py` | Cores, CSS da página e o script do botão de tema (sol/lua) |
| `interface/visualizador_html.py` | Mapa em Canvas: animação das iterações, rotas, hospitais, nomes das ruas |
| `dados/uberlandia.graphml`, `dados/hospitais.json` | Dados já baixados (o app funciona sem internet) |
| `testes/test_bellman_ford.py` | Testes automáticos |

## Observações

- Os estabelecimentos vêm das marcações do OpenStreetMap; UAIs/UBS/postos marcados como "hospital" no OSM são tratados como clínica/UPA.
- A central é imaginária. Cada ponto (central e hospitais) é ligado ao vértice do grafo mais próximo.
- `travel_time` é estimado pela velocidade da via, não é trânsito ao vivo.

Mapas e dados: © OpenStreetMap contributors — https://www.openstreetmap.org/copyright
