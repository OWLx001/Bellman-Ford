"""Mapa do grafo em Canvas (desenhado no navegador, sem recarregar o Streamlit).

Desenha as ruas (com os nomes ao dar zoom), anima as iterações do Bellman-Ford e
mostra a central, os hospitais e as rotas finais.

Os dados vão em quatro blocos JSON, para o app guardar em cache o que não muda:
    json_grafo(g)                                     ruas e vértices    (muda só com o mapa)
    json_pesos(g, criterio)                           peso de cada rua   (muda com o critério)
    json_busca(g, resultado, criterio)                iterações          (muda com central/critério)
    json_extra(g, criterio, central, pontos, rotas)   hospitais e rotas  (muda com o filtro)

`resultado` é o ResultadoBF de bellman_ford.py: cada passo traz as arestas (u, v)
que melhoraram na iteração, quantos vértices já foram alcançados e quantos melhoraram.
"""
import json
import math
from algoritmo.bellman_ford import aresta_mais_barata, peso
from mapa.rotas_texto import nome_da_rua


def _json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def _ponto(x, y):
    return [round(float(x), 6), round(float(y), 6)]


def _reduzir(coord, maximo):
    """Tira pontos de geometrias muito detalhadas (mantém o primeiro e o último)."""
    if len(coord) <= maximo:
        return coord
    salto = max(1, len(coord) // (maximo - 5))
    return coord[::salto] + [coord[-1]]


def _geometria(g, dados, u, v):
    """Pontos (lon, lat) do trecho; sem geometria no OSM, é a reta entre os dois vértices."""
    geom = dados.get('geometry')
    if geom is not None and hasattr(geom, 'coords'):
        return list(geom.coords)
    return [(g.nodes[u]['x'], g.nodes[u]['y']), (g.nodes[v]['x'], g.nodes[v]['y'])]


def _coords_aresta(g, u, v, criterio, maximo=70):
    """Pontos da aresta u -> v usada pelo Bellman-Ford, já no sentido u -> v."""
    if not g.get_edge_data(u, v):
        return None
    coord = _reduzir(_geometria(g, aresta_mais_barata(g, u, v, criterio), u, v), maximo)
    pu = (g.nodes[u]['x'], g.nodes[u]['y'])
    if (coord[0][0]-pu[0])**2 + (coord[0][1]-pu[1])**2 > (coord[-1][0]-pu[0])**2 + (coord[-1][1]-pu[1])**2:
        coord.reverse()
    return [_ponto(x, y) for x, y in coord]


def _vias(g):
    """Ruas desenhadas, cada uma uma vez só: [(u, v, dados, pontos)].

    As duas mãos de uma rua têm a mesma geometria (em ordem inversa), então viram uma via só.
    A lista fica guardada no grafo: json_grafo e json_pesos precisam da mesma ordem.
    """
    if '_vias' not in g.graph:
        vias, vistos = [], set()
        for u, v, dados in g.edges(data=True):
            coord = _reduzir(_geometria(g, dados, u, v), 80)
            pontas = tuple(sorted(tuple(round(x, 5) for x in p) for p in (coord[0], coord[-1])))
            chave = (min(str(u), str(v)), max(str(u), str(v)), pontas)
            if chave not in vistos:
                vistos.add(chave)
                vias.append((u, v, dados, coord))
        g.graph['_vias'] = vias
    return g.graph['_vias']


def json_grafo(g):
    nodes = {str(v): _ponto(d['x'], d['y']) for v, d in g.nodes(data=True)}
    vias = []
    nomes, indice_nome, via_nome = [], {}, []        # nome de cada via (escrito no mapa com zoom)
    for u, v, dados, coord in _vias(g):
        vias.append([_ponto(x, y) for x, y in coord])
        nome = nome_da_rua(dados)
        if nome is not None and nome not in indice_nome:
            indice_nome[nome] = len(nomes)
            nomes.append(nome)
        via_nome.append(indice_nome[nome] if nome is not None else -1)
    return _json({'nodes': nodes, 'vias': vias, 'nomes': nomes, 'via_nome': via_nome,
                  'qtd_vertices': g.number_of_nodes(), 'qtd_arestas': g.number_of_edges()})


def json_pesos(g, criterio='length'):
    """Para cada via: [comprimento em m, peso no sentido u -> v, peso no sentido v -> u (None = mão única)].

    É o que aparece ao clicar numa rua. O peso é o mesmo que o Bellman-Ford usa.
    """
    def p(a, b):
        if not g.has_edge(a, b):
            return None
        w = peso(aresta_mais_barata(g, a, b, criterio), criterio)
        return round(w, 1) if math.isfinite(w) else None

    return _json({'pesos': [[round(float(d.get('length', 0)), 1), p(u, v), p(v, u)] for u, v, d, _ in _vias(g)]})


def json_busca(g, resultado, criterio='length'):
    # Cada geometria relaxada vai uma vez só numa tabela; os passos guardam só índices.
    geo, indice = [], {}

    def id_aresta(u, v):
        if (u, v) not in indice:
            linha = _coords_aresta(g, u, v, criterio)
            indice[(u, v)] = len(geo) if linha else -1
            if linha:
                geo.append([str(v), linha])
        return indice[(u, v)]

    # Com ciclo negativo as mesmas arestas relaxam milhões de vezes: a animação leva só as que mudam
    # o "anterior" de um vértice (o desenho é o mesmo e o mapa não fica pesado). As contagens são as reais.
    passos, anterior = [], {}
    for p in resultado.passos:
        arestas = p['arestas']
        if resultado.ciclo_negativo:
            arestas = [(u, v) for u, v in arestas if anterior.get(v) != u]
            anterior.update((v, u) for u, v in arestas)
        passos.append({'e': [i for i in (id_aresta(u, v) for u, v in arestas) if i >= 0],
                       'alcancados': p['alcancados'], 'relaxadas': p['relaxadas']})
    return _json({'geo': geo, 'passos': passos, 'duracao': resultado.duracao, 'iteracoes': resultado.iteracoes,
                  'ciclo': resultado.ciclo_negativo})


def _linha_rota(g, rota, criterio):
    pts = []
    for u, v in zip(rota, rota[1:]):
        linha = _coords_aresta(g, u, v, criterio, maximo=10**9)
        if linha:
            pts.extend(linha if not pts else linha[1:])
    return pts


def json_extra(g, criterio='length', central=None, pontos=None, rotas=None, ciclo=None, ciclo_texto=''):
    """ciclo: vértices do ciclo negativo (desenhado em vermelho); ciclo_texto: rótulo dele no mapa."""
    return _json({'central': central, 'pontos': pontos or [], 'criterio': criterio,
                  'rotas': [_linha_rota(g, rota, criterio) for rota in (rotas or [])],
                  'cicloLinha': _linha_rota(g, ciclo, criterio) if ciclo else None, 'cicloTexto': ciclo_texto})


def montar_html(grafo_json, busca_json='{}', extra_json='{}', tema='escuro', pesos_json='{}'):
    tema = 'claro' if tema == 'claro' else 'escuro'
    return (HTML.replace('<html lang="pt-br">', f'<html lang="pt-br" data-theme="{tema}">', 1)
            .replace('/*GRAFO*/', grafo_json, 1).replace('/*BUSCA*/', busca_json, 1).replace('/*EXTRA*/', extra_json, 1)
            .replace('/*PESOS*/', pesos_json, 1))


HTML = r'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#111113;--panel:#1A1A1D;--panel2:#232327;--border:#2E2E33;--text:#E7E7EA;--muted:#9A9AA3;--accent:#71717A;--btnHover:#2C2C31;--ctlBg:rgba(26,26,29,.9);--hintBg:rgba(12,12,14,.75);
--map:#0C0C0E;--street:#45454C;--node:#A1A1AA;--explored:#D4D4D8;--frontier:#F2B740;--route:#34D399;--routeHi:#A7F3D0;--central:#A78BFA;--hosp:#F87171;--clinic:#FBBF24;--off:#6B7280;--label:#E6EAF2;--neg:#FB7185;--sel:#38BDF8}
:root[data-theme="claro"]{--bg:#FFFFFF;--panel:#F3F5F9;--panel2:#EEF2F7;--border:#D5DCE6;--text:#18212F;--muted:#5B6878;--accent:#2563EB;--btnHover:#E1E9F7;--ctlBg:rgba(255,255,255,.92);--hintBg:rgba(255,255,255,.85);
--map:#F7F9FC;--street:#B9C3D0;--node:#5B6B80;--explored:#2F6FDB;--frontier:#D98E04;--route:#10A26F;--routeHi:#065F46;--central:#7C3AED;--hosp:#DC2626;--clinic:#E08A00;--off:#9CA3AF;--label:#18212F;--neg:#E11D48;--sel:#0284C7}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{font-family:"Source Sans Pro","Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);display:flex;flex-direction:column;gap:8px;padding:2px;overflow:hidden;font-size:14px}
button{font:inherit;background:var(--panel2);color:var(--text);border:1px solid var(--border);border-radius:10px;min-height:36px;padding:6px 12px;cursor:pointer;transition:background .15s,border-color .15s,transform .05s;white-space:nowrap}
button:hover:not(:disabled){border-color:var(--accent);background:var(--btnHover)}button:active:not(:disabled){transform:translateY(1px)}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}button.primary:hover:not(:disabled){background:var(--accent);filter:brightness(1.1)}
button:disabled{opacity:.38;cursor:not-allowed}
input[type=range]{accent-color:var(--accent);cursor:pointer}input[type=range]:disabled{opacity:.4;cursor:not-allowed}input[type=checkbox]{accent-color:var(--accent);width:16px;height:16px;cursor:pointer}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.group{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.spacer{flex:1}.lbl{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:13px;cursor:pointer;user-select:none}
.stats{display:flex;flex-wrap:wrap;gap:6px}.chip{background:var(--panel);border:1px solid var(--border);border-radius:999px;padding:4px 11px;font-size:12.5px;color:var(--muted);white-space:nowrap}.chip strong{color:var(--text);font-weight:600;margin-left:3px}
.mapWrap{position:relative;flex:1;min-height:240px;background:var(--map);border:1px solid var(--border);border-radius:14px;overflow:hidden;touch-action:none}
canvas{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab}canvas.dragging{cursor:grabbing}canvas.hover{cursor:pointer}
.mapCtl{position:absolute;right:10px;top:10px;display:flex;flex-direction:column;gap:6px;z-index:2}.mapCtl button{width:38px;height:38px;padding:0;min-height:0;font-size:18px;background:var(--ctlBg);backdrop-filter:blur(4px)}
.hint{position:absolute;left:12px;bottom:10px;font-size:12px;color:var(--muted);background:var(--hintBg);padding:4px 9px;border-radius:8px;pointer-events:none}
.tip{position:absolute;z-index:3;pointer-events:none;background:var(--panel);color:var(--text);border:1px solid var(--border);border-radius:9px;padding:6px 9px;font-size:12.5px;box-shadow:0 6px 18px rgba(0,0,0,.25);max-width:260px;display:none}.tip b{display:block;margin-bottom:2px}.tip span{color:var(--muted)}.tip .neg{color:var(--neg);font-weight:600}.tip .pw{display:block;color:var(--text)}
.legend{display:flex;gap:14px;font-size:12px;color:var(--muted);overflow-x:auto;white-space:nowrap;padding:2px 2px 4px;scrollbar-width:thin}
.key{width:18px;display:inline-block;vertical-align:middle;border-top:3px solid;border-radius:2px;margin-right:5px}.dot{width:9px;height:9px;border-radius:50%;display:inline-block;vertical-align:middle;margin-right:5px}
.seek{flex:1;min-width:140px;display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px}.seek input{flex:1}
select{font:inherit;font-size:13px;background:var(--panel2);color:var(--text);border:1px solid var(--border);border-radius:10px;min-height:36px;padding:5px 10px;max-width:min(420px,70vw);min-width:0;text-overflow:ellipsis;cursor:pointer}.destSel{min-width:0}select:focus{outline:2px solid var(--accent);outline-offset:1px}
.info{font-size:13px;color:var(--muted);min-height:18px;padding:0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:900px){.hint{display:none}.legend{flex-wrap:wrap;white-space:normal;gap:4px 12px;overflow:visible}}
@media(max-width:640px){body{gap:6px;font-size:13px}button{min-height:34px;padding:5px 8px;font-size:13px}#speedText{display:none}
.bar>.group{display:grid;grid-template-columns:repeat(4,1fr);width:100%}.bar>.group button{padding:5px 2px}
.chip{padding:3px 8px;font-size:11.5px}.chip.opt{display:none}.stats{gap:5px}
.seek{min-width:100%}.speed{flex:1}.speed input{flex:1;width:auto}.destSel{min-width:100%;max-width:100%}.destSel select{flex:1 1 0;width:0;min-width:0;max-width:none}#car{width:100%}
.mapWrap{min-height:300px;border-radius:12px}.mapCtl{right:8px;top:8px;gap:5px}.mapCtl button{width:34px;height:34px;font-size:16px}
.legend{font-size:11px}.info{white-space:normal;font-size:12px;line-height:1.35}}
</style></head><body>
<div class="bar"><div class="group"><button class="primary" id="play">▶ Reproduzir</button><button id="step">Próximo</button><button id="end">Resultado</button><button id="reset">Reiniciar</button></div>
<label class="lbl speed">Velocidade <input id="speed" type="range" min="1" max="60" value="6"><span id="speedText">6/s</span></label><span class="spacer"></span><label class="lbl"><input id="nomesRuas" type="checkbox" checked> Nomes das ruas</label><label class="lbl"><input id="pesosRuas" type="checkbox" checked> Pesos das ruas</label><label class="lbl"><input id="showNodes" type="checkbox"> Mostrar vértices</label></div>
<div class="stats"><span class="chip opt">Vértices<strong id="nv">0</strong></span><span class="chip opt">Arestas<strong id="ne">0</strong></span><span class="chip">Iteração<strong id="count">0 / 0</strong></span><span class="chip">Alcançados<strong id="visited">—</strong></span><span class="chip">Relaxadas<strong id="frontier">—</strong></span><span class="chip">Rota destacada<strong id="cost">—</strong></span><span class="chip opt">Cálculo<strong id="time">—</strong></span></div>
<div class="mapWrap" id="wrap"><canvas id="map" aria-label="Mapa do grafo: linhas são as arestas (ruas). Arraste para mover; use a roda ou a pinça para aproximar."></canvas>
<div class="mapCtl"><button id="zoomIn" title="Aproximar" aria-label="Aproximar">+</button><button id="zoomOut" title="Afastar" aria-label="Afastar">−</button><button id="fit" title="Enquadrar central e hospitais" aria-label="Enquadrar central e hospitais">⤢</button><button id="cidade" title="Cidade inteira" aria-label="Cidade inteira">🗺</button><button id="cheia" title="Tela cheia" aria-label="Tela cheia">⛶</button></div>
<div class="tip" id="tip"></div>
<div class="hint">Arraste para mover · roda/pinça para zoom · clique num hospital para destacar a rota · clique numa rua para ver o peso</div></div>
<div class="legend"><span><i class="key" style="border-color:var(--street)"></i>ruas</span><span><i class="dot" style="background:var(--node)"></i>vértices</span><span><i class="key" style="border-color:var(--explored)"></i>relaxadas antes</span><span><i class="key" style="border-color:var(--frontier)"></i>relaxadas nesta iteração</span><span><i class="key" style="border-color:var(--route)"></i>rotas central → hospitais</span><span id="legCiclo" style="display:none"><i class="key" style="border-color:var(--neg)"></i>ciclo negativo</span><span id="legNeg" style="display:none"><b id="legNegV" style="color:var(--neg)"></b> = desconta <span id="legNegD"></span> do caminho (dê zoom)</span><span><i class="dot" style="background:var(--central)"></i>central</span><span><i class="dot" style="background:var(--hosp)"></i>hospital</span><span><i class="dot" style="background:var(--clinic)"></i>clínica/UPA</span></div>
<div class="bar"><label class="lbl destSel">Rota destacada <select id="dest" aria-label="Rota destacada"></select></label><label class="seek">Iteração <input id="seek" type="range" min="0" max="0" value="0"></label><button id="car" disabled>🚚 Animar entrega</button></div>
<div id="info" class="info" aria-live="polite"></div>
<script>
(()=>{'use strict';
const data=Object.assign({passos:[],geo:[],rotas:[],pontos:[],central:null,duracao:null,iteracoes:null,criterio:'length',pesos:[],ciclo:false,cicloLinha:null,cicloTexto:''},/*GRAFO*/,/*BUSCA*/,/*EXTRA*/,/*PESOS*/);const $=id=>document.getElementById(id);const cvs=$('map'),ctx=cvs.getContext('2d');
const css=getComputedStyle(document.documentElement);const C=n=>css.getPropertyValue('--'+n).trim();
const COL={};for(const k of['map','street','node','explored','frontier','route','routeHi','central','hosp','clinic','off','label','muted','neg','sel'])COL[k]=C(k);
const passos=data.passos,temBusca=passos.length>0,fmt=n=>Number(n).toLocaleString('pt-BR');

/* ---- coordenadas do mundo: centradas e escaladas (boa precisão para o Path2D) ---- */
const coords=Object.values(data.nodes);let b=[Infinity,Infinity,-Infinity,-Infinity];
for(const p of coords){if(p[0]<b[0])b[0]=p[0];if(p[1]<b[1])b[1]=p[1];if(p[0]>b[2])b[2]=p[0];if(p[1]>b[3])b[3]=p[1]}
if(!coords.length)b=[0,0,1,1];
const K=10000,ASP=1.057,lon0=(b[0]+b[2])/2,lat0=(b[1]+b[3])/2;
const W=p=>[(p[0]-lon0)*K,-(p[1]-lat0)*K*ASP];
const WX=Math.max(1e-3,(b[2]-b[0])*K),WY=Math.max(1e-3,(b[3]-b[1])*K*ASP);
function pathOf(lines){const P=new Path2D();for(const c of lines){if(!c||c.length<2)continue;let q=W(c[0]);P.moveTo(q[0],q[1]);for(let i=1;i<c.length;i++){q=W(c[i]);P.lineTo(q[0],q[1])}}return P}
/* Grade espacial: ruas e vértices divididos em blocos; só os blocos visíveis são desenhados. */
const G=Math.max(1,Math.min(28,Math.round(Math.sqrt(data.vias.length/60)))),cw=WX/G,ch=WY/G;
const cellOf=(x,y)=>[Math.max(0,Math.min(G-1,Math.floor((x+WX/2)/cw))),Math.max(0,Math.min(G-1,Math.floor((y+WY/2)/ch)))];
const cells=new Map();const cell=(i,j)=>{const k=i*G+j;let c=cells.get(k);if(!c){c={s:new Path2D(),n:new Path2D(),r:[],v:[],bb:[Infinity,Infinity,-Infinity,-Infinity]};cells.set(k,c)}return c};
const grow=(bb,x,y)=>{if(x<bb[0])bb[0]=x;if(y<bb[1])bb[1]=y;if(x>bb[2])bb[2]=x;if(y>bb[3])bb[3]=y};
const viaNome=data.via_nome||[];data.vias.forEach((via,idx)=>{if(via.length<2)return;const pts=via.map(W);const m=pts[pts.length>>1];const [i,j]=cellOf(m[0],m[1]);const c=cell(i,j);c.v.push(idx);c.s.moveTo(pts[0][0],pts[0][1]);grow(c.bb,pts[0][0],pts[0][1]);let melhor=null;for(let t=1;t<pts.length;t++){c.s.lineTo(pts[t][0],pts[t][1]);grow(c.bb,pts[t][0],pts[t][1]);const dx=pts[t][0]-pts[t-1][0],dy=pts[t][1]-pts[t-1][1],L=Math.hypot(dx,dy);if(!melhor||L>melhor.len){let a=Math.atan2(dy,dx);if(a>Math.PI/2)a-=Math.PI;else if(a<-Math.PI/2)a+=Math.PI;melhor={x:(pts[t][0]+pts[t-1][0])/2,y:(pts[t][1]+pts[t-1][1])/2,a,len:L}}}const n=viaNome[idx];if(melhor){melhor.n=n!=null?n:-1;melhor.i=idx;c.r.push(melhor)}});
for(const id in data.nodes){const q=W(data.nodes[id]);const [i,j]=cellOf(q[0],q[1]);const c=cell(i,j);c.n.moveTo(q[0],q[1]);c.n.lineTo(q[0]+1e-4,q[1]);grow(c.bb,q[0],q[1])}
const cellList=[...cells.values()];
function visibleCells(){const a=inv(0,0),z=inv(size.w,size.h),pad=8/S();return cellList.filter(c=>c.bb[2]>=a[0]-pad&&c.bb[0]<=z[0]+pad&&c.bb[3]>=a[1]-pad&&c.bb[1]<=z[1]+pad)}

/* ---- central, hospitais e rotas ---- */
const central=data.central?{...data.central,w:W([data.central.lon,data.central.lat])}:null;
const pontos=data.pontos.map((p,i)=>({...p,i,w:W([p.lon,p.lat])}));
const temRotas=data.rotas.some(r=>r&&r.length>1);
/* ciclo negativo (chave "Criar ciclo negativo"): desenhado em vermelho, com um círculo em volta */
const cicloW=data.cicloLinha&&data.cicloLinha.length>1?data.cicloLinha.map(W):null,cicloPath=cicloW?pathOf([data.cicloLinha]):null;
let cicloBB=null;if(cicloW){cicloBB=[Infinity,Infinity,-Infinity,-Infinity];for(const q of cicloW)grow(cicloBB,q[0],q[1])}
let rotasOutras=null,rotaHiPath=null,rotaHiW=[],pDest=null;
/* Troca a rota destacada no próprio navegador (sem recarregar o Streamlit). */
function setDest(i){pDest=i!=null&&pontos[i]?pontos[i]:null;rotasOutras=pathOf(data.rotas.filter((r,k)=>k!==i));const hi=pDest&&data.rotas[i]?data.rotas[i]:[];rotaHiPath=pathOf([hi]);rotaHiW=hi.map(W);carPos=0;carPlaying=false;if($('dest').value!==String(i??''))$('dest').value=String(i??'')}
{const sel=$('dest');if(!pontos.length)sel.closest('label').style.display='none';for(const p of pontos){const o=document.createElement('option');o.value=p.i;o.textContent=(p.i+1)+'. '+p.nome+(p.rotulo?' — '+p.rotulo:'');sel.appendChild(o)}sel.onchange=()=>{setDest(Number(sel.value));schedule()}}

/* ---- vista ---- */
let size={w:800,h:500,dpr:1},view={cx:0,cy:0,scale:1};
const base=()=>Math.min(size.w/(WX*1.08),size.h/(WY*1.08));
const S=()=>base()*view.scale;
const toScr=q=>{const s=S();return[size.w/2+(q[0]-view.cx)*s,size.h/2+(q[1]-view.cy)*s]};
const inv=(x,y)=>{const s=S();return[view.cx+(x-size.w/2)/s,view.cy+(y-size.h/2)/s]};
function clampView(){view.scale=Math.min(80,Math.max(.6,view.scale));view.cx=Math.max(-WX/2,Math.min(WX/2,view.cx));view.cy=Math.max(-WY/2,Math.min(WY/2,view.cy))}
function resize(){const r=cvs.getBoundingClientRect();size={w:Math.max(200,r.width),h:Math.max(200,r.height),dpr:Math.min(2,window.devicePixelRatio||1)};cvs.width=Math.round(size.w*size.dpr);cvs.height=Math.round(size.h*size.dpr);paint()}

/* ---- camadas da busca: recalculadas só quando o passo muda ----
   azul = arestas da árvore de caminhos mínimos já relaxadas em iterações anteriores;
   amarelo = arestas relaxadas na iteração atual. Se um vértice melhora de novo, a aresta nova substitui a antiga. */
let frame=temBusca?passos.length:0,ovFrame=-1,ov={closed:null,front:null};
function overlay(){if(ovFrame===frame)return ov;const pairs=new Map();for(let i=0;i<frame;i++)for(const e of passos[i].e)pairs.set(data.geo[e][0],[e,i]);
const closed=[],front=[];for(const [,[e,i]] of pairs)(i===frame-1?front:closed).push(data.geo[e][1]);ov={closed:pathOf(closed),front:pathOf(front)};ovFrame=frame;return ov}

/* ---- desenho ---- */
let carPlaying=false,carPos=0,hover=null,ruaSel=null;
const done=()=>!temBusca||frame>=passos.length;
function strokeW(P,color,px,alpha=1){const s=S();ctx.globalAlpha=alpha;ctx.strokeStyle=color;ctx.lineWidth=px/s;ctx.stroke(P);ctx.globalAlpha=1}
function label(text,x,y){ctx.font='600 12px system-ui';ctx.lineWidth=3.5;ctx.strokeStyle=COL.map;ctx.lineJoin='round';ctx.strokeText(text,x,y);ctx.fillStyle=COL.label;ctx.fillText(text,x,y)}
function drawPonto(p){const [x,y]=toScr(p.w),hi=pDest&&p.i===pDest.i,hosp=p.tipo==='hospital';const r=(hosp?7:5.5)+(hi?2:0)+(hover===p?1.5:0);
const cor=p.alcancavel===false?COL.off:hosp?COL.hosp:COL.clinic;ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.fillStyle=cor;ctx.fill();ctx.lineWidth=hi?3:2;ctx.strokeStyle=hi?COL.routeHi:COL.map;ctx.stroke();
if(hosp){ctx.fillStyle='#fff';const a=r*.55,t=Math.max(1.4,r*.22);ctx.fillRect(x-a,y-t,2*a,2*t);ctx.fillRect(x-t,y-a,2*t,2*a)}
if(hi||view.scale>=3.2||hover===p)label(p.nome,x+r+5,y-r-2)}
function drawCentral(){if(!central)return;const [x,y]=toScr(central.w);ctx.save();ctx.translate(x,y);ctx.rotate(Math.PI/4);ctx.fillStyle=COL.central;ctx.fillRect(-9,-9,18,18);ctx.lineWidth=2.5;ctx.strokeStyle=COL.map;ctx.strokeRect(-9,-9,18,18);ctx.restore();ctx.font='13px system-ui';ctx.fillText('💊',x-8,y+5);label(central.nome||'Central',x+14,y-12)}
function paint(){const {w,h,dpr}=size,s=S();
ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle=COL.map;ctx.fillRect(0,0,w,h);
ctx.setTransform(dpr*s,0,0,dpr*s,dpr*(w/2-view.cx*s),dpr*(h/2-view.cy*s));ctx.lineJoin='round';ctx.lineCap='round';
const vis=visibleCells();
ctx.globalAlpha=.95;ctx.strokeStyle=COL.street;ctx.lineWidth=Math.min(2.2,.9+view.scale*.06)/s;for(const c of vis)ctx.stroke(c.s);
if($('showNodes').checked){ctx.globalAlpha=.9;ctx.strokeStyle=COL.node;ctx.lineWidth=Math.max(2,Math.min(7,1.6+view.scale*.9))/s;for(const c of vis)ctx.stroke(c.n)}
ctx.globalAlpha=1;
if(temBusca&&frame>0&&!(done()&&temRotas)){const o=overlay();strokeW(o.closed,COL.explored,2.4,.85);strokeW(o.front,COL.frontier,2.6,.95)}
if(done()&&temRotas){strokeW(rotasOutras,COL.route,3.2,.85);strokeW(rotaHiPath,COL.map,8.5,1);strokeW(rotaHiPath,COL.routeHi,5.5,1)}
if(cicloPath){strokeW(cicloPath,COL.map,10,1);strokeW(cicloPath,COL.neg,6,1)}
if(ruaSel){if(!ruaSel.path)ruaSel.path=pathOf([data.vias[ruaSel.i]]);strokeW(ruaSel.path,COL.map,9,1);strokeW(ruaSel.path,COL.sel,5.5,1)}
ctx.setTransform(dpr,0,0,dpr,0,0);
desenharSelecao();
const ocupado=[];desenharCiclo(ocupado);desenharNomes(vis,ocupado);desenharPesos(vis,ocupado);
for(const p of pontos)if(p!==pDest)drawPonto(p);if(pDest)drawPonto(pDest);drawCentral();
if(done()&&(carPlaying||carPos>0)&&rotaHiW.length){const k=Math.max(0,Math.min(rotaHiW.length-1,Math.floor(carPos)));const [x,y]=toScr(rotaHiW[k]);ctx.font='22px system-ui';ctx.fillText('🚚',x-12,y-8)}
if(ruaSel&&!hover)tipRua();
updateUI()}
/* ---- rua clicada: seta no sentido "→" ---- */
const meio=via=>{const p=via.map(W);let m=null;for(let t=1;t<p.length;t++){const dx=p[t][0]-p[t-1][0],dy=p[t][1]-p[t-1][1],L=Math.hypot(dx,dy);if(!m||L>m.len)m={w:[(p[t][0]+p[t-1][0])/2,(p[t][1]+p[t-1][1])/2],a:Math.atan2(dy,dx),len:L}}return m};
function seta(w,a,cor,tam){const [x,y]=toScr(w);ctx.save();ctx.translate(x,y);ctx.rotate(a);ctx.beginPath();ctx.moveTo(tam,0);ctx.lineTo(-tam*.75,tam*.7);ctx.lineTo(-tam*.75,-tam*.7);ctx.closePath();ctx.fillStyle=cor;ctx.fill();ctx.lineWidth=1.6;ctx.strokeStyle=COL.map;ctx.stroke();ctx.restore()}
function desenharSelecao(){if(ruaSel){if(!ruaSel.m)ruaSel.m=meio(data.vias[ruaSel.i]);if(ruaSel.m)seta(ruaSel.m.w,ruaSel.m.a,COL.sel,8)}}
function desenharCiclo(ocupado){if(!cicloBB)return;const s=S(),[x,y]=toScr([(cicloBB[0]+cicloBB[2])/2,(cicloBB[1]+cicloBB[3])/2]);
const r=Math.max(22,Math.hypot(cicloBB[2]-cicloBB[0],cicloBB[3]-cicloBB[1])*s/2+14);
ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.lineWidth=5;ctx.strokeStyle=COL.map;ctx.stroke();ctx.lineWidth=2.5;ctx.strokeStyle=COL.neg;ctx.stroke();
if(data.cicloTexto){ctx.font='700 13px system-ui';const tw=ctx.measureText(data.cicloTexto).width,tx=x-tw/2,ty=y-r-10;
ctx.lineWidth=4;ctx.lineJoin='round';ctx.strokeStyle=COL.map;ctx.strokeText(data.cicloTexto,tx,ty);ctx.fillStyle=COL.neg;ctx.fillText(data.cicloTexto,tx,ty);ocupado.push([tx-4,ty-14,tx+tw+4,ty+4])}
ocupado.push([x-r,y-r,x+r,y+r])}
const sobrepoe=(ocupado,b)=>ocupado.some(o=>o[0]<b[2]&&b[0]<o[2]&&o[1]<b[3]&&b[1]<o[3]);
/* ---- peso de cada rua escrito no mapa (com zoom): negativos em vermelho, primeiro ---- */
const ZOOM_PESOS=3.2;
function textoPeso(pw){if(!pw||pw[1]==null)return null;const m=(data.criterio||'').startsWith('dist'),f=v=>fmtPeso(m?Math.round(v):v);   // no mapa, metros sem casas
if(pw[2]==null||pw[2]===pw[1])return f(pw[1]);return f(pw[1]).replace(/ [ms]$/,'')+' / '+f(pw[2])}
function desenharPesos(vis,ocupado){if(!$('pesosRuas').checked||!data.pesos.length)return;const s=S();if(s<ZOOM_PESOS)return;
const cand=[];for(const c of vis)for(const r of c.r){const pw=data.pesos[r.i];if(!pw)continue;const neg=(pw[1]??0)<0||(pw[2]??0)<0;if(neg||r.len*s>=34)cand.push([r,pw,neg])}
cand.sort((a,b)=>(b[2]-a[2])||(b[0].len-a[0].len));
ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineJoin='round';let total=0;
for(const [r,pw,neg] of cand){if(total>=200)break;const txt=textoPeso(pw);if(!txt)continue;
const [x0,y0]=toScr([r.x,r.y]);const x=x0-Math.sin(r.a)*11,y=y0+Math.cos(r.a)*11;if(x<-30||y<-15||x>size.w+30||y>size.h+15)continue;
ctx.font=(neg?'700 12px':'500 10.5px')+' system-ui';const tw=ctx.measureText(txt).width;
const co=Math.abs(Math.cos(r.a)),si=Math.abs(Math.sin(r.a)),hw=co*tw/2+si*6,hh=si*tw/2+co*6,b=[x-hw,y-hh,x+hw,y+hh];
if(sobrepoe(ocupado,b))continue;ocupado.push(b);total++;
ctx.save();ctx.translate(x,y);ctx.rotate(r.a);ctx.lineWidth=3.5;ctx.strokeStyle=COL.map;ctx.strokeText(txt,0,0);ctx.globalAlpha=neg?1:.85;ctx.fillStyle=neg?COL.neg:COL.muted;ctx.fillText(txt,0,0);ctx.restore()}
ctx.textAlign='start';ctx.textBaseline='alphabetic'}
/* ---- nomes das ruas: só com zoom, ao longo da rua, sem sobrepor nem repetir perto ---- */
const ZOOM_NOMES=1.6,larguraNome=new Map();
function desenharNomes(vis,ocupado){if(!$('nomesRuas').checked||!data.nomes)return;const s=S();if(s<ZOOM_NOMES)return;
const cand=[];for(const c of vis)for(const r of c.r)if(r.n>=0&&r.len*s>=25)cand.push(r);cand.sort((a,b)=>b.len-a.len);
ctx.font='600 11px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineJoin='round';
const perto=new Map();let total=0;
for(const r of cand){if(total>=150)break;const nome=data.nomes[r.n];let tw=larguraNome.get(nome);if(tw==null){tw=ctx.measureText(nome).width;larguraNome.set(nome,tw)}
if(r.len*s<tw*.45)continue;const [x,y]=toScr([r.x,r.y]);if(x<-40||y<-20||x>size.w+40||y>size.h+20)continue;
const ja=perto.get(r.n);if(ja&&ja.some(p=>Math.hypot(p[0]-x,p[1]-y)<250))continue;
const co=Math.abs(Math.cos(r.a)),si=Math.abs(Math.sin(r.a)),hw=co*tw/2+si*7,hh=si*tw/2+co*7,cx=[x-hw,y-hh,x+hw,y+hh];
if(sobrepoe(ocupado,cx))continue;
ocupado.push(cx);if(ja)ja.push([x,y]);else perto.set(r.n,[[x,y]]);total++;
ctx.save();ctx.translate(x,y);ctx.rotate(r.a);ctx.lineWidth=3.5;ctx.strokeStyle=COL.map;ctx.strokeText(nome,0,0);ctx.fillStyle=COL.muted;ctx.fillText(nome,0,0);ctx.restore()}
ctx.textAlign='start';ctx.textBaseline='alphabetic'}
let pending=false;function schedule(){if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;paint()})}}

function updateUI(){$('count').textContent=frame+' / '+passos.length;const pa=frame?passos[frame-1]:null;
$('visited').textContent=pa?fmt(pa.alcancados):'—';$('frontier').textContent=pa?fmt(pa.relaxadas):'—';
$('cost').textContent=pDest&&pDest.rotulo?pDest.rotulo:'—';$('time').textContent=data.duracao!=null?data.duracao.toFixed(2)+' s':'—';
$('seek').value=frame;$('car').disabled=!done()||!rotaHiW.length;
let t;if(!temBusca&&!pontos.length)t='Grafo carregado: '+fmt(data.qtd_vertices)+' vértices e '+fmt(data.qtd_arestas)+' arestas. Escolha a central e clique em Calcular com Bellman-Ford.';
else if(!temBusca)t=pontos.length+' estabelecimentos no mapa. Clique em Calcular com Bellman-Ford para traçar as rotas.';
else if(frame===passos.length&&data.ciclo)t='Ciclo negativo detectado na iteração '+data.iteracoes+(cicloW?' (em vermelho no mapa)':'')+'. Não existe menor caminho.';
else if(frame===passos.length)t='Bellman-Ford convergiu em '+(data.iteracoes||passos.length)+' iterações ('+passos.length+' com relaxações'+(data.iteracoes>passos.length?' + a última, sem mudanças, que confirma':'')+')'+(pDest?' · destaque: '+pDest.nome+(pDest.rotulo?' — '+pDest.rotulo:''):'')+'. Use Reiniciar/Reproduzir para ver as relaxações.';
else if(pa)t='iteração = '+frame+' | relaxadas = '+fmt(pa.relaxadas)+' | alcançados = '+fmt(pa.alcancados);
else t='Início: só a central tem distância 0; as demais são ∞. Clique em Reproduzir ou Próximo.';$('info').textContent=t}

/* ---- reprodução ---- */
let playing=false,last=0,carry=0,raf=0;
function toggle(on){playing=on&&temBusca;carPlaying=false;$('play').textContent=playing?'⏸ Pausar':'▶ Reproduzir';if(playing){last=0;carry=0;request()}}
function request(){if(!raf)raf=requestAnimationFrame(tick)}
function tick(ts){raf=0;if(!last)last=ts;const dt=Math.min(.1,(ts-last)/1000);last=ts;
if(playing){carry+=dt*Number($('speed').value);const st=Math.min(200,Math.floor(carry));if(st){carry-=st;frame=Math.min(passos.length,frame+st);paint()}if(frame>=passos.length)toggle(false)}
if(carPlaying){carPos=Math.min(rotaHiW.length-1,carPos+dt*Math.max(15,rotaHiW.length/8));paint();if(carPos>=rotaHiW.length-1)carPlaying=false}
if(playing||carPlaying)request()}
for(const id of['play','step','end','reset','seek','speed'])$(id).disabled=!temBusca;
$('nv').textContent=fmt(data.qtd_vertices);$('ne').textContent=fmt(data.qtd_arestas);
$('play').onclick=()=>frame===passos.length?(frame=0,carPos=0,toggle(true)):toggle(!playing);
$('step').onclick=()=>{toggle(false);frame=Math.min(passos.length,frame+1);paint()};
$('reset').onclick=()=>{toggle(false);frame=0;carPos=0;paint()};
$('end').onclick=()=>{toggle(false);frame=passos.length;carPos=0;paint()};
$('seek').max=passos.length;$('seek').oninput=e=>{toggle(false);frame=Number(e.target.value);carPos=0;schedule()};
$('speed').oninput=e=>$('speedText').textContent=e.target.value+'/s';
$('car').onclick=()=>{toggle(false);carPos=0;carPlaying=true;last=0;request()};
$('showNodes').onchange=schedule;$('nomesRuas').onchange=schedule;$('pesosRuas').onchange=schedule;
{const neg=data.pesos.find(p=>(p[1]??0)<0||(p[2]??0)<0);if(neg){$('legNeg').style.display='';const vn=Math.min(neg[1]??0,neg[2]??0);$('legNegV').textContent=fmtPeso(vn);$('legNegD').textContent=fmtPeso(-vn)}}

/* ---- dica ao passar o mouse ---- */
const tip=$('tip');
function hit(x,y){let best=null,bd=14*14;for(const p of pontos){const [px,py]=toScr(p.w),d=(px-x)**2+(py-y)**2;if(d<bd){bd=d;best=p}}if(central){const [px,py]=toScr(central.w),d=(px-x)**2+(py-y)**2;if(d<bd)best={central:true}}return best}
function showTip(x,y){const h=hit(x,y);const novo=h&&!h.central?h:null;if(novo!==hover){hover=novo;schedule()}cvs.classList.toggle('hover',!!h);
if(!h){if(!tipRua())tip.style.display='none';return}
tip.innerHTML=h.central?'<b>'+esc(central.nome||'Central')+'</b><span>Central de distribuição de remédios</span>':'<b>'+esc(h.nome)+'</b><span>'+(h.tipo==='hospital'?'Hospital':'Clínica/UPA/UAI')+(h.rotulo?' · '+esc(h.rotulo):'')+(h.alcancavel===false?' · sem rota':'')+'</span>';
tip.style.display='block';posTip(x,y)}
function posTip(x,y){const r=$('wrap').getBoundingClientRect(),tw=tip.offsetWidth,th=tip.offsetHeight;tip.style.left=Math.max(6,Math.min(r.width-tw-6,x+14))+'px';tip.style.top=Math.max(6,y-th-10)+'px'}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---- clicar numa rua mostra o peso dela (o mesmo que o Bellman-Ford usa) ---- */
function distSeg(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],L=dx*dx+dy*dy;const t=L?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L)):0;const ex=a[0]+t*dx-p[0],ey=a[1]+t*dy-p[1];return ex*ex+ey*ey}
function ruaPerto(x,y){const a=inv(x,y),tol=10/S();let melhor=-1,md=tol*tol,neg=-1,nd=tol*tol;
for(const c of cellList){if(a[0]<c.bb[0]-tol||a[0]>c.bb[2]+tol||a[1]<c.bb[1]-tol||a[1]>c.bb[3]+tol)continue;
for(const i of c.v){const via=data.vias[i],pw=data.pesos[i],negativa=pw&&((pw[1]??0)<0||(pw[2]??0)<0);let q=W(via[0]);
for(let t=1;t<via.length;t++){const r=W(via[t]),d=distSeg(a,q,r);if(d<md){md=d;melhor=i}if(negativa&&d<nd){nd=d;neg=i}q=r}}}
return neg>=0?neg:melhor}   // perto da linha vermelha, a rua com peso negativo tem preferência
function fmtPeso(w){if(w==null)return 'não existe (mão única)';const c=data.criterio||'dist';
return (w<0?'−':'')+Math.abs(w).toLocaleString('pt-BR',{maximumFractionDigits:1})+(c.startsWith('tempo')||c==='travel_time'?' s':' m')}
function tipRua(){if(!ruaSel)return false;const n=viaNome[ruaSel.i],pw=data.pesos[ruaSel.i];
let h='<b>'+esc(n!=null&&n>=0?data.nomes[n]:'Rua sem nome')+'</b>';
if(pw){h+='<span>comprimento: '+fmt(Math.round(pw[0]))+' m</span><span class="pw">peso → (seta azul): '+fmtPeso(pw[1])+'</span><span class="pw">peso ← (contrário): '+fmtPeso(pw[2])+'</span>';
const vn=Math.min(pw[1]??0,pw[2]??0);if(vn<0)h+='<span class="neg">peso negativo: passar por aqui desconta '+fmtPeso(-vn)+' do total do caminho</span>'}
tip.innerHTML=h;tip.style.display='block';const [x,y]=toScr(ruaSel.w);posTip(x,y);return true}

