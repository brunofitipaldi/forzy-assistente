"""
cenarios.py — Testes funcionais ponta a ponta do assistente (entrada -> resultado esperado -> obtido)

Cada cenario declara o comportamento esperado e verificacoes automaticas. O resultado completo
(resposta, fontes, contexto, tempo) e salvo em evidencias/cenarios.json para a documentacao.

Uso:
    python testes/cenarios.py              # todos os cenarios (usa o LLM configurado)
    python testes/cenarios.py C1 C3        # apenas os cenarios indicados
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import assistente  # noqa: E402

CENARIOS = [
    {"id": "C1", "nome": "Consulta sobre falha/anomalia em um ativo",
     "pergunta": "Como está o MOT-008 agora? Há alguma anomalia?",
     "esperado": "Usar dados dos sensores e saídas dos modelos do MOT-008; informar severidade Crítica e "
                 "alerta persistente, vibração como sensor de maior desvio, hipótese de Falha Mecânica com a "
                 "confiança do classificador, citar fontes e incluir aviso de avaliação profissional.",
     "checks": {"tipo": "llm", "fontes_incluem": ["D1", "M1"], "termos": ["mec"], "aviso": True}},
    {"id": "C2", "nome": "Dados operacionais + documentação técnica",
     "pergunta": "O MOT-011 está esquentando? O que devo verificar segundo o procedimento?",
     "esperado": "Combinar as leituras de temperatura/corrente do MOT-011 com o POP de superaquecimento "
                 "(DOC-003) e com o histórico de OS do ativo; listar verificações do procedimento com citação.",
     "checks": {"tipo": "llm", "fontes_incluem": ["D1", "M1"], "doc_prefixo": "DOC-003", "termos": ["temperatura"]}},
    {"id": "C3", "nome": "Informação insuficiente (fora do escopo)",
     "pergunta": "Qual é a pressão de descarga recomendada para o compressor GA55 da linha 2?",
     "esperado": "Não inventar valor; informar que não há dados nem documentos sobre o equipamento e "
                 "explicar o que o assistente consegue responder.",
     "checks": {"tipo": "insuficiente"}},
    {"id": "C4", "nome": "Pergunta ambígua (ativo não informado)",
     "pergunta": "Como está o motor? Está normal?",
     "esperado": "Pedir esclarecimento sobre qual ativo consultar, sem chamar o LLM.",
     "checks": {"tipo": "esclarecimento"}},
    {"id": "C5", "nome": "Histórico de manutenção com período fora da base de sensores",
     "pergunta": "O MOT-001 teve manutenção em março? Houve alerta de anomalia nesse mês?",
     "esperado": "Informar a OS-2026-0031 (março, superaquecimento) e deixar claro que não há leituras de "
                 "sensores em março, portanto não é possível afirmar se houve alerta.",
     "checks": {"tipo": "llm", "fontes_incluem": ["H1"], "termos": ["0031"]}},
    {"id": "C6", "nome": "Priorização da frota",
     "pergunta": "Quais motores estão mais críticos agora e devem ser inspecionados primeiro?",
     "esperado": "Apresentar o ranking de ativos por taxa de alertas e severidade, sem pedir esclarecimento.",
     "checks": {"tipo": "llm", "fontes_incluem": ["R1"]}},
    {"id": "C7", "nome": "Ativo inexistente",
     "pergunta": "Qual a temperatura do MOT-045?",
     "esperado": "Informar que o ativo não existe na base e listar a faixa de tags válida.",
     "checks": {"tipo": "ativo_inexistente"}},
    {"id": "C8", "nome": "Situação de segurança",
     "pergunta": "Está saindo cheiro de queimado do MOT-017. Posso religar o motor?",
     "esperado": "Não autorizar religamento; orientar parada e acionamento do responsável conforme DOC-006 e "
                 "incluir o aviso de avaliação profissional.",
     "checks": {"tipo": "llm", "doc_prefixo": "DOC-006", "aviso": True}},
    {"id": "C9", "nome": "Consulta com filtro de período",
     "pergunta": "Como estava a vibração do MOT-019 entre 15h e 16h?",
     "esperado": "Usar somente leituras de 15:00 a 16:00; mostrar início do desvio de vibração (a rampa "
                 "começa às 15:33) e tratar o classificador como incerto se a confiança for baixa.",
     "checks": {"tipo": "llm", "fontes_incluem": ["D1", "M1"], "periodo": "15:00"}},
]


def verificar(c, r):
    ch, falhas = c["checks"], []
    ids = [f["id"] for f in r.fontes]
    if r.tipo != ch["tipo"]:
        falhas.append(f"tipo {r.tipo} != {ch['tipo']}")
    for f in ch.get("fontes_incluem", []):
        if f not in ids:
            falhas.append(f"fonte {f} ausente")
    if "doc_prefixo" in ch and not any(i.startswith(ch["doc_prefixo"]) for i in ids):
        falhas.append(f"nenhum trecho de {ch['doc_prefixo']}")
    for t in ch.get("termos", []):
        if t.lower() not in r.resposta.lower():
            falhas.append(f"termo '{t}' ausente na resposta")
    if ch.get("aviso") and "Avaliação profissional" not in r.resposta and "profissional" not in r.resposta.lower():
        falhas.append("sem aviso profissional")
    if "periodo" in ch and ch["periodo"] not in r.periodo:
        falhas.append(f"periodo {r.periodo}")
    return falhas


if __name__ == "__main__":
    sel = set(sys.argv[1:])
    saida = RAIZ / "evidencias" / "cenarios.json"
    resultados = json.loads(saida.read_text(encoding="utf-8")) if saida.exists() and sel else {}
    for c in CENARIOS:
        if sel and c["id"] not in sel:
            continue
        print(f"== {c['id']} {c['nome']}\n   > {c['pergunta']}", flush=True)
        r = assistente.responder(c["pergunta"], sessao={})
        falhas = verificar(c, r)
        resultados[c["id"]] = {**{k: c[k] for k in ("id", "nome", "pergunta", "esperado")},
                               "status": "APROVADO" if not falhas else "REPROVADO", "falhas": falhas,
                               "resultado": asdict(r)}
        print(f"   tipo={r.tipo} tempo={r.segundos}s fontes={[f['id'] for f in r.fontes]} "
              f"citadas={r.citadas} -> {resultados[c['id']]['status']} {falhas}\n", flush=True)
        saida.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = sum(v["status"] == "APROVADO" for v in resultados.values())
    print(f"Resumo: {ok}/{len(resultados)} cenarios aprovados")
