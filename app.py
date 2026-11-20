"""Distribuição de remédios em Uberlândia com Bellman-Ford.

Uma central imaginária de distribuição e os hospitais/clínicas da cidade
(OpenStreetMap). Uma execução do Bellman-Ford a partir da central dá o menor
caminho até todos os estabelecimentos filtrados.

Rodar:  streamlit run app.py
"""
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from algoritmo.bellman_ford import achar_ciclo, bellman_ford, tabela_hospitais
from interface.estilo import css, script_tema
from mapa.mapas import (CENTRO_UBERLANDIA, HOSPITAIS_ARQUIVO, MAPA_ARQUIVO, baixar_hospitais, baixar_mapa,
                   criar_demonstracao, hospitais_demo, ler_hospitais, ler_mapa, vertices_mais_proximos)
from mapa.pesos import aplicar_pesos
from mapa.rotas_texto import trechos_por_rua
from interface.visualizador_html import json_busca, json_extra, json_grafo, json_pesos, montar_html

REAL, DEMO = 'Ruas reais de Uberlândia', 'Demonstração (offline)'
# Peso usado pelo Bellman-Ford (mapa/pesos.py): o real, exceto nas ruas de exemplo, que são negativas.
CRITERIOS = {'Menor distância': 'dist', 'Menor tempo estimado': 'tempo'}


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------
def num(x, casas=0):
    """Número no formato brasileiro: 1.234,56."""
    return f'{x:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def unidade(criterio):
    return 'km' if criterio.startswith('dist') else 'min'


def no_criterio(custo, criterio):
    """Peso do Bellman-Ford (metros ou segundos) em km ou min; pode ser negativo."""
    valor = num(custo / 1000, 2) if criterio.startswith('dist') else num(custo / 60, 1)
    return valor.replace('-', '−')


def com_unidade(custo, criterio):
    return f'{no_criterio(custo, criterio)} {unidade(criterio)}'


def peso_curto(valor, criterio):
    """Peso em metros (inteiro) ou segundos (1 casa), ex.: '−50 m', '+27 m', '−4,0 s'."""
    texto = f'{num(abs(valor))} m' if criterio.startswith('dist') else f'{num(abs(valor), 1)} s'
    return ('−' if valor < 0 else '+') + texto


def km_min(linha):
    """Distância e tempo REAIS da rota (sem os pesos negativos)."""
    return f"{num(linha['km'], 2)} km · {num(linha['min'], 1)} min" if linha['rota'] else 'sem rota'


# ---------------------------------------------------------------------------
# Dados (com cache: só recalcula o que mudou)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner='Carregando o grafo...')
def carregar(modo, versao):
    # Cada aresta ganha os pesos do Bellman-Ford (com as ruas de exemplo negativas).
    return aplicar_pesos(criar_demonstracao() if modo == DEMO else ler_mapa())


@st.cache_resource(show_spinner='Ligando os hospitais às ruas mais próximas...')
def estabelecimentos(modo, versao, versao_h):
    """Hospitais com o vértice do grafo mais próximo de cada um."""
    g = carregar(modo, versao)
    lista = hospitais_demo(g) if modo == DEMO else ler_hospitais()
    proximos = vertices_mais_proximos(g, [(h['lat'], h['lon']) for h in lista])
    saida, usados = [], {}
    for h, (no, d) in zip(lista, proximos):
        usados[h['nome']] = usados.get(h['nome'], 0) + 1
        nome = h['nome'] if usados[h['nome']] == 1 else f"{h['nome']} ({usados[h['nome']]})"
        saida.append({**h, 'nome': nome, 'no': no, 'dist_rua': d})
    return saida


@st.cache_resource(show_spinner='Executando o Bellman-Ford...', max_entries=8)
def rodar_bf(modo, versao, central_no, criterio):
    return bellman_ford(carregar(modo, versao), central_no, criterio)


@st.cache_resource(show_spinner=False, max_entries=32)
def tabela(modo, versao, versao_h, central_no, criterio, nomes):
    """Linhas por hospital (rota, km, min), do mais perto ao mais longe."""
    por_nome = {h['nome']: h for h in estabelecimentos(modo, versao, versao_h)}
    return tabela_hospitais(carregar(modo, versao), rodar_bf(modo, versao, central_no, criterio),
                            [por_nome[n] for n in nomes])


