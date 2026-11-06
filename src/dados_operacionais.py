"""
dados_operacionais.py — Acesso aos dados dos sensores, aos resultados dos modelos e ao historico de OS
FIAP x Forzy | Challenge IA | Grupo 4M

Funcoes usadas pelo assistente para montar o contexto operacional:
  - resumo_ativo(tag, inicio, fim): estatisticas dos sensores x baseline, anomalias e classificacao
  - ranking_frota(inicio, fim): ativos ordenados por taxa de alertas
  - historico_os(tag, inicio, fim): ordens de servico do ativo
"""
from __future__ import annotations

import sqlite3
import warnings
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

RAIZ = Path(__file__).resolve().parents[1]
DB = RAIZ / "dados" / "motor.db"
OS_CSV = RAIZ / "dados" / "historico_manutencao.csv"
RES_ANOM = RAIZ / "modelos" / "sprint3" / "resultados_anomalias.csv"
DET = RAIZ / "modelos" / "sprint3" / "detector_anomalias.joblib"
S2 = RAIZ / "modelos" / "sprint2"

SENSORES = ["rotacao", "vibracao", "temperatura", "corrente"]
NOMES = {"rotacao": "Rotação", "vibracao": "Vibração", "temperatura": "Temperatura", "corrente": "Corrente"}
UNID = {"rotacao": "RPM", "vibracao": "mm/s", "temperatura": "°C", "corrente": "A"}
JANELA_PADRAO_MIN = 30
NOMES_FALHA = {0: "Normal", 1: "Desbalanceamento", 2: "Superaquecimento", 3: "Falha Mecânica"}


@lru_cache
def leituras() -> pd.DataFrame:
    """Leituras + saidas do detector (score, percentil, severidade...) por leitura."""
    df = pd.read_csv(RES_ANOM, parse_dates=["timestamp"])
    df["persistencia"] = df["persistencia"].fillna("")   # leituras sem alerta nao tem persistencia
    return df


@lru_cache
def detector() -> dict:
    return joblib.load(DET)


@lru_cache
def classificador():
    return (joblib.load(S2 / "modelo_falhas.joblib"), joblib.load(S2 / "scaler.joblib"),
            joblib.load(S2 / "modelo_config.joblib"))


@lru_cache
def ordens_servico() -> pd.DataFrame:
    return pd.read_csv(OS_CSV, dtype=str).fillna("")


def ativos() -> list[str]:
    return sorted(leituras()["tag"].unique())


def periodo_dados() -> tuple[datetime, datetime]:
    ts = leituras()["timestamp"]
    return ts.min().to_pydatetime(), ts.max().to_pydatetime()


def classificar(linha: pd.Series) -> dict:
    rf, sc, cfg = classificador()
    x = sc.transform([[linha[s] for s in cfg["ordem_sensores"]]])
    probs = rf.predict_proba(x)[0]
    i = int(probs.argmax())
    cod = int(rf.classes_[i])
    return {"classe": NOMES_FALHA[cod], "confianca": round(float(probs[i]), 3),
            "incerto": bool(probs[i] < 0.6),
            "distribuicao": {NOMES_FALHA[int(c)]: round(float(p), 3) for c, p in zip(rf.classes_, probs)}}


