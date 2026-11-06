"""
assistente.py — Orquestrador do assistente conversacional de manutencao (RAG + modelos)
FIAP x Forzy | Challenge IA | Grupo 4M

Fluxo de uma pergunta:
  1. Interpretacao: identifica ativos (MOT-xxx), periodo e intencao (status, historico, procedimento, frota)
  2. Guardas deterministicas: ativo inexistente, pergunta ambigua (pede esclarecimento)
  3. Contexto operacional: sensores x baseline, detector de anomalias (Sprint 3),
     classificador de falhas (Sprint 2), historico de ordens de servico
  4. Recuperacao (RAG): trechos de documentos tecnicos filtrados por ativo, consulta enriquecida
     com a falha provavel e o sensor de maior desvio
  5. Guarda de suficiencia: sem dado operacional e sem trecho relevante -> resposta de "informacao insuficiente"
  6. Geracao: LLM com instrucoes de citacao de fontes, incerteza e seguranca
  7. Pos-processamento: aviso obrigatorio de avaliacao profissional em situacoes criticas + log

Uso:
    python src/assistente.py "Como esta o MOT-008?"
    python src/assistente.py            # chat no terminal
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import dados_operacionais as dop
import llm
import rag

RAIZ = Path(__file__).resolve().parents[1]
LOG = RAIZ / "logs" / "conversas.jsonl"

AVISO_PROFISSIONAL = ("⚠️ **Avaliação profissional obrigatória:** a situação envolve severidade crítica ou risco "
                      "à segurança. As indicações acima apoiam a investigação, mas a decisão de parada, "
                      "intervenção ou liberação deve ser tomada por profissional habilitado (NR-10/NR-12), "
                      "conforme DOC-006.")

SYSTEM = """Você é o assistente de manutenção preditiva da Forzy para a frota de motores elétricos MOT-001 a MOT-020.
Responda em português, de forma técnica e objetiva (no máximo 220 palavras).