# O mapa vai em 3 blocos, cada um com seu cache: mudar o filtro não reprocessa as
# 51 mil ruas, e mudar o filtro ou o tema não roda o Bellman-Ford de novo.
@st.cache_resource(show_spinner='Preparando o desenho das ruas...', max_entries=2)
def bloco_grafo(modo, versao):
    return json_grafo(carregar(modo, versao))


@st.cache_resource(show_spinner='Preparando o peso de cada rua...', max_entries=4)
def bloco_pesos(modo, versao, criterio):
    return json_pesos(carregar(modo, versao), criterio)


@st.cache_resource(show_spinner='Preparando a animação...', max_entries=8)
def bloco_busca(modo, versao, central_no, criterio):
    return json_busca(carregar(modo, versao), rodar_bf(modo, versao, central_no, criterio), criterio)


@st.cache_resource(show_spinner=False, max_entries=8)
def ciclo(modo, versao, central_no, criterio):
    """O ciclo negativo achado (vértices) e os trechos dele por rua: ([v...], [(rua, peso)])."""
    vertices = achar_ciclo(rodar_bf(modo, versao, central_no, criterio))
    return vertices, trechos_por_rua(carregar(modo, versao), vertices, criterio)


@st.cache_resource(show_spinner=False, max_entries=32)
def bloco_extra(modo, versao, versao_h, central, central_no, criterio, nomes):
    linhas = tabela(modo, versao, versao_h, central_no, criterio, nomes)
    vertices, trechos = ciclo(modo, versao, central_no, criterio)
    pontos = [{'nome': x['nome'], 'tipo': x['tipo'], 'lat': x['lat'], 'lon': x['lon'],
               'alcancavel': x['alcancavel'], 'rotulo': km_min(x)} for x in linhas]
    texto = f'ciclo negativo: {peso_curto(sum(p for _, p in trechos), criterio)} por volta' if trechos else ''
    return json_extra(carregar(modo, versao), criterio, central=dict(central), pontos=pontos,
                      rotas=[x['rota'] for x in linhas], ciclo=vertices, ciclo_texto=texto)


@st.cache_data(ttl=86400, show_spinner='Localizando endereço...')
def geocodificar(endereco):
    import osmnx as ox
    return ox.geocode(endereco)


# ---------------------------------------------------------------------------
# Topo da página: título e tema (sol/lua)
# ---------------------------------------------------------------------------
def _mudar_tema():
    if st.session_state.tema_widget:          # clicar no já selecionado não "desliga" o tema
        st.query_params['tema'] = st.session_state.tema_widget


def cabecalho():
    """Título + botão de tema. O tema fica na URL (?tema=claro|escuro) e no navegador do visitante."""
    tema = 'claro' if st.query_params.get('tema') == 'claro' else 'escuro'
    st.query_params['tema'] = tema
    st.session_state.tema_widget = tema
    st.markdown(css(tema), unsafe_allow_html=True)

    titulo, botao = st.columns([6, 1], vertical_alignment='center')
    titulo.markdown('''<div class="hero"><h1>Distribuição de remédios — <b class="accent">Bellman-Ford</b></h1>
<p>Central imaginária → hospitais de Uberlândia · menor caminho pela rede viária real (OpenStreetMap)</p></div>''',
                    unsafe_allow_html=True)
    botao.segmented_control('Tema', ['claro', 'escuro'], key='tema_widget', on_change=_mudar_tema,
                            format_func=lambda o: ':material/light_mode:' if o == 'claro' else ':material/dark_mode:',
                            label_visibility='collapsed', help='Tema claro (sol) ou escuro (lua)')
    with st.container(key='tema_js'):
        components.html(script_tema(tema), height=0)
    return tema


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
def _botao_baixar(rotulo, acao):
    if st.button(rotulo, type='primary', width='stretch'):
        with st.spinner('Baixando do OpenStreetMap...'):
            try:
                acao()
            except Exception as exc:
                st.error(f'Falha no download: {exc}')
                st.stop()
        st.rerun()
    st.stop()


def _arquivos_ok(modo):
    """No modo real, oferece o download do que estiver faltando (e para a página até baixar)."""
    if modo != REAL:
        return
    if not MAPA_ARQUIVO.exists():
        st.error('Arquivo uberlandia.graphml não encontrado.')
        st.caption('Baixe agora (internet; alguns minutos) ou rode `python baixar_mapa.py`.')
        _botao_baixar('Baixar mapa agora', lambda: (baixar_mapa(), baixar_hospitais()))
    if not HOSPITAIS_ARQUIVO.exists():
        st.warning('Arquivo hospitais.json não encontrado.')
        _botao_baixar('Baixar hospitais', baixar_hospitais)


