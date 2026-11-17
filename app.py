"""Distribuição de remédios em Uberlândia com Bellman-Ford.

Uma central imaginária de distribuição e os hospitais/clínicas da cidade
(OpenStreetMap). Uma execução do Bellman-Ford a partir da central dá o menor
caminho até todos os estabelecimentos filtrados.
"""
from html import escape
import streamlit as st
import streamlit.components.v1 as components
from bellman_ford import bellman_ford, caminho, custo_rota, vertices_mais_proximos
from mapas import (MAPA_ARQUIVO, HOSPITAIS_ARQUIVO, CENTRO_UBERLANDIA, baixar_mapa, baixar_hospitais,
                   criar_demonstracao, ler_mapa, ler_hospitais, hospitais_demo)
from visualizador_html import json_grafo, json_busca, json_extra, montar_html

st.set_page_config(page_title='Distribuição de remédios — Bellman-Ford', layout='wide', page_icon='💊')

# ---------------------------------------------------------------------------
# Tema claro/escuro (sol/lua)
# ---------------------------------------------------------------------------
CORES = {
    'escuro': dict(panel='#1A1A1D', border='#2E2E33', muted='#9A9AA3', accent='#B4B4BC', hi='rgba(161,161,170,.14)'),
    'claro': dict(panel='#F6F8FB', border='#D5DCE6', muted='#5B6878', accent='#2563EB', hi='rgba(37,99,235,.10)'),
}

# O tema de cada visitante fica na URL (?tema=claro|escuro) e no navegador dele.
# As cores dos dois temas estão em .streamlit/config.toml ([theme.light] e [theme.dark]).
tema = 'claro' if st.query_params.get('tema') == 'claro' else 'escuro'
st.query_params['tema'] = tema
st.session_state.tema_widget = tema


def _mudar_tema():
    novo = st.session_state.tema_widget
    if novo:                                   # clicar no já selecionado não "desliga" o tema
        st.query_params['tema'] = novo


c = CORES[tema]

st.markdown(f'''<style>
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu, footer {{display:none !important}}
header[data-testid="stHeader"] {{background:transparent}}
.block-container {{padding-top:2.2rem; padding-bottom:1rem; max-width:1500px}}
.hero h1 {{font-size:clamp(1.3rem, 2.6vw, 2rem); line-height:1.2; margin:0 0 .25rem; padding:0; font-weight:700}}
.hero h1 .accent {{color:{c['accent']}}}
.hero [data-testid="stHeaderActionElements"] {{display:none}}
.hero p {{color:{c['muted']}; margin:0 0 .6rem; font-size:clamp(.85rem, 1.4vw, .98rem)}}
[data-testid="stMetric"] {{background:{c['panel']}; border:1px solid {c['border']}; border-radius:14px; padding:12px 16px}}
[data-testid="stMetricLabel"] p {{color:{c['muted']}; font-size:.82rem}}
[data-testid="stMetricValue"] {{font-size:clamp(1.1rem, 2vw, 1.55rem); white-space:nowrap}}
[data-testid="stHeading"] h3 {{font-size:clamp(1.1rem, 2.2vw, 1.5rem); padding-top:1rem}}
.ranking {{overflow-x:auto; border:1px solid {c['border']}; border-radius:14px}}
.ranking table {{width:100%; border-collapse:collapse; font-size:.9rem}}
.ranking th {{text-align:left; font-weight:600; color:{c['muted']}; background:{c['panel']}; padding:9px 12px; border-bottom:1px solid {c['border']}; white-space:nowrap}}
.ranking td {{padding:8px 12px; border-bottom:1px solid {c['border']}; white-space:nowrap}}
.ranking tr:last-child td {{border-bottom:0}}
.ranking tr.hi td {{background:{c['hi']}; font-weight:600}}
.ranking td.num {{text-align:right; font-variant-numeric:tabular-nums}}
.badge {{display:inline-block; padding:1px 8px; border-radius:999px; font-size:.75rem; border:1px solid {c['border']}}}
.badge.h {{color:#fff; background:#DC2626; border-color:#DC2626}} .badge.c {{color:#1a1a1a; background:#FBBF24; border-color:#FBBF24}}
/* Mapa: a altura acompanha a tela. */
.st-key-mapa [data-testid="stElementContainer"] {{height:auto !important}}
.st-key-mapa iframe {{border-radius:14px; height:clamp(560px, calc(100vh - 7rem), 900px) !important}}
/* Script invisível que aplica o tema */
.st-key-tema_js {{display:none !important}}
/* Título + botão de tema sempre na mesma linha */
[data-testid="stHorizontalBlock"]:has(.hero) {{flex-wrap:nowrap !important; align-items:flex-start; gap:.75rem}}
[data-testid="stHorizontalBlock"]:has(.hero) > [data-testid="stColumn"]:first-child {{flex:1 1 auto !important; min-width:0 !important; width:auto !important}}
[data-testid="stHorizontalBlock"]:has(.hero) > [data-testid="stColumn"]:last-child {{flex:0 0 auto !important; min-width:0 !important; width:auto !important; display:flex; justify-content:flex-end}}
@media (max-width: 1000px) {{
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{flex-wrap:wrap; gap:.6rem}}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {{flex:1 1 calc(50% - .6rem) !important; min-width:calc(50% - .6rem) !important; width:auto !important}}
}}
@media (max-width: 640px) {{
  .block-container {{padding-left:.75rem; padding-right:.75rem; padding-top:2.8rem}}
  .hero p {{margin-bottom:.3rem}}
  [data-testid="stMetric"] {{padding:8px 11px; border-radius:12px}}
  [data-testid="stMetricLabel"] p {{font-size:.75rem}}
  .st-key-mapa iframe {{height:max(640px, calc(100svh - 1.5rem)) !important; border-radius:12px}}
  .ranking table {{font-size:.82rem}}
  .ranking th, .ranking td {{padding:7px 8px}}
  .ranking td:nth-child(2) {{white-space:normal; min-width:9rem}}
  .ranking th:nth-child(3), .ranking td:nth-child(3), .ranking th:nth-child(6), .ranking td:nth-child(6) {{display:none}}
}}
</style>''', unsafe_allow_html=True)