REGRAS:
1. Use SOMENTE as informações do CONTEXTO. Não invente valores, peças, normas ou procedimentos.
2. Cite as fontes entre colchetes logo após cada afirmação, usando exatamente os IDs do contexto, ex.: [D1], [M1], [H2], [DOC-003#3].
3. Se o contexto não tiver a informação pedida, diga claramente o que não foi encontrado.
4. Um alerta de anomalia indica prioridade de inspeção, NÃO falha confirmada. O percentil NÃO é probabilidade de falha. O "sensor de maior desvio" é uma heurística, não prova de causa.
5. Se o classificador estiver incerto (confiança < 60%), diga isso e trate o diagnóstico como hipótese.
6. Nunca oriente religar, desmontar ou intervir eletricamente; intervenções são feitas por profissional habilitado.
7. Não crie números (percentuais, confianças, limites) que não estejam no contexto. Ao listar vários ativos, descreva cada um com os seus próprios dados, sem generalizar.
8. Os dados são simulados (base sintética do projeto); não é preciso repetir isso em toda frase.

FORMATO (use apenas as seções que se aplicam à pergunta):
**Situação:** o que os dados e os modelos mostram.
**Diagnóstico provável:** hipótese e grau de confiança.
**Ações recomendadas:** passos do procedimento técnico, em lista curta.
"""

PALAVRAS_SEGURANCA = ["fumaca", "fumaça", "cheiro de queimado", "queimado", "faisca", "faísca", "choque",
                      "pegando fogo", "fogo", "energizado", "religar", "isolamento"]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# ---------------------------------------------------------------- interpretacao
def extrair_ativos(q: str) -> tuple[list[str], list[str]]:
    qn = _norm(q)
    nums = re.findall(r"\bmot[\s\-_]?0*(\d{1,3})\b", qn) + re.findall(r"\bmotor(?:es)?\s+(?:n[o.]?\s*)?0*(\d{1,3})\b", qn)
    validos, invalidos = [], []
    for n in dict.fromkeys(nums):
        tag = f"MOT-{int(n):03d}"
        (validos if tag in dop.ativos() else invalidos).append(tag)
    return validos, invalidos


MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def extrair_periodo(q: str) -> dict:
    """Retorna {'sensores': (ini, fim) | None, 'os': (date, date) | None, 'fora_da_base': bool, 'descricao': str}."""
    qn = _norm(q)
    ini_base, fim_base = dop.periodo_dados()
    dia = ini_base.date()
    out = {"sensores": None, "os": None, "fora_da_base": False, "descricao": "últimos 30 min da base"}

    def hm(h, m):
        return datetime.combine(dia, datetime.min.time()) + timedelta(hours=int(h), minutes=int(m or 0))

    m = re.search(r"(?:entre|das|de)\s+(\d{1,2})(?:[:h](\d{2}))?\s*h?\s*(?:e|as|a|ate)\s+(?:as\s+)?(\d{1,2})(?:[:h](\d{2}))?", qn)
    if m:
        out["sensores"] = (hm(m[1], m[2]), hm(m[3], m[4]))
    elif (m := re.search(r"\bas\s+(\d{1,2})[:h](\d{2})", qn)):
        t = hm(m[1], m[2])
        out["sensores"] = (t - timedelta(minutes=5), t + timedelta(minutes=5))
    elif (m := re.search(r"ultim[oa]s?\s+(\d+)?\s*(minutos?|horas?)", qn)):
        n = int(m[1] or 1)
        delta = timedelta(hours=n) if m[2].startswith("hora") else timedelta(minutes=n)
        out["sensores"] = (fim_base - delta, fim_base)
    elif re.search(r"\b(hoje|dia todo|todo o periodo|desde o inicio|01/05)\b", qn):
        out["sensores"] = (ini_base, fim_base)
    if out["sensores"]:
        a, b = out["sensores"]
        out["descricao"] = f"{a:%d/%m %H:%M} a {b:%d/%m %H:%M}"

    meses = [v for k, v in MESES.items() if re.search(rf"\b{k}\b", qn)]
    if meses:
        ano = int(m[1]) if (m := re.search(r"\b(20\d\d)\b", qn)) else 2026
        mes = meses[0]
        fim_mes = date(ano + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)
        out["os"] = (date(ano, mes, 1), fim_mes)
        out["descricao"] = f"{mes:02d}/{ano} (histórico de OS)"
        if not (mes == 5 and ano == 2026):
            out["fora_da_base"] = True     # sensores so existem em 01/05/2026
    if re.search(r"\b(ontem|semana passada|mes passado|ano passado|amanha|proxima semana)\b", qn):
        out["fora_da_base"] = True
    return out


def intencoes(q: str) -> set[str]:
    qn = _norm(q)
    it = set()
    if re.search(r"historic|manutenc|ordem de servico|\bos\b|intervenc|ja teve|ultima troca|ja foi", qn):
        it.add("historico")
    if re.search(r"\bcomo (resolver|corrigir|proceder|fazer|verificar)|procedimento|o que fazer|o que verificar|"
                 r"causa|passo|devo|recomend|troubleshoot|investig", qn):
        it.add("procedimento")
    if re.search(r"como esta|situac|status|estado|leitura|valores|anomal|alerta|esta normal|com problema|"
                 r"temperatura|vibrac|corrente|rotac|sensor|falha|diagnost|o que (esta acontecendo|houve)", qn):
        it.add("status")
    if re.search(r"quais motores|frota|ranking|mais critic|prioridad|todos os motores|algum motor|qual motor|"
                 r"quais ativos|qual ativo", qn):
        it.add("frota")
    if re.search(r"\b(esse|este|ele|dele|desse|deste|nele|mesmo motor)\b", qn):
        it.add("referencia_implicita")
    return it


# ---------------------------------------------------------------- contexto
def _bloco_ativo(i: int, r: dict) -> tuple[str, str]:
    s = r["sensores"]
    linhas = [f"Ativo {r['tag']} | período {r['inicio']} a {r['fim']} ({r['n_leituras']} leituras de 30 s)"]
    for k, v in s.items():
        linhas.append(f"- {v['nome']}: atual {v['atual']} {v['unidade']} (média {v['media']}, mín {v['min']}, "
                      f"máx {v['max']}); faixa normal do baseline {v['faixa_normal'][0]}–{v['faixa_normal'][1]} "
                      f"{v['unidade']}; desvio atual {v['desvio_padronizado_atual']:+} desvios-padrão")
    a, c = r["anomalia"], r["classificador"]
    mod = [f"Detector de anomalias (Isolation Forest temporal) para {r['tag']}:",
           f"- última leitura {a['ultima_leitura']}: percentil {a['percentil_atual']}, severidade {a['severidade_atual']}, "
           f"persistência {a['persistencia_atual']}, sensor de maior desvio: {a['sensor_maior_desvio_atual']}",
           f"- alertas no período: {a['alertas_no_periodo']} de {r['n_leituras']} leituras "
           f"({a['taxa_alertas_periodo_pct']}%); primeiro alerta no período: {a['primeiro_alerta'] or 'nenhum'}; "
           f"sequência de alertas em curso desde: {a['inicio_sequencia_atual'] or 'sem alerta atual'}; "
           f"severidade máxima: {a['severidade_maxima']}",
           f"Classificador de falhas conhecidas (Random Forest) na última leitura: {c['classe']} "
           f"com confiança {c['confianca']:.0%}{' (INCERTO)' if c['incerto'] else ''}; distribuição "
           + ", ".join(f"{k} {v:.0%}" for k, v in c["distribuicao"].items())]
    return "\n".join(linhas), "\n".join(mod)


def _bloco_os(o: dict) -> str:
    return (f"{o['os_id']} | {o['tag']} | {o['tipo']} | aberta {o['data_abertura']}"
            f"{' fechada ' + o['data_fechamento'] if o['data_fechamento'] else ''} | status {o['status']} | "
            f"falha: {o['falha_relacionada']} | {o['descricao']} | causa raiz: {o['causa_raiz']} | ação: {o['acao']} | "
            f"parada {o['horas_parada']} h")


@dataclass
class Resposta:
    pergunta: str
    resposta: str
    tipo: str                       # llm | esclarecimento | insuficiente | ativo_inexistente | erro
    ativos: list[str] = field(default_factory=list)
    periodo: str = ""
    fontes: list[dict] = field(default_factory=list)
    contexto: str = ""
    aviso_profissional: bool = False
    modelo: str = ""
    segundos: float = 0.0
    citadas: list[str] = field(default_factory=list)


def responder(pergunta: str, ativo_ui: str | None = None, sessao: dict | None = None,
              usar_llm: bool = True) -> Resposta:
    t0 = time.time()
    sessao = sessao if sessao is not None else {}
    tags, invalidos = extrair_ativos(pergunta)
    per = extrair_periodo(pergunta)
    it = intencoes(pergunta)
    nota_ativo = ""

    if invalidos and not tags:
        return _fim(Resposta(pergunta, (
            f"Não encontrei o ativo {', '.join(invalidos)} na base monitorada. Os ativos disponíveis são "
            f"MOT-001 a MOT-020. Verifique a tag e refaça a pergunta."), "ativo_inexistente", invalidos), t0)

    if not tags and ativo_ui:
        tags = [ativo_ui]
    if not tags and "referencia_implicita" in it and sessao.get("ultimo_ativo"):
        tags = [sessao["ultimo_ativo"]]
        nota_ativo = f"(Considerei o ativo {tags[0]}, citado anteriormente na conversa.)\n\n"

    precisa_ativo = bool(it & {"status", "historico", "referencia_implicita"}) and "frota" not in it
    if not tags and precisa_ativo and not ("procedimento" in it and "historico" not in it
                                           and "referencia_implicita" not in it):
        return _fim(Resposta(pergunta, (
            "Para responder preciso saber **qual ativo** você quer consultar. Informe a tag do motor "
            "(MOT-001 a MOT-020), por exemplo: *\"Como está o MOT-008 na última hora?\"*. "
            "Se quiser uma visão geral, pergunte: *\"Quais motores estão mais críticos agora?\"*"),
            "esclarecimento"), t0)

    blocos, fontes = [], []
    aviso = any(p in _norm(pergunta) for p in map(_norm, PALAVRAS_SEGURANCA))
    termos_extra = []

    if per["fora_da_base"]:
        ini, fim = dop.periodo_dados()
        blocos.append(("P1", f"AVISO: a pergunta cita um período sem leituras de sensores. Só há leituras de "
                             f"{ini:%d/%m/%Y %H:%M} a {fim:%d/%m/%Y %H:%M}; para o período citado só é "
                             f"possível consultar o histórico de ordens de serviço."))
        fontes.append({"id": "P1", "tipo": "cobertura da base", "titulo": "Período coberto pelos sensores",
                       "texto": blocos[-1][1]})
        it.add("historico")
    for i, tag in enumerate(tags[:3], 1):
        ini, fim = per["sensores"] or (None, None)
        r = None if per["fora_da_base"] else dop.resumo_ativo(tag, ini, fim)
        if r and not r.get("sem_dados"):
            d, m = _bloco_ativo(i, r)
            blocos += [(f"D{i}", d), (f"M{i}", m)]
            fontes += [{"id": f"D{i}", "tipo": "dados de sensores", "titulo": f"Leituras de {tag}", "texto": d},
                       {"id": f"M{i}", "tipo": "resultado de modelo", "titulo": f"Modelos de IA — {tag}", "texto": m}]
            if r["anomalia"]["severidade_atual"] == "Crítica":
                aviso = True
            if r["anomalia"]["alerta_atual"]:
                c = r["classificador"]
                termos_extra += [c["classe"] if not c["incerto"] else "",
                                 r["anomalia"]["sensor_maior_desvio_atual"]]
        elif r and r.get("sem_dados"):
            blocos.append((f"D{i}", f"Não há leituras de {tag} no período solicitado ({per['descricao']})."))
        hist = dop.historico_os(tag, *(per["os"] or (None, None)))
        if "historico" in it or "procedimento" in it or (r and r["anomalia"]["alerta_atual"] if r and not r.get("sem_dados") else False):
            if hist:
                for j, o in enumerate(hist[-4:], 1):
                    hid = f"H{i}.{j}" if len(tags) > 1 else f"H{j}"
                    txt = _bloco_os(o)
                    blocos.append((hid, txt))
                    fontes.append({"id": hid, "tipo": "histórico de manutenção", "titulo": o["os_id"], "texto": txt})
            elif "historico" in it:
                blocos.append((f"H{i}", f"Nenhuma ordem de serviço registrada para {tag} no período consultado."))
    if tags:
        sessao["ultimo_ativo"] = tags[0]

    if "frota" in it and not tags:
        ini, fim = per["sensores"] or (None, None)
        rk = dop.ranking_frota(ini, fim)
        txt = "Ranking da frota (prioridade: taxa de alertas, severidade atual, percentil médio):\n" + "\n".join(
            f"{n}. {x['tag']}: {x['taxa_alertas_pct']}% das leituras em alerta, percentil médio {x['percentil_medio']}, "
            f"severidade atual {x['ultima_severidade']}, sensor de maior desvio {x['sensor_principal']}"
            for n, x in enumerate(rk, 1))
        blocos.append(("R1", txt))
        fontes.append({"id": "R1", "tipo": "resultado de modelo", "titulo": "Ranking de ativos", "texto": txt})

    consulta = pergunta + " " + " ".join(t for t in termos_extra if t)
    docs = rag.carregar_indice().buscar(consulta, k=3, ativo=tags[0] if tags else None,
                                        incluir_os=not tags, periodo=per["os"])
    for d in docs:
        blocos.append((d["chunk_id"], f"{d['titulo']} — {d['secao']}: {d['texto']}"))
        fontes.append({"id": d["chunk_id"], "tipo": "documento técnico" if d["tipo"] != "ordem_servico"
                       else "histórico de manutenção", "titulo": f"{d['titulo']} — {d['secao']}",
                       "texto": d["texto"], "score": d["score"], "origem": d["origem"]})

    tem_operacional = any(b[0][0] in "DMR" and not b[1].startswith("Não há") for b in blocos) or \
        any(b[0][0] == "H" and not b[1].startswith("Nenhuma") for b in blocos)
    if not docs and not tem_operacional:
        motivo = ("o período solicitado está fora da base de sensores" if per["fora_da_base"]
                  else "não há dados operacionais nem trechos de documentação relevantes para a pergunta")
        msg = (f"Não encontrei informações suficientes para responder com segurança: {motivo}.\n\n"
               "Posso ajudar com: situação dos sensores e alertas de um motor (MOT-001 a MOT-020), "
               "diagnóstico provável de falhas conhecidas, histórico de ordens de serviço, ranking da frota e "
               "procedimentos de troubleshooting dos documentos técnicos indexados. "
               "Se a informação existir em outra fonte, ela precisa ser incluída na base documental.")
        return _fim(Resposta(pergunta, nota_ativo + msg, "insuficiente", tags, per["descricao"],
                             contexto="\n\n".join(f"[{k}] {v}" for k, v in blocos)), t0)

    contexto = "\n\n".join(f"[{k}] {v}" for k, v in blocos)
    res = Resposta(pergunta, "", "llm", tags, per["descricao"], fontes, contexto, aviso)
    if not usar_llm:
        res.resposta = "(geração desativada)"
        return _fim(res, t0)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nPERGUNTA: {pergunta}\n\n"
                                        "Responda usando só o CONTEXTO e coloque o ID da fonte entre colchetes "
                                        "ao final de cada frase, ex.: [D1], [M1], [H1], [DOC-004#3]."}]
    try:
        g = llm.gerar(msgs)
    except Exception as e:
        res.tipo, res.resposta = "erro", (f"Não foi possível consultar o modelo de linguagem ({e.__class__.__name__}). "
                                          "Verifique se o Ollama está em execução (ollama serve).")
        return _fim(res, t0)
    texto = g["texto"]
    if aviso and "profissional" not in _norm(texto[-400:]):
        texto += "\n\n" + AVISO_PROFISSIONAL
    res.citadas = ids_citados(texto, [f["id"] for f in fontes])
    rodape = "; ".join(f"[{f['id']}] {f['titulo']}" for f in fontes)
    res.resposta = nota_ativo + texto + f"\n\n**Fontes consultadas:** {rodape}"
    res.modelo = g["modelo"]
    return _fim(res, t0)


def ids_citados(texto: str, ids: list[str]) -> list[str]:
    """IDs de fontes citados no texto, aceitando [D1], [H1, H2] e [DOC-004#2]."""
    achados = set()
    for grupo in re.findall(r"\[([^\]]{1,80})\]", texto):
        achados.update(x.strip() for x in re.split(r"[,;]| e ", grupo))
    return sorted(achados & set(ids))


def _fim(res: Resposta, t0: float) -> Resposta:
    res.segundos = round(time.time() - t0, 1)
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), **asdict(res)},
                           ensure_ascii=False) + "\n")
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        r = responder(" ".join(sys.argv[1:]))
        print(r.resposta, "\n\nFontes:", [f["id"] for f in r.fontes], f"| {r.tipo} | {r.segundos}s")
    else:
        sessao = {}
        print("Assistente Forzy — digite 'sair' para encerrar")
        while (q := input("\nVocê: ").strip()).lower() not in {"sair", "exit"}:
            r = responder(q, sessao=sessao)
            print("\nAssistente:", r.resposta, "\nFontes:", [f["id"] for f in r.fontes])