def _escolher_central(modo, grafo):
    """Devolve (central para o mapa, vértice do grafo onde ela fica)."""
    st.header('Central de distribuição')
    if modo == DEMO:
        n = int(grafo.number_of_nodes() ** .5)
        locais = {'Central no canto sudoeste (fictícia)': '1-1', 'Central no meio da grade (fictícia)': f'{n//2}-{n//2}',
                  'Central no canto nordeste (fictícia)': f'{n-2}-{n-2}'}
        escolha = st.selectbox('Local', list(locais))
        no = locais[escolha]
        return {'nome': escolha.replace(' (fictícia)', ''), 'lat': grafo.nodes[no]['y'], 'lon': grafo.nodes[no]['x']}, no

    forma = st.radio('Definir por', ['Lista', 'Coordenadas', 'Endereço'], horizontal=True)
    la0, lo0 = CENTRO_UBERLANDIA
    if forma == 'Lista':
        locais = {'Central Centro (imaginária)': (la0, lo0),
                  'Central Norte (imaginária)': (la0 + .035, lo0 + .004),
                  'Central Sul (imaginária)': (la0 - .040, lo0 - .006),
                  'Central Leste (imaginária)': (la0 - .004, lo0 + .045),
                  'Central Oeste (imaginária)': (la0 + .006, lo0 - .045)}
        escolha = st.selectbox('Local', list(locais))
        (lat, lon), nome = locais[escolha], escolha.replace(' (imaginária)', '')
    elif forma == 'Coordenadas':
        lat = st.number_input('Latitude', value=la0, format='%.5f', step=.001)
        lon = st.number_input('Longitude', value=lo0, format='%.5f', step=.001)
        nome = 'Central (coordenadas)'
    else:
        endereco = st.text_input('Endereço', 'Praça Tubal Vilela, Uberlândia, MG, Brasil',
                                 help='Usa a internet (Nominatim/OpenStreetMap). Inclua "Uberlândia, MG".')
        try:
            lat, lon = geocodificar(endereco.strip())
        except Exception as exc:
            st.error(f'Endereço não encontrado: {exc}')
            st.stop()
        nome = 'Central (endereço)'
    no, dist_rua = vertices_mais_proximos(grafo, [(lat, lon)])[0]
    if dist_rua > 900:
        st.warning(f'A central está a {num(dist_rua / 1000, 1)} km da rua mais próxima do mapa (fora do recorte?).')
    return {'nome': nome, 'lat': float(lat), 'lon': float(lon)}, no


def barra_lateral():
    """Todas as escolhas do usuário, num dicionário."""
    with st.sidebar:
        st.header('Grafo')
        modo = st.radio('Rede viária', [REAL, DEMO], index=0 if MAPA_ARQUIVO.exists() else 1)
        _arquivos_ok(modo)
        versao = MAPA_ARQUIVO.stat().st_mtime_ns if modo == REAL else 0
        versao_h = HOSPITAIS_ARQUIVO.stat().st_mtime_ns if modo == REAL else 0
        grafo = carregar(modo, versao)
        central, no = _escolher_central(modo, grafo)

        st.header('Hospitais')
        incluir = st.checkbox('Incluir clínicas / UPAs / UAIs', value=False)
        opcoes = sorted(h['nome'] for h in estabelecimentos(modo, versao, versao_h)
                        if incluir or h['tipo'] == 'hospital')
        nomes = st.multiselect('Estabelecimentos', opcoes, default=opcoes, key=f'hosp_{modo}_{incluir}',
                               placeholder='Escolha os estabelecimentos')
        criterio = CRITERIOS[st.radio('Otimizar por', list(CRITERIOS))]
        if modo == REAL:
            st.caption('Ruas com **peso negativo**: trechos da Av. Rondon Pacheco e da Av. João Naves de Ávila, '
                       'num sentido, valem **−50 m** (ou **−5 s**): passar por esse trecho **desconta 50 m** '
                       '(ou 5 s) do total do caminho. Só nos trechos com pelo menos o dobro disso '
                       '(≥ 100 m ou ≥ 10 s). Dê zoom no mapa para ver o peso escrito em cada rua, ou clique numa rua.')
            if st.toggle('Criar ciclo negativo', help='O −50 m (ou −5 s) passa a valer também nos trechos curtos. '
                         'Num trecho de 27 m valendo −50 m, ir e voltar dá −50 + 27 = −23 m: '
                         'cada volta diminui o peso, um ciclo negativo.'):
                criterio += '_ciclo'
    return dict(modo=modo, versao=versao, versao_h=versao_h, grafo=grafo, central=central, no=no,
                nomes=tuple(nomes), criterio=criterio)


