"""Visualizador do grafo em Canvas (no navegador, sem recarregar o Streamlit).

Desenha o grafo (ruas e, opcionalmente, vértices) e, quando recebe o resultado
do algoritmo (ex.: Bellman-Ford), anima as relaxações passo a passo e mostra a
central, os hospitais e as rotas finais.

Os dados vão em três blocos JSON separados, para o app poder guardar em cache
o que não muda (o grafo) e regerar só o que mudou:
    json_grafo(g)                         ruas e vértices            (muda só com o mapa)
    json_busca(g, resultado, criterio)    passos da animação         (muda com central/critério)
    json_extra(g, criterio, central, pontos, rotas)  hospitais e rotas (muda com o filtro)

Formato esperado de `resultado` (objeto com `passos`; opcionais `duracao`, `iteracoes`):
    passos      lista de dicts, um por passo da animação. Cada passo traz:
                  'arestas'        lista de (u, v) relaxadas no passo  — ou —
                  'atual' + 'novos' vértice processado e vizinhos melhorados
                  'qtd_visitados'  opcional, mostrado em "Alcançados"
                  'qtd_fila'       opcional, mostrado em "Relaxadas"
                  'info'           opcional, dict {rótulo: valor} exibido no rodapé
Extras:
    central     {'nome', 'lat', 'lon'}
    pontos      [{'nome', 'tipo' ('hospital'|'clinica'), 'lat', 'lon', 'rotulo', 'alcancavel'}]
    rotas       lista paralela a `pontos`: vértices da rota central -> ponto ([] se não há)
"""
import json