/* ---- zoom/arrastar (mouse e toque) ---- */
function zoomAt(f,x=size.w/2,y=size.h/2){const a=inv(x,y);view.scale*=f;clampView();const s=S();view.cx=a[0]-(x-size.w/2)/s;view.cy=a[1]-(y-size.h/2)/s;clampView();schedule()}
let anim=0;function animateTo(target){cancelAnimationFrame(anim);const from={...view},t0=performance.now();const step=t=>{const k=Math.min(1,(t-t0)/260),e=1-Math.pow(1-k,3);view.cx=from.cx+(target.cx-from.cx)*e;view.cy=from.cy+(target.cy-from.cy)*e;view.scale=from.scale*Math.pow(target.scale/from.scale,e);paint();if(k<1)anim=requestAnimationFrame(step)};anim=requestAnimationFrame(step)}
function smoothZoom(f){animateTo({...view,scale:Math.min(80,Math.max(.6,view.scale*f))})}
$('zoomIn').onclick=()=>smoothZoom(1.6);$('zoomOut').onclick=()=>smoothZoom(1/1.6);$('fit').onclick=()=>animateTo(vistaRotas());$('cidade').onclick=()=>animateTo({cx:0,cy:0,scale:1});$('cheia').onclick=telaCheia;
const rel=e=>{const r=cvs.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top}};
cvs.addEventListener('wheel',e=>{e.preventDefault();cancelAnimationFrame(anim);const d=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?400:1);const p=rel(e);zoomAt(Math.exp(-Math.max(-300,Math.min(300,d))*.0018),p.x,p.y)},{passive:false});
cvs.addEventListener('dblclick',e=>{const p=rel(e);const a=inv(p.x,p.y);animateTo({cx:a[0],cy:a[1],scale:Math.min(80,view.scale*2)})});
const pts=new Map();let gest=null;
function startGesture(){const a=[...pts.values()];if(a.length===1)gest={t:'pan',x:a[0].x,y:a[0].y,cx:view.cx,cy:view.cy};else if(a.length>=2){const[p,q]=a,mx=(p.x+q.x)/2,my=(p.y+q.y)/2;gest={t:'pinch',d:Math.hypot(p.x-q.x,p.y-q.y)||1,scale:view.scale,world:inv(mx,my)}}else gest=null;cvs.classList.toggle('dragging',!!gest)}
cvs.addEventListener('pointerdown',e=>{cancelAnimationFrame(anim);tip.style.display='none';pts.set(e.pointerId,rel(e));cvs.setPointerCapture(e.pointerId);startGesture()});
cvs.addEventListener('pointermove',e=>{const p=rel(e);if(!pts.has(e.pointerId)||!gest){if(e.pointerType==='mouse')showTip(p.x,p.y);return}pts.set(e.pointerId,p);const a=[...pts.values()];
if(gest.t==='pan'&&a.length===1){const s=S();view.cx=gest.cx-(a[0].x-gest.x)/s;view.cy=gest.cy-(a[0].y-gest.y)/s}
else if(gest.t==='pinch'&&a.length>=2){const[p1,q]=a,mx=(p1.x+q.x)/2,my=(p1.y+q.y)/2;view.scale=gest.scale*Math.hypot(p1.x-q.x,p1.y-q.y)/gest.d;clampView();const s=S();view.cx=gest.world[0]-(mx-size.w/2)/s;view.cy=gest.world[1]-(my-size.h/2)/s}
clampView();schedule()});
const endPtr=e=>{const p=rel(e),moved=!!gest&&(gest.t!=='pan'||Math.hypot(p.x-gest.x,p.y-gest.y)>4);pts.delete(e.pointerId);startGesture();
if(!moved){const h=hit(p.x,p.y);if(h&&!h.central){setDest(h.i);ruaSel=null}else if(!h){const i=ruaPerto(p.x,p.y);ruaSel=i>=0?{i,w:inv(p.x,p.y)}:null;if(!ruaSel)tip.style.display='none'}schedule();if(e.pointerType!=='mouse')showTip(p.x,p.y)}};
cvs.addEventListener('pointerup',endPtr);cvs.addEventListener('pointercancel',endPtr);cvs.addEventListener('pointerleave',()=>{if(!gest){tip.style.display='none';if(hover){hover=null;schedule()}}});
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;if(e.key==='+'||e.key==='=')smoothZoom(1.6);else if(e.key==='-')smoothZoom(1/1.6);else if(e.key==='0')animateTo({cx:0,cy:0,scale:1});else if(e.key==='Escape'){if(ruaSel){ruaSel=null;tip.style.display='none';schedule()}else if(pseudo)telaCheia()}});
/* ---- enquadrar central + hospitais ---- */
function vistaCiclo(){const a=cicloBB,w=Math.max(a[2]-a[0],40),h=Math.max(a[3]-a[1],40);
return{cx:(a[0]+a[2])/2,cy:(a[1]+a[3])/2,scale:Math.min(80,Math.max(1,Math.min(size.w/(w*1.25),size.h/(h*1.25))/base()))}}
function vistaRotas(){if(cicloBB)return vistaCiclo();const pts=pontos.map(p=>p.w);if(central)pts.push(central.w);for(const r of data.rotas)for(let i=0;i<r.length;i+=8)pts.push(W(r[i]));
if(pts.length<2)return{cx:0,cy:0,scale:1};let a=[Infinity,Infinity,-Infinity,-Infinity];for(const q of pts)grow(a,q[0],q[1]);
const w=Math.max(a[2]-a[0],WX*.04),h=Math.max(a[3]-a[1],WY*.04);const sc=Math.min(size.w/(w*1.25),size.h/(h*1.25))/base();
return{cx:(a[0]+a[2])/2,cy:(a[1]+a[3])/2,scale:Math.min(80,Math.max(1,sc))}}