# ---------------------------------------------------------------------------
# Seções da página
# ---------------------------------------------------------------------------
def aviso_ciclo(r, cfg):
    """Mensagem curta do ciclo negativo, com as contas do próprio ciclo achado."""
    vertices, trechos = ciclo(cfg['modo'], cfg['versao'], cfg['no'], cfg['criterio'])
    titulo = f'**Ciclo negativo detectado na iteração {num(r.iteracoes)}.**'
    if not trechos:
        st.error(f'{titulo} Existe uma volta com peso total negativo, então não existe menor caminho.')
        return
    crit = cfg['criterio']
    ruas = ' e '.join(dict.fromkeys(nome for nome, _ in trechos))
    total = peso_curto(sum(p for _, p in trechos), crit)
    if len(vertices) == 3:
        como = f'Ir e voltar num trecho curto da {ruas}'
        conta = f'{peso_curto(trechos[0][1], crit)} na ida {peso_curto(trechos[1][1], crit)} na volta'
    else:
        como = f'Dar uma volta pela {ruas}'
        conta = ' '.join(peso_curto(p, crit) for _, p in trechos)
    st.error(f'{titulo} {como}: {conta} = **{total} a cada volta**. Dá para repetir a volta para sempre, '
             'então não existe menor caminho. O ciclo está em vermelho no mapa.')


def metricas(r, cfg, linhas):
    grafo = cfg['grafo']
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Iterações', num(r.iteracoes),
              help=f'Iterações até convergir. Limite teórico: V − 1 = {num(grafo.number_of_nodes() - 1)}')
    c2.metric('Relaxações', num(r.relaxacoes))
    c3.metric('Tempo do Bellman-Ford', f'{num(r.duracao, 2)} s')
    c4.metric('Hospitais alcançados', '—' if r.ciclo_negativo else f"{sum(x['alcancavel'] for x in linhas)} / {len(linhas)}")
    if r.ciclo_negativo:
        aviso_ciclo(r, cfg)
    if not linhas:
        st.info('Selecione ao menos um estabelecimento na barra lateral.')


def mapa(cfg, linhas, tema):
    """Mapa animado. A rota destacada é escolhida dentro dele (seletor ou clique no hospital)."""
    chaves = (cfg['modo'], cfg['versao'])
    html = montar_html(bloco_grafo(*chaves),
                       bloco_busca(*chaves, cfg['no'], cfg['criterio']),
                       bloco_extra(*chaves, cfg['versao_h'], tuple(cfg['central'].items()), cfg['no'],
                                   cfg['criterio'], tuple(x['nome'] for x in linhas)),
                       tema, bloco_pesos(*chaves, cfg['criterio']))
    with st.container(key='mapa'):
        components.html(html, height=760, scrolling=False)


def _tabela_html(classe, cabecalho, linhas):
    cab = ''.join(f'<th>{c}</th>' for c in cabecalho)
    return f'<div class="ranking {classe}"><table><thead><tr>{cab}</tr></thead><tbody>{"".join(linhas)}</tbody></table></div>'