def _json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def _coords_aresta(g, u, v, criterio, limite=70):
    """Pontos (lon, lat) da aresta u->v, já no sentido u -> v."""
    data = g.get_edge_data(u, v)
    if not data:
        return None
    d = min(data.values(), key=lambda a: float(a.get(criterio, float('inf'))))
    geom = d.get('geometry')
    nu, nv = g.nodes[u], g.nodes[v]
    pu = (float(nu['x']), float(nu['y']))
    coord = list(geom.coords) if geom is not None and hasattr(geom, 'coords') else [pu, (float(nv['x']), float(nv['y']))]
    if len(coord) > limite:
        salto = max(1, len(coord) // (limite - 5))
        coord = coord[::salto] + [coord[-1]]
    if (coord[0][0]-pu[0])**2 + (coord[0][1]-pu[1])**2 > (coord[-1][0]-pu[0])**2 + (coord[-1][1]-pu[1])**2:
        coord.reverse()
    return [[round(float(x), 6), round(float(y), 6)] for x, y in coord]


def json_grafo(g):
    nodes = {str(v): [round(float(d['x']), 6), round(float(d['y']), 6)] for v, d in g.nodes(data=True)}
    # Desenha apenas uma vez cada geometria de rua (duas direções usam a mesma rua).
    vias, vistos = [], set()
    for u, v, data in g.edges(data=True):
        geom = data.get('geometry')
        coord = list(geom.coords) if geom is not None and hasattr(geom, 'coords') else [nodes[str(u)], nodes[str(v)]]
        if len(coord) > 80:
            salto = max(1, len(coord) // 75)
            coord = coord[::salto] + [coord[-1]]
        chave = (min(str(u), str(v)), max(str(u), str(v)),
                 tuple(round(x, 5) for x in coord[0]), tuple(round(x, 5) for x in coord[-1]))
        if chave in vistos:
            continue
        vistos.add(chave)
        vias.append([[round(float(x), 6), round(float(y), 6)] for x, y in coord])
    return _json({'nodes': nodes, 'vias': vias,
                  'qtd_vertices': g.number_of_nodes(), 'qtd_arestas': g.number_of_edges()})


def json_busca(g, resultado, criterio='length'):
    if resultado is None:
        return '{}'
    # Tabela de arestas relaxadas: cada geometria vai uma vez só; os passos guardam índices.
    geo, indice = [], {}

    def id_aresta(u, v):
        k = (u, v)
        if k not in indice:
            linha = _coords_aresta(g, u, v, criterio)
            indice[k] = -1 if not linha else len(geo)
            if linha:
                geo.append([str(v), linha])
        return indice[k]

    passos = []
    for p in resultado.passos:
        pares = p['arestas'] if 'arestas' in p else [(p['atual'], v) for v in p.get('novos', [])]
        ids = [i for i in (id_aresta(u, v) for u, v in pares) if i >= 0]
        info = {str(k): (round(x, 3) if isinstance(x, float) else x) for k, x in (p.get('info') or {}).items()}
        passos.append({'e': ids, 'atual': str(p['atual']) if 'atual' in p else None, 'info': info,
                       'visitados': p.get('qtd_visitados'), 'fila': p.get('qtd_fila')})
    return _json({'geo': geo, 'passos': passos,
                  'duracao': getattr(resultado, 'duracao', None),
                  'iteracoes': getattr(resultado, 'iteracoes', None)})


def json_extra(g, criterio='length', central=None, pontos=None, rotas=None):
    linhas_rotas = []
    for rota in (rotas or []):
        pts = []
        for u, v in zip(rota, rota[1:]):
            linha = _coords_aresta(g, u, v, criterio, limite=10**9)
            if linha:
                pts.extend(linha if not pts else linha[1:])
        linhas_rotas.append(pts)
    return _json({'central': central, 'pontos': pontos or [], 'rotas': linhas_rotas, 'criterio': criterio})


def montar_html(grafo_json, busca_json='{}', extra_json='{}', tema='escuro'):
    tema = 'claro' if tema == 'claro' else 'escuro'
    return (HTML.replace('<html lang="pt-br">', f'<html lang="pt-br" data-theme="{tema}">', 1)
            .replace('/*GRAFO*/', grafo_json, 1).replace('/*BUSCA*/', busca_json, 1).replace('/*EXTRA*/', extra_json, 1))


HTML = r'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#111113;--panel:#1A1A1D;--panel2:#232327;--border:#2E2E33;--text:#E7E7EA;--muted:#9A9AA3;--accent:#71717A;--btnHover:#2C2C31;--ctlBg:rgba(26,26,29,.9);--hintBg:rgba(12,12,14,.75);
--map:#0C0C0E;--street:#45454C;--node:#A1A1AA;--explored:#D4D4D8;--frontier:#F2B740;--route:#34D399;--routeHi:#A7F3D0;--current:#F75A68;--central:#A78BFA;--hosp:#F87171;--clinic:#FBBF24;--off:#6B7280;--label:#E6EAF2}
:root[data-theme="claro"]{--bg:#FFFFFF;--panel:#F3F5F9;--panel2:#EEF2F7;--border:#D5DCE6;--text:#18212F;--muted:#5B6878;--accent:#2563EB;--btnHover:#E1E9F7;--ctlBg:rgba(255,255,255,.92);--hintBg:rgba(255,255,255,.85);
--map:#F7F9FC;--street:#B9C3D0;--node:#5B6B80;--explored:#2F6FDB;--frontier:#D98E04;--route:#10A26F;--routeHi:#065F46;--current:#DC3545;--central:#7C3AED;--hosp:#DC2626;--clinic:#E08A00;--off:#9CA3AF;--label:#18212F}
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
.tip{position:absolute;z-index:3;pointer-events:none;background:var(--panel);color:var(--text);border:1px solid var(--border);border-radius:9px;padding:6px 9px;font-size:12.5px;box-shadow:0 6px 18px rgba(0,0,0,.25);max-width:260px;display:none}.tip b{display:block;margin-bottom:2px}.tip span{color:var(--muted)}
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
<label class="lbl speed">Velocidade <input id="speed" type="range" min="1" max="60" value="6"><span id="speedText">6/s</span></label><span class="spacer"></span><label class="lbl"><input id="showNodes" type="checkbox"> Mostrar vértices</label></div>
<div class="stats"><span class="chip opt">Vértices<strong id="nv">0</strong></span><span class="chip opt">Arestas<strong id="ne">0</strong></span><span class="chip">Iteração<strong id="count">0 / 0</strong></span><span class="chip">Alcançados<strong id="visited">—</strong></span><span class="chip">Relaxadas<strong id="frontier">—</strong></span><span class="chip">Rota destacada<strong id="cost">—</strong></span><span class="chip opt">Cálculo<strong id="time">—</strong></span></div>
<div class="mapWrap" id="wrap"><canvas id="map" aria-label="Mapa do grafo: linhas são as arestas (ruas). Arraste para mover; use a roda ou a pinça para aproximar."></canvas>
<div class="mapCtl"><button id="zoomIn" title="Aproximar" aria-label="Aproximar">+</button><button id="zoomOut" title="Afastar" aria-label="Afastar">−</button><button id="fit" title="Enquadrar" aria-label="Enquadrar">⤢</button></div>
<div class="tip" id="tip"></div>
<div class="hint">Arraste para mover · roda/pinça para zoom · clique num hospital para destacar a rota</div></div>
<div class="legend"><span><i class="key" style="border-color:var(--street)"></i>ruas</span><span><i class="dot" style="background:var(--node)"></i>vértices</span><span><i class="key" style="border-color:var(--explored)"></i>relaxadas antes</span><span><i class="key" style="border-color:var(--frontier)"></i>relaxadas nesta iteração</span><span><i class="key" style="border-color:var(--route)"></i>rotas central → hospitais</span><span><i class="dot" style="background:var(--central)"></i>central</span><span><i class="dot" style="background:var(--hosp)"></i>hospital</span><span><i class="dot" style="background:var(--clinic)"></i>clínica/UPA</span></div>
<div class="bar"><label class="lbl destSel">Rota destacada <select id="dest" aria-label="Rota destacada"></select></label><label class="seek">Iteração <input id="seek" type="range" min="0" max="0" value="0"></label><button id="car" disabled>🚚 Animar entrega</button></div>
<div id="info" class="info" aria-live="polite"></div>
<script>
(()=>{'use strict';
const data=Object.assign({passos:[],geo:[],rotas:[],pontos:[],central:null,duracao:null,iteracoes:null,criterio:'length'},/*GRAFO*/,/*BUSCA*/,/*EXTRA*/);const $=id=>document.getElementById(id);const cvs=$('map'),ctx=cvs.getContext('2d');
const css=getComputedStyle(document.documentElement);const C=n=>css.getPropertyValue('--'+n).trim();
const COL={};for(const k of['map','street','node','explored','frontier','route','routeHi','current','central','hosp','clinic','off','label'])COL[k]=C(k);
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
const cells=new Map();const cell=(i,j)=>{const k=i*G+j;let c=cells.get(k);if(!c){c={s:new Path2D(),n:new Path2D(),bb:[Infinity,Infinity,-Infinity,-Infinity]};cells.set(k,c)}return c};
const grow=(bb,x,y)=>{if(x<bb[0])bb[0]=x;if(y<bb[1])bb[1]=y;if(x>bb[2])bb[2]=x;if(y>bb[3])bb[3]=y};
for(const via of data.vias){if(via.length<2)continue;const pts=via.map(W);const m=pts[pts.length>>1];const [i,j]=cellOf(m[0],m[1]);const c=cell(i,j);c.s.moveTo(pts[0][0],pts[0][1]);grow(c.bb,pts[0][0],pts[0][1]);for(let t=1;t<pts.length;t++){c.s.lineTo(pts[t][0],pts[t][1]);grow(c.bb,pts[t][0],pts[t][1])}}
for(const id in data.nodes){const q=W(data.nodes[id]);const [i,j]=cellOf(q[0],q[1]);const c=cell(i,j);c.n.moveTo(q[0],q[1]);c.n.lineTo(q[0]+1e-4,q[1]);grow(c.bb,q[0],q[1])}
const cellList=[...cells.values()];
function visibleCells(){const a=inv(0,0),z=inv(size.w,size.h),pad=8/S();return cellList.filter(c=>c.bb[2]>=a[0]-pad&&c.bb[0]<=z[0]+pad&&c.bb[3]>=a[1]-pad&&c.bb[1]<=z[1]+pad)}

/* ---- central, hospitais e rotas ---- */
const central=data.central?{...data.central,w:W([data.central.lon,data.central.lat])}:null;
const pontos=data.pontos.map((p,i)=>({...p,i,w:W([p.lon,p.lat])}));
const temRotas=data.rotas.some(r=>r&&r.length>1);
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
let carPlaying=false,carPos=0,hover=null;
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
ctx.setTransform(dpr,0,0,dpr,0,0);
if(frame>0&&passos[frame-1].atual&&data.nodes[passos[frame-1].atual]){const [x,y]=toScr(W(data.nodes[passos[frame-1].atual]));ctx.beginPath();ctx.arc(x,y,6,0,2*Math.PI);ctx.fillStyle=COL.current;ctx.fill()}
for(const p of pontos)if(p!==pDest)drawPonto(p);if(pDest)drawPonto(pDest);drawCentral();
if(done()&&(carPlaying||carPos>0)&&rotaHiW.length){const k=Math.max(0,Math.min(rotaHiW.length-1,Math.floor(carPos)));const [x,y]=toScr(rotaHiW[k]);ctx.font='22px system-ui';ctx.fillText('🚚',x-12,y-8)}
updateUI()}
let pending=false;function schedule(){if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;paint()})}}

function updateUI(){$('count').textContent=frame+' / '+passos.length;const pa=frame?passos[frame-1]:null;
$('visited').textContent=pa&&pa.visitados!=null?fmt(pa.visitados):'—';$('frontier').textContent=pa&&pa.fila!=null?fmt(pa.fila):'—';
$('cost').textContent=pDest&&pDest.rotulo?pDest.rotulo:'—';$('time').textContent=data.duracao!=null?data.duracao.toFixed(2)+' s':'—';
$('seek').value=frame;$('car').disabled=!done()||!rotaHiW.length;
let t;if(!temBusca&&!pontos.length)t='Grafo carregado: '+fmt(data.qtd_vertices)+' vértices e '+fmt(data.qtd_arestas)+' arestas. Escolha a central e clique em Calcular com Bellman-Ford.';
else if(!temBusca)t=pontos.length+' estabelecimentos no mapa. Clique em Calcular com Bellman-Ford para traçar as rotas.';
else if(frame===passos.length)t='Bellman-Ford convergiu em '+(data.iteracoes||passos.length)+' iterações ('+passos.length+' com relaxações'+(data.iteracoes>passos.length?' + a última, sem mudanças, que confirma':'')+')'+(pDest?' · destaque: '+pDest.nome+(pDest.rotulo?' — '+pDest.rotulo:''):'')+'. Use Reiniciar/Reproduzir para ver as relaxações.';
else if(pa){const extra=Object.entries(pa.info||{}).map(([k,v])=>k+' = '+fmt(v)).join(' | ');t=extra||('Passo '+frame)}
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
$('showNodes').onchange=schedule;

/* ---- dica ao passar o mouse ---- */
const tip=$('tip');
function hit(x,y){let best=null,bd=14*14;for(const p of pontos){const [px,py]=toScr(p.w),d=(px-x)**2+(py-y)**2;if(d<bd){bd=d;best=p}}if(central){const [px,py]=toScr(central.w),d=(px-x)**2+(py-y)**2;if(d<bd)best={central:true}}return best}
function showTip(x,y){const h=hit(x,y);const novo=h&&!h.central?h:null;if(novo!==hover){hover=novo;schedule()}cvs.classList.toggle('hover',!!h);
if(!h){tip.style.display='none';return}
tip.innerHTML=h.central?'<b>'+esc(central.nome||'Central')+'</b><span>Central de distribuição de remédios</span>':'<b>'+esc(h.nome)+'</b><span>'+(h.tipo==='hospital'?'Hospital':'Clínica/UPA/UAI')+(h.rotulo?' · '+esc(h.rotulo):'')+(h.alcancavel===false?' · sem rota':'')+'</span>';
tip.style.display='block';const r=$('wrap').getBoundingClientRect(),tw=tip.offsetWidth,th=tip.offsetHeight;tip.style.left=Math.min(r.width-tw-6,x+14)+'px';tip.style.top=Math.max(6,y-th-10)+'px'}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---- zoom/arrastar (mouse e toque) ---- */
function zoomAt(f,x=size.w/2,y=size.h/2){const a=inv(x,y);view.scale*=f;clampView();const s=S();view.cx=a[0]-(x-size.w/2)/s;view.cy=a[1]-(y-size.h/2)/s;clampView();schedule()}
let anim=0;function animateTo(target){cancelAnimationFrame(anim);const from={...view},t0=performance.now();const step=t=>{const k=Math.min(1,(t-t0)/260),e=1-Math.pow(1-k,3);view.cx=from.cx+(target.cx-from.cx)*e;view.cy=from.cy+(target.cy-from.cy)*e;view.scale=from.scale*Math.pow(target.scale/from.scale,e);paint();if(k<1)anim=requestAnimationFrame(step)};anim=requestAnimationFrame(step)}
function smoothZoom(f){animateTo({...view,scale:Math.min(80,Math.max(.6,view.scale*f))})}
$('zoomIn').onclick=()=>smoothZoom(1.6);$('zoomOut').onclick=()=>smoothZoom(1/1.6);$('fit').onclick=()=>animateTo({cx:0,cy:0,scale:1});
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
const endPtr=e=>{const p=rel(e),moved=gest&&gest.t==='pan'&&Math.hypot(p.x-gest.x,p.y-gest.y)>4;pts.delete(e.pointerId);startGesture();if(!moved){const h=hit(p.x,p.y);if(h&&!h.central){setDest(h.i);schedule()}if(e.pointerType!=='mouse')showTip(p.x,p.y)}};
cvs.addEventListener('pointerup',endPtr);cvs.addEventListener('pointercancel',endPtr);cvs.addEventListener('pointerleave',()=>{if(!gest){tip.style.display='none';if(hover){hover=null;schedule()}}});
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;if(e.key==='+'||e.key==='=')smoothZoom(1.6);else if(e.key==='-')smoothZoom(1/1.6);else if(e.key==='0')animateTo({cx:0,cy:0,scale:1})});

{const k=pontos.findIndex(p=>p.alcancavel!==false);setDest(k>=0?k:null)}
if(window.ResizeObserver)new ResizeObserver(resize).observe($('wrap'));else window.addEventListener('resize',resize);
resize();if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)$('speed').value=1;
})();
</script></body></html>'''
