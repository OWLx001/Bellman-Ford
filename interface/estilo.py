"""Aparência do app: cores dos temas, CSS da página e o script do botão sol/lua."""

CORES = {
    'escuro': dict(panel='#1A1A1D', border='#2E2E33', muted='#9A9AA3', accent='#B4B4BC', hi='rgba(161,161,170,.14)'),
    'claro': dict(panel='#F6F8FB', border='#D5DCE6', muted='#5B6878', accent='#2563EB', hi='rgba(37,99,235,.10)'),
}


def css(tema):
    """Bloco <style> da página (cores do tema escolhido)."""
    c = CORES[tema]
    return f'''<style>
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
/* O Streamlit fixa o bloco em 760 px (flex-basis); deixa ele com a altura real do mapa */
.st-key-mapa [data-testid="stElementContainer"] {{flex:0 0 auto !important; height:auto !important}}
.st-key-mapa iframe {{display:block; border-radius:14px; height:clamp(560px, calc(100vh - 7rem), 900px) !important}}
.st-key-mapa iframe:fullscreen {{width:100vw !important; height:100vh !important; border-radius:0 !important}}
/* Tabela da rota: nomes das ruas quebram linha */
.ranking.rota td {{white-space:normal}}
.ranking.rota td.num {{white-space:nowrap}}
.ranking td.neg {{color:#F43F5E; font-weight:700}}
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
  .ranking.rk th:nth-child(3), .ranking.rk td:nth-child(3), .ranking.rk th:last-child, .ranking.rk td:last-child {{display:none}}
}}
</style>'''


def script_tema(tema):
    """Script que aplica o tema só no navegador de quem está vendo.

    Grava a preferência que o próprio Streamlit lê do localStorage e recarrega a página
    se ela ainda não bate (com proteção para não recarregar em laço).
    """
    alvo = 'Light' if tema == 'claro' else 'Dark'
    return f'''<script>(function(){{
  var P = window.parent;
  try {{
    var k = 'stActiveTheme-' + P.location.pathname + '-v2', alvo = JSON.stringify('{alvo}');
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