def resumo_ativo(tag: str, inicio: datetime | None = None, fim: datetime | None = None) -> dict | None:
    df = leituras()
    d = df[df.tag == tag]
    if d.empty:
        return None
    if fim is None:
        fim = d.timestamp.max()
    if inicio is None:
        inicio = fim - pd.Timedelta(minutes=JANELA_PADRAO_MIN)
    d = d[(d.timestamp >= inicio) & (d.timestamp <= fim)]
    if d.empty:
        return {"tag": tag, "sem_dados": True, "inicio": str(inicio), "fim": str(fim)}
    base = detector()["baseline"]
    ult = d.iloc[-1]
    sensores = {}
    for s in SENSORES:
        b = base[s]
        sensores[s] = {"nome": NOMES[s], "unidade": UNID[s], "atual": round(float(ult[s]), 2),
                       "media": round(float(d[s].mean()), 2), "min": round(float(d[s].min()), 2),
                       "max": round(float(d[s].max()), 2), "baseline_media": b["media"],
                       "faixa_normal": [b["p1"], b["p99"]],
                       "desvio_padronizado_atual": round((float(ult[s]) - b["media"]) / b["desvio"], 1)}
    al = d[d.alerta]
    # inicio da sequencia de alertas em curso, olhando toda a serie do ativo (nao so a janela)
    serie = df[(df.tag == tag) & (df.timestamp <= d.timestamp.max())]
    normais = serie[~serie.alerta]
    inicio_seq = None
    if bool(ult.alerta):
        resto = serie if normais.empty else serie[serie.timestamp > normais.timestamp.max()]
        inicio_seq = str(resto.timestamp.min())
    return {
        "tag": tag, "inicio": str(d.timestamp.min()), "fim": str(d.timestamp.max()),
        "n_leituras": int(len(d)), "sensores": sensores,
        "anomalia": {
            "ultima_leitura": str(ult.timestamp), "percentil_atual": round(float(ult.percentil), 1),
            "severidade_atual": ult.severidade, "alerta_atual": bool(ult.alerta),
            "persistencia_atual": ult.persistencia or "-",
            "sensor_maior_desvio_atual": NOMES[ult.sensor_principal],
            "alertas_no_periodo": int(len(al)),
            "taxa_alertas_periodo_pct": round(100 * len(al) / len(d), 1),
            "primeiro_alerta": str(al.timestamp.min()) if len(al) else None,
            "inicio_sequencia_atual": inicio_seq,
            "severidade_maxima": ({1: "Atenção", 2: "Alta", 3: "Crítica"}[int(
                al.severidade.map({"Atenção": 1, "Alta": 2, "Crítica": 3}).max())] if len(al) else "Normal"),
        },
        "classificador": classificar(ult),
        # gabarito da simulacao: usado SOMENTE nos testes, nunca enviado ao LLM
        "_rotulo_simulado": NOMES_FALHA[int(ult.falha)],
    }


def ranking_frota(inicio: datetime | None = None, fim: datetime | None = None, n: int = 5) -> list[dict]:
    df = leituras()
    if fim is None:
        fim = df.timestamp.max()
    if inicio is None:
        inicio = fim - pd.Timedelta(minutes=JANELA_PADRAO_MIN)
    d = df[(df.timestamp >= inicio) & (df.timestamp <= fim)]
    g = d.groupby("tag")
    r = pd.DataFrame({"alertas": g.alerta.sum(), "leituras": g.size(),
                      "percentil_max": g.percentil.max().round(1),
                      "percentil_medio": g.percentil.mean().round(1),
                      "ultima_severidade": g.severidade.last(),
                      "sensor_principal": g.sensor_principal.agg(lambda x: NOMES[x.mode().iat[0]])})
    r["taxa_alertas_pct"] = (100 * r.alertas / r.leituras).round(1)
    # desempate: muitos ativos ficam com 100% de alertas; ordena por severidade atual e percentil medio
    r["_sev"] = r.ultima_severidade.map({"Crítica": 3, "Alta": 2, "Atenção": 1}).fillna(0)
    r = r.sort_values(["taxa_alertas_pct", "_sev", "percentil_medio"], ascending=False).head(n)
    r = r.drop(columns="_sev")
    return [{"tag": t, **{k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()}}
            for t, row in r.iterrows()]


def historico_os(tag: str, inicio=None, fim=None) -> list[dict]:
    os_ = ordens_servico()
    d = os_[os_.tag == tag]
    if inicio is not None:
        d = d[d.data_abertura >= str(inicio)[:10]]
    if fim is not None:
        d = d[d.data_abertura <= str(fim)[:10]]
    return d.sort_values("data_abertura").to_dict(orient="records")