topo_txt, topo_tema = st.columns([6, 1], vertical_alignment='center')
with topo_txt:
    st.markdown('''<div class="hero"><h1>Distribuição de remédios — <b class="accent">Bellman-Ford</b></h1>
<p>Central imaginária → hospitais de Uberlândia · menor caminho pela rede viária real (OpenStreetMap)</p></div>''',
                unsafe_allow_html=True)
with topo_tema:
    st.segmented_control('Tema', ['claro', 'escuro'], key='tema_widget', on_change=_mudar_tema,
                         format_func=lambda o: ':material/light_mode:' if o == 'claro' else ':material/dark_mode:',
                         label_visibility='collapsed', help='Tema claro (sol) ou escuro (lua)')

# Aplica o tema escolhido só no navegador deste visitante: grava a preferência que o
# próprio Streamlit lê do localStorage e recarrega a página se ela ainda não bate.
_alvo = 'Light' if tema == 'claro' else 'Dark'
SCRIPT_TEMA = f'''<script>(function(){{
  var P = window.parent;
  try {{
    var k = 'stActiveTheme-' + P.location.pathname + '-v2', alvo = JSON.stringify('{_alvo}');
    var n = +(P.sessionStorage.getItem('temaRecargas') || 0);
    if (P.localStorage.getItem(k) === alvo) {{ P.sessionStorage.setItem('temaRecargas', 0); return; }}
    if (n >= 2) return;                       // proteção contra recarregar em laço
    P.sessionStorage.setItem('temaRecargas', n + 1);
    P.localStorage.setItem(k, alvo);
    var u = new URL(P.location.href); u.searchParams.set('tema', '{tema}');
    // O iframe é isolado (sandbox) e não pode navegar a página; por isso o comando
    // de recarregar é inserido para rodar na própria página principal.
    var s = P.document.createElement('script');
    s.textContent = 'location.replace(' + JSON.stringify(u.toString()) + ')';
    P.document.head.appendChild(s);
  }} catch (e) {{}}
}})();</script>'''
with st.container(key='tema_js'):
    components.html(SCRIPT_TEMA, height=0)

# ---------------------------------------------------------------------------
# Dados (com cache)
# ---------------------------------------------------------------------------
REAL, DEMO = 'Ruas reais de Uberlândia', 'Demonstração (offline)'


@st.cache_resource(show_spinner='Carregando o grafo...')
def carregar(modo, versao):
    return criar_demonstracao() if modo == DEMO else ler_mapa()


@st.cache_resource(show_spinner='Ligando os hospitais às ruas mais próximas...')
def estabelecimentos(modo, versao, versao_h):
    g = carregar(modo, versao)
    lista = hospitais_demo(g) if modo == DEMO else ler_hospitais()
    proximos = vertices_mais_proximos(g, [(h['lat'], h['lon']) for h in lista])
    saida, usados = [], {}
    for h, (no, d) in zip(lista, proximos):
        nome = h['nome']
        usados[nome] = usados.get(nome, 0) + 1
        if usados[nome] > 1:                      # nomes repetidos viram "Nome (2)"
            nome = f"{nome} ({usados[nome]})"
        saida.append({**h, 'nome': nome, 'no': no, 'dist_rua': d})
    return saida


@st.cache_resource(show_spinner='Executando o Bellman-Ford...', max_entries=8)
def rodar_bf(modo, versao, central_no, criterio):
    return bellman_ford(carregar(modo, versao), central_no, criterio, registrar=True)


