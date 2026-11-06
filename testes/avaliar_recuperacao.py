"""
avaliar_recuperacao.py — Avaliacao da recuperacao (R do RAG) com consultas rotuladas.

Positivas: consulta -> doc_id esperado. Metricas: Hit@1, Hit@3, MRR.
Negativas: consultas fora do escopo; o melhor score deve ficar abaixo do limiar.

Uso: python testes/avaliar_recuperacao.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import rag  # noqa: E402

POSITIVAS = [
    ("o motor esta esquentando muito, o que verificar?", "DOC-003", None),
    ("corrente acima do nominal e temperatura subindo", "DOC-003", None),
    ("como resolver vibracao alta com rotacao oscilando", "DOC-002", None),
    ("quando fazer balanceamento dinamico do rotor", "DOC-002", None),
    ("ruido metalico no mancal, o que pode ser", "DOC-004", None),
    ("queda de rotacao com vibracao e aquecimento", "DOC-004", None),
    ("tolerancia de alinhamento do acoplamento", "DOC-001", None),
    ("quais sao os limites de alarme de temperatura", "DOC-001", None),
    ("de quanto em quanto tempo relubrificar os rolamentos", "DOC-005", None),
    ("o que fazer se sair fumaca do motor", "DOC-006", None),
    ("quem pode medir o isolamento do enrolamento", "DOC-006", None),
    ("o que significa severidade critica no alerta", "DOC-007", None),
    ("o percentil de anomalia e probabilidade de falha?", "DOC-007", None),
    ("troca de rolamento no historico", "OS-2026-0009", "MOT-008"),
    ("houve problema de tensao de alimentacao", "OS-2026-0029", "MOT-011"),
    ("ventilador trincado", "OS-2026-0026", "MOT-019"),
]
NEGATIVAS = [
    "qual a pressao de descarga do compressor GA55?",
    "quanto custa um motor novo?",
    "receita de bolo de cenoura",
    "qual o consumo de oleo do redutor da esteira 3?",
    "quem ganhou o jogo de ontem?",
    "qual a previsao do tempo para amanha?",
]


def avaliar(idx):
    hits1 = hits3 = mrr = 0.0
    det = []
    for q, esperado, ativo in POSITIVAS:
        res = idx.buscar(q, k=10, ativo=ativo)
        ids = [r["doc_id"] for r in res]
        pos = ids.index(esperado) + 1 if esperado in ids else None
        hits1 += pos == 1
        hits3 += bool(pos and pos <= 3)
        mrr += 1 / pos if pos else 0
        det.append({"consulta": q, "esperado": esperado, "posicao": pos,
                    "top1": ids[0] if ids else "-", "score_top1": res[0]["score"] if res else 0,
                    "melhor_score": round(idx.melhor_score(q), 3)})
    n = len(POSITIVAS)
    neg = [{"consulta": q, "melhor_score": round(idx.melhor_score(q), 3)} for q in NEGATIVAS]
    return {"hit@1": round(hits1 / n, 3), "hit@3": round(hits3 / n, 3), "mrr": round(mrr / n, 3),
            "n_positivas": n, "detalhes": det, "negativas": neg}


if __name__ == "__main__":
    idx = rag.indexar()
    r = avaliar(idx)
    pos_scores = sorted(d["melhor_score"] for d in r["detalhes"])
    neg_scores = sorted(d["melhor_score"] for d in r["negativas"])
    r["menor_score_positivo"] = pos_scores[0]
    r["maior_score_negativo"] = neg_scores[-1]
    r["limiar_usado"] = rag.LIMIAR_DENSO
    r["negativas_bloqueadas"] = sum(s < rag.LIMIAR_DENSO for s in neg_scores)
    out = RAIZ / "evidencias" / "avaliacao_recuperacao.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in r.items() if k != "detalhes"}, indent=2, ensure_ascii=False))
    for d in r["detalhes"]:
        print(f"  pos={d['posicao']}  top1={d['top1']:13s} max={d['melhor_score']:.3f}  {d['consulta']}")