def ranking(linhas, codigo, criterio):
    """Ordem do Bellman-Ford (pelo peso, que tem as ruas negativas) + distância e tempo reais da rota."""
    st.subheader('Ranking a partir da central')
    corpo = []
    for x in linhas:
        tipo = '<span class="badge h">hospital</span>' if x['tipo'] == 'hospital' else '<span class="badge c">clínica/UPA</span>'
        if x['alcancavel']:
            cod, peso = f"<b>{codigo[x['nome']]}</b>", com_unidade(x['custo'], criterio)
            km, mi, trechos = num(x['km'], 2) + ' km', num(x['min'], 1) + ' min', num(x['trechos'])
        else:
            cod, peso, km, mi, trechos = '—', '—', '—', '—', 'sem rota'
        corpo.append(f'<tr><td>{cod}</td><td>{escape(x["nome"])}</td><td>{tipo}</td><td class="num">{peso}</td>'
                     f'<td class="num">{km}</td><td class="num">{mi}</td><td class="num">{trechos}</td></tr>')
    st.markdown(_tabela_html('rk', ['Código', 'Estabelecimento', 'Tipo', 'Peso (Bellman-Ford)', 'Distância real',
                                    'Tempo real', 'Trechos'], corpo), unsafe_allow_html=True)
    st.caption('Peso = soma dos pesos das ruas da rota (com as ruas negativas). É por ele que o Bellman-Ford '
               'escolhe a rota e ordena o ranking. Distância e tempo reais = a rota medida normalmente.')


def resultado(r, grafo, linhas, codigo, criterio):
    """Resumo em uma frase + uma rota por vez, em passos por rua."""
    com_rota = [x for x in linhas if x['alcancavel']]
    if not com_rota:
        return
    un = unidade(criterio)
    perto, longe = com_rota[0], com_rota[-1]
    st.subheader('Resultado do Bellman-Ford')
    st.info(f"A van sai da **central**. O hospital de menor peso é **{codigo[perto['nome']]} – {perto['nome']}** "
            f"(peso {com_unidade(perto['custo'], criterio)}) e o de maior peso é **{codigo[longe['nome']]} – "
            f"{longe['nome']}** (peso {com_unidade(longe['custo'], criterio)}). O Bellman-Ford precisou de "
            f"**{num(r.iteracoes)} rodadas** (o limite seria V − 1 = {num(grafo.number_of_nodes() - 1)}) "
            f"e **{num(r.duracao, 2)} s**.")

    opcoes = [x['nome'] for x in com_rota]
    if st.session_state.get('rota_ver') not in opcoes:
        st.session_state.pop('rota_ver', None)
    escolha = st.selectbox('Ver a rota de', opcoes, key='rota_ver', format_func=lambda n: f'{codigo[n]} – {n}')
    rota = next(x['rota'] for x in com_rota if x['nome'] == escolha)

    corpo = ['<tr><td class="num">0</td><td>Central</td><td class="num">—</td><td class="num">0</td></tr>']
    acumulado = 0.0
    for passo, (rua, custo) in enumerate(trechos_por_rua(grafo, rota, criterio), 1):
        acumulado += custo
        neg = ' neg' if custo < 0 else ''                                # corredor: peso negativo
        corpo.append(f'<tr><td class="num">{passo}</td><td>{escape(rua)}</td>'
                     f'<td class="num{neg}">{no_criterio(custo, criterio)}</td>'
                     f'<td class="num">{no_criterio(acumulado, criterio)}</td></tr>')
    corpo.append(f'<tr class="hi"><td class="num">✓</td><td>chega em {codigo[escolha]} – {escape(escolha)}</td>'
                 f'<td></td><td class="num">{no_criterio(acumulado, criterio)}</td></tr>')
    st.markdown(_tabela_html('rota', ['Passo', 'Rua', f'peso do trecho ({un})', f'acumulado ({un})'], corpo),
                unsafe_allow_html=True)
    st.caption('acumulado = anterior + trecho → é a relaxação do Bellman-Ford: dist[v] = dist[pai] + peso. '
               'Trecho em vermelho = rua com peso negativo: ali o acumulado diminui.')


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title='Distribuição de remédios — Bellman-Ford', layout='wide', page_icon='💊')
    tema = cabecalho()
    cfg = barra_lateral()
    r = rodar_bf(cfg['modo'], cfg['versao'], cfg['no'], cfg['criterio'])
    linhas = tabela(cfg['modo'], cfg['versao'], cfg['versao_h'], cfg['no'], cfg['criterio'], cfg['nomes'])
    codigo = {x['nome']: f'H{i}' for i, x in enumerate(linhas, 1) if x['alcancavel']}   # H1 = mais perto

    metricas(r, cfg, linhas)
    mapa(cfg, linhas, tema)
    if linhas and not r.ciclo_negativo:          # com ciclo negativo não existem menores caminhos
        ranking(linhas, codigo, cfg['criterio'])
        resultado(r, cfg['grafo'], linhas, codigo, cfg['criterio'])


main()
