"""
montar_documentacao.py — Monta a documentacao final (HTML -> PDF) a partir dos resultados reais.

Preenche docs/fonte/documentacao.html com: diagrama, resultados de evidencias/cenarios.json, capturas de
tela, exemplo de contexto e arvore do repositorio; depois imprime o PDF com o Edge (Playwright).

Uso: python docs/montar_documentacao.py [--repo https://github.com/usuario/forzy-assistente]
"""
import argparse
import html
import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistente import ids_citados  # noqa: E402
from analises_cenarios import ANALISES, MANUAL, PENDENCIAS, PROBLEMAS

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
EV = RAIZ / "evidencias"
TIPOS = {"llm": "Resposta gerada (RAG + LLM)", "insuficiente": "Informação insuficiente (sem LLM)",
         "esclarecimento": "Pedido de esclarecimento (sem LLM)", "ativo_inexistente": "Ativo inexistente (sem LLM)",
         "erro": "Erro"}


def md(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", t)
    return t


def arvore() -> str:
    ignorar = {"__pycache__", "logs", ".git", ".venv"}
    linhas = ["forzy-assistente/"]

    def rec(p: Path, pref: str):
        itens = sorted([x for x in p.iterdir() if x.name not in ignorar and not x.name.endswith(".pyc")],
                       key=lambda x: (x.is_file(), x.name.lower()))
        for i, x in enumerate(itens):
            ult = i == len(itens) - 1
            linhas.append(f"{pref}{'└── ' if ult else '├── '}{x.name}{'/' if x.is_dir() else ''}")
            if x.is_dir() and x.name not in {"evidencias", "docs_tecnicos", "notebooks"}:
                rec(x, pref + ("    " if ult else "│   "))
            elif x.is_dir():
                n = len(list(x.iterdir()))
                linhas[-1] += f"  ({n} arquivos)"
    rec(RAIZ, "")
    return html.escape("\n".join(linhas))


def montar(repo: str) -> Path:
    src = (DOCS / "fonte" / "documentacao.html").read_text(encoding="utf-8")
    cen = json.loads((EV / "cenarios.json").read_text(encoding="utf-8"))
    ok = sum(v["status"] == "APROVADO" for v in cen.values())
    okm = sum(MANUAL.get(k, ("",))[0] == "ok" for k in cen)
    resumo = (f"{ok} de {len(cen)} aprovados nas verificações automáticas; {okm} de {len(cen)} corretos "
              f"na avaliação manual")

    tab = ["<table><tr><th>ID</th><th>Cenário</th><th>Tipo de resposta</th><th>Tempo</th>"
           "<th>Fontes (citadas/consultadas)</th><th>Verificação automática</th><th>Avaliação manual</th></tr>"]
    blocos = []
    for k, v in cen.items():
        r = v["resultado"]
        r["citadas"] = ids_citados(r["resposta"], [f["id"] for f in r["fontes"]])
        st = "ok" if v["status"] == "APROVADO" else "nao"
        nf = len(r["fontes"])
        tab.append(f"<tr><td>{k}</td><td>{html.escape(v['nome'])}</td><td>{TIPOS[r['tipo']]}</td>"
                   f"<td>{r['segundos']:.1f} s</td><td>{len(r['citadas'])}/{nf}</td>"
                   f"<td><span class='tag {st}'>{v['status'].title()}</span></td>"
                   f"<td><span class='tag {MANUAL.get(k, ('parc', 'Pendente'))[0]}'>{MANUAL.get(k, ('parc', 'Pendente'))[1]}</span></td></tr>")
        resp = r["resposta"].split("\n\n**Fontes consultadas:**")[0]
        fontes = ", ".join(f"<code>{f['id']}</code>{' ✅' if f['id'] in r['citadas'] else ''}"
                           for f in r["fontes"]) or "nenhuma (resposta determinística)"
        falhas = "; ".join(v["falhas"]) or "todas atendidas"
        blocos.append(f"""<div class="cenario">
<h3>{k} — {html.escape(v['nome'])}</h3>
<table>
<tr><td style="width:19%"><b>Entrada</b></td><td>“{html.escape(v['pergunta'])}”</td></tr>
<tr><td><b>Resultado esperado</b></td><td>{html.escape(v['esperado'])}</td></tr>
<tr><td><b>Execução</b></td><td>{TIPOS[r['tipo']]} · {r['segundos']:.1f} s · período: {html.escape(r['periodo'] or '—')}
{(' · modelo: <code>' + r['modelo'] + '</code>') if r['modelo'] else ''}</td></tr>
<tr><td><b>Fontes</b></td><td>{fontes} <span class="pequeno">(✅ = citada no texto)</span></td></tr>
<tr><td><b>Verificações</b></td><td>Automática: <span class="tag {'ok' if v['status'] == 'APROVADO' else 'nao'}">{v['status'].title()}</span> {html.escape(falhas)} · Manual: <span class="tag {MANUAL.get(k, ('parc', 'Pendente'))[0]}">{MANUAL.get(k, ('parc', 'Pendente'))[1]}</span></td></tr>
</table>
<p style="margin:4px 0 2px"><b>Resultado obtido</b> (resposta transcrita):</p>
<div class="resp">{md(resp)}</div>
<p style="margin-top:6px"><b>Análise da equipe.</b> {ANALISES.get(k, '')}</p>
</div>""")
    tab.append("</table>")

    capturas = ""
    telas = [("tela_02_fontes_consultadas.png", "Consulta sobre o MOT-008 (execução independente dos testes da seção 7): barra lateral com ativo em foco, modelo, estado do Ollama e exemplos; resposta com aviso profissional e painel “Fontes consultadas” expandido, com tipo, relevância e indicação das fontes citadas."),
             ("tela_03_ambigua_insuficiente.png", "Pergunta ambígua (pedido de esclarecimento) e pergunta fora do escopo (informação insuficiente)."),
             ("tela_04_painel_frota.png", "Aba “Painel da frota”: ranking de ativos e séries de percentil de anomalia e de sensor.")]
    n = 1
    for arq, leg in telas:
        if (EV / arq).exists():
            capturas += (f'<figure><img src="../../evidencias/{arq}" style="width:{"74" if "02" in arq else "92"}%">'
                         f'<figcaption>Figura 6.{n} — {leg}</figcaption></figure>\n')
            n += 1
    if not capturas:
        capturas = '<div class="alerta">Capturas de tela não geradas: execute testes/capturar_telas.py.</div>'

    c1 = cen.get("C1", {}).get("resultado", {}).get("contexto", "")
    exemplo = "\n\n".join(b for b in c1.split("\n\n") if b.startswith(("[D1]", "[M1]")))

    svg = (DOCS / "diagrama_arquitetura.svg").read_text(encoding="utf-8")
    out = (src.replace("{{REPO_URL}}", html.escape(repo))
              .replace("{{RESUMO_CENARIOS}}", resumo)
              .replace("{{DIAGRAMA}}", svg)
              .replace("{{EXEMPLO_CONTEXTO}}", html.escape(exemplo))
              .replace("{{CAPTURAS}}", capturas)
              .replace("{{TABELA_CENARIOS}}", "\n".join(tab))
              .replace("{{CENARIOS}}", "\n".join(blocos))
              .replace("{{PENDENCIAS}}", PENDENCIAS)
              .replace("{{PROBLEMAS}}", PROBLEMAS)
              .replace("{{ARVORE}}", arvore()))
    assert "{{" not in out, re.findall(r"\{\{\w+\}\}", out)
    dest = DOCS / "fonte" / "documentacao_montada.html"
    dest.write_text(out, encoding="utf-8")
    return dest


def pdf(html_path: Path) -> Path:
    from playwright.sync_api import sync_playwright
    dest = DOCS / "Documentacao_Final_Sprint4_Grupo4M.pdf"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page()
        pg.goto(html_path.resolve().as_uri(), wait_until="load")
        pg.wait_for_timeout(800)
        pg.pdf(path=str(dest), format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=True,
               header_template="<div></div>",
               footer_template=("<div style='font-size:7.5pt;color:#888;width:100%;padding:0 18mm;"
                                "display:flex;justify-content:space-between'><span>Grupo 4M · FIAP × Forzy · "
                                "Sprint 4 — Documentação Final</span><span><span class='pageNumber'></span>/"
                                "<span class='totalPages'></span></span></div>"),
               margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"})
        b.close()
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="https://github.com/<usuario>/forzy-assistente")
    a = ap.parse_args()
    h = montar(a.repo)
    print("HTML:", h)
    print("PDF :", pdf(h))