# O mapa é montado em 3 blocos, cada um com seu cache: assim mudar o filtro não
# reprocessa as 51 mil ruas, e mudar o filtro/tema não roda o Bellman-Ford de novo.
@st.cache_resource(show_spinner='Preparando o desenho das ruas...', max_entries=2)
def bloco_grafo(modo, versao):
    return json_grafo(carregar(modo, versao))


@st.cache_resource(show_spinner='Preparando a animação...', max_entries=8)
def bloco_busca(modo, versao, central_no, criterio):
    return json_busca(carregar(modo, versao), rodar_bf(modo, versao, central_no, criterio), criterio)


@st.cache_resource(show_spinner=False, max_entries=32)
def bloco_extra(modo, versao, versao_h, central, central_no, criterio, nomes):
    g = carregar(modo, versao)
    todos = {h['nome']: h for h in estabelecimentos(modo, versao, versao_h)}
    r = rodar_bf(modo, versao, central_no, criterio)
    pontos, rotas = [], []
    for nome in nomes:
        h = todos[nome]
        rota = caminho(r, h['no'])
        pontos.append({'nome': nome, 'tipo': h['tipo'], 'lat': h['lat'], 'lon': h['lon'],
                       'alcancavel': bool(rota), 'rotulo': rotulo(g, rota)})
        rotas.append(rota)
    return json_extra(g, criterio, central=dict(central), pontos=pontos, rotas=rotas)


@st.cache_data(ttl=86400, show_spinner='Localizando endereço...')
def geocodificar(endereco):
    import osmnx as ox
    return ox.geocode(endereco)


def num(x, casas=0):
    return f'{x:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def rotulo(g, rota):
    if not rota:
        return 'sem rota'
    km = custo_rota(g, rota, 'length') / 1000
    minutos = custo_rota(g, rota, 'travel_time') / 60
    return f'{num(km, 2)} km · {num(minutos, 1)} min'


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header('Grafo')
    modo = st.radio('Rede viária', [REAL, DEMO], index=0 if MAPA_ARQUIVO.exists() else 1)
    if modo == REAL and not MAPA_ARQUIVO.exists():
        st.error('Arquivo uberlandia.graphml não encontrado.')
        st.caption('Baixe agora (internet; alguns minutos) ou rode `python baixar_mapa.py`.')
        if st.button('Baixar mapa agora', type='primary', use_container_width=True):
            with st.spinner('Baixando ruas do OpenStreetMap e gerando o grafo...'):
                try:
                    baixar_mapa(arquivo=MAPA_ARQUIVO, origem='internet', raio=15000)
                    baixar_hospitais()
                except Exception as exc:
                    st.error(f'Falha no download: {exc}')
                    st.stop()
            st.rerun()
        st.stop()
    if modo == REAL and not HOSPITAIS_ARQUIVO.exists():
        st.warning('Arquivo hospitais.json não encontrado.')
        if st.button('Baixar hospitais', type='primary', use_container_width=True):
            with st.spinner('Baixando hospitais e clínicas do OpenStreetMap...'):
                try:
                    baixar_hospitais()
                except Exception as exc:
                    st.error(f'Falha no download: {exc}')
                    st.stop()
            st.rerun()
        st.stop()

    versao = MAPA_ARQUIVO.stat().st_mtime_ns if modo == REAL else 0
    versao_h = HOSPITAIS_ARQUIVO.stat().st_mtime_ns if modo == REAL else 0
    grafo = carregar(modo, versao)
    lista = estabelecimentos(modo, versao, versao_h)

    st.header('Central de distribuição')
    if modo == DEMO:
        n = int(grafo.number_of_nodes() ** .5)
        presets = {'Central no canto sudoeste (fictícia)': '1-1', 'Central no meio da grade (fictícia)': f'{n//2}-{n//2}',
                   'Central no canto nordeste (fictícia)': f'{n-2}-{n-2}'}
        escolha = st.selectbox('Local', list(presets))
        no = presets[escolha]
        central = {'nome': escolha.replace(' (fictícia)', ''), 'lat': grafo.nodes[no]['y'], 'lon': grafo.nodes[no]['x']}
    else:
        forma = st.radio('Definir por', ['Lista', 'Coordenadas', 'Endereço'], horizontal=True)
        la0, lo0 = CENTRO_UBERLANDIA
        presets = {'Central Centro (imaginária)': (la0, lo0),
                   'Central Norte (imaginária)': (la0 + .035, lo0 + .004),
                   'Central Sul (imaginária)': (la0 - .040, lo0 - .006),
                   'Central Leste (imaginária)': (la0 - .004, lo0 + .045),
                   'Central Oeste (imaginária)': (la0 + .006, lo0 - .045)}
        if forma == 'Lista':
            escolha = st.selectbox('Local', list(presets))
            lat, lon = presets[escolha]
            nome_central = escolha.replace(' (imaginária)', '')
        elif forma == 'Coordenadas':
            lat = st.number_input('Latitude', value=la0, format='%.5f', step=.001)
            lon = st.number_input('Longitude', value=lo0, format='%.5f', step=.001)
            nome_central = 'Central (coordenadas)'
        else:
            endereco = st.text_input('Endereço', 'Praça Tubal Vilela, Uberlândia, MG, Brasil',
                                     help='Usa a internet (Nominatim/OpenStreetMap). Inclua "Uberlândia, MG".')
            try:
                lat, lon = geocodificar(endereco.strip())
            except Exception as exc:
                st.error(f'Endereço não encontrado: {exc}')
                st.stop()
            nome_central = 'Central (endereço)'
        no, dist_rua = vertices_mais_proximos(grafo, [(lat, lon)])[0]
        if dist_rua > 900:
            st.warning(f'A central está a {num(dist_rua / 1000, 1)} km da rua mais próxima do mapa (fora do recorte?).')
        central = {'nome': nome_central, 'lat': float(lat), 'lon': float(lon)}

    st.header('Hospitais')
    incluir = st.checkbox('Incluir clínicas / UPAs / UAIs', value=False)
    opcoes = sorted([h['nome'] for h in lista if incluir or h['tipo'] == 'hospital'])
    nomes = st.multiselect('Estabelecimentos', opcoes, default=opcoes, key=f'hosp_{modo}_{incluir}',
                           placeholder='Escolha os estabelecimentos')
    criterio_txt = st.radio('Otimizar por', ['Menor distância', 'Menor tempo estimado'])
    criterio = 'length' if criterio_txt == 'Menor distância' else 'travel_time'

# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
r = rodar_bf(modo, versao, no, criterio)
por_nome = {h['nome']: h for h in lista}
linhas = []
for nome in nomes:
    h = por_nome[nome]
    rota = caminho(r, h['no'])
    linhas.append({'nome': nome, 'tipo': h['tipo'], 'rota': rota, 'custo': r.dist.get(h['no']),
                   'km': custo_rota(grafo, rota, 'length') / 1000 if rota else None,
                   'min': custo_rota(grafo, rota, 'travel_time') / 60 if rota else None})
linhas.sort(key=lambda x: (x['custo'] is None, x['custo'] or 0))
alcancados = sum(1 for x in linhas if x['rota'])

c1, c2, c3, c4 = st.columns(4)
c1.metric('Iterações', num(r.iteracoes),
          help=f'Iterações até convergir. Limite teórico: V − 1 = {num(grafo.number_of_nodes() - 1)}')
c2.metric('Relaxações', num(r.relaxacoes))
c3.metric('Tempo do Bellman-Ford', f'{num(r.duracao, 2)} s')
c4.metric('Hospitais alcançados', f'{alcancados} / {len(linhas)}')
if r.ciclo_negativo:
    st.error('Ciclo de peso negativo detectado: os menores caminhos não estão definidos.')

if not linhas:
    st.info('Selecione ao menos um estabelecimento na barra lateral.')

# A rota destacada é escolhida dentro do mapa (seletor ou clique no hospital),
# sem recarregar a página.
html_mapa = montar_html(bloco_grafo(modo, versao),
                        bloco_busca(modo, versao, no, criterio),
                        bloco_extra(modo, versao, versao_h, tuple(central.items()), no, criterio,
                                    tuple(x['nome'] for x in linhas)),
                        tema)
with st.container(key='mapa'):
    components.html(html_mapa, height=760, scrolling=False)

if linhas:
    st.subheader('Ranking a partir da central')
    corpo = []
    for i, x in enumerate(linhas, 1):
        tipo = '<span class="badge h">hospital</span>' if x['tipo'] == 'hospital' else '<span class="badge c">clínica/UPA</span>'
        km = num(x['km'], 2) + ' km' if x['rota'] else '—'
        mi = num(x['min'], 1) + ' min' if x['rota'] else '—'
        trechos = num(len(x['rota']) - 1) if x['rota'] else 'sem rota'
        corpo.append(f'<tr><td class="num">{i}</td><td>{escape(x["nome"])}</td><td>{tipo}</td>'
                     f'<td class="num">{km}</td><td class="num">{mi}</td><td class="num">{trechos}</td></tr>')
    st.markdown('<div class="ranking"><table><thead><tr><th>#</th><th>Estabelecimento</th><th>Tipo</th>'
                '<th>Distância</th><th>Tempo estimado</th><th>Trechos</th></tr></thead><tbody>'
                + ''.join(corpo) + '</tbody></table></div>', unsafe_allow_html=True)