/* ---- tela cheia: o próprio iframe vai para tela cheia; se o navegador recusar, cobre a página ---- */
let pseudo=false;const fe=window.frameElement,docPai=fe?fe.ownerDocument:document;
function iconeCheia(){const on=!!docPai.fullscreenElement||pseudo;$('cheia').textContent=on?'✕':'⛶';$('cheia').title=on?'Sair da tela cheia':'Tela cheia'}
function pseudoTela(on){pseudo=on;if(!fe)return;const st=fe.style;for(const [k,v] of [['position','fixed'],['inset','0'],['z-index','999999'],['width','100vw'],['height','100vh'],['border-radius','0']]){if(on)st.setProperty(k,v,'important');else st.removeProperty(k)}iconeCheia()}
function telaCheia(){if(pseudo||docPai.fullscreenElement){pseudoTela(false);if(docPai.fullscreenElement)docPai.exitFullscreen().catch(()=>{});return}
pseudoTela(true);   // cobre a página na hora (funciona em qualquer navegador)
const alvo=fe||document.documentElement;try{const p=alvo.requestFullscreen&&alvo.requestFullscreen();if(p&&p.catch)p.catch(()=>{})}catch(err){}}   // e tenta a tela cheia de verdade
docPai.addEventListener('fullscreenchange',()=>{if(!docPai.fullscreenElement&&pseudo&&fsAtivo)pseudoTela(false);fsAtivo=!!docPai.fullscreenElement;iconeCheia()});let fsAtivo=false;
try{docPai.addEventListener('keydown',e=>{if(e.key==='Escape'&&pseudo)pseudoTela(false)})}catch(err){}

{const k=pontos.findIndex(p=>p.alcancavel!==false);setDest(k>=0?k:null)}
if(window.ResizeObserver)new ResizeObserver(resize).observe($('wrap'));else window.addEventListener('resize',resize);
if(cicloBB)$('legCiclo').style.display='';
resize();if(pontos.length||cicloBB){view=vistaRotas();paint()}if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)$('speed').value=1;
})();
</script></body></html>'''
