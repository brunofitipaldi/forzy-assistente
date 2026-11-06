"""
anomalias.py — Baseline operacional + detector de anomalias (Isolation Forest temporal)
FIAP x Forzy | Challenge IA | Grupo 4M

Reimplementacao, em script reproduzivel, do pipeline descrito no relatorio da Sprint 3:
  - treino: 55% iniciais de cada motor (somente operacao normal)
  - calibracao: faixa 55%-70%, apenas leituras normais -> limiar P95
  - teste: 30% finais (mesmo recorte da Sprint 2)
  - janela causal de 10 leituras (5 min): media, desvio e delta por sensor (16 features)
  - Isolation Forest com 300 arvores, random_state=42

Uso:
    python src/anomalias.py            # treina, avalia e grava artefatos em modelos/sprint3
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score, accuracy_score)
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parents[1]
DB = RAIZ / "dados" / "motor.db"
SAIDA = RAIZ / "modelos" / "sprint3"

SENSORES = ["rotacao", "vibracao", "temperatura", "corrente"]
UNIDADES = {"rotacao": "RPM", "vibracao": "mm/s", "temperatura": "°C", "corrente": "A"}
JANELA = 10
FRAC_TREINO, FRAC_CALIB = 0.55, 0.70
PERSISTENCIA_MIN = 10   # >= 10 alertas consecutivos (5 min) = persistente
CURTA_MIN = 3           # 3 a 9 consecutivos = curta; 1-2 = pontual


def carregar(db: Path = DB) -> pd.DataFrame:
    with sqlite3.connect(db) as conn:
        df = pd.read_sql(
            "SELECT l.*, m.tag FROM leituras l JOIN motores m USING(motor_id) "
            "ORDER BY l.motor_id, l.timestamp", conn)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def features_temporais(df: pd.DataFrame) -> pd.DataFrame:
    """Janela causal por motor: so usa a leitura atual e as anteriores."""
    out = df.copy()
    g = out.groupby("motor_id")
    for s in SENSORES:
        out[f"{s}_media"] = g[s].transform(lambda x: x.rolling(JANELA, min_periods=1).mean())
        out[f"{s}_desvio"] = g[s].transform(lambda x: x.rolling(JANELA, min_periods=2).std()).fillna(0.0)
        out[f"{s}_delta"] = g[s].diff().fillna(0.0)
    return out


FEATURES = SENSORES + [f"{s}_{t}" for s in SENSORES for t in ("media", "desvio", "delta")]


def particionar(df: pd.DataFrame):
    pos = df.groupby("motor_id").cumcount()
    n = df.groupby("motor_id")["id"].transform("size")
    frac = pos / n
    treino = frac < FRAC_TREINO
    calib = (frac >= FRAC_TREINO) & (frac < FRAC_CALIB)
    teste = frac >= FRAC_CALIB
    return treino, calib, teste


def severidade(pct: float) -> str:
    if pct < 95:
        return "Normal"
    if pct < 97:
        return "Atenção"
    if pct < 99:
        return "Alta"
    return "Crítica"


def classificar_persistencia(alertas: pd.Series) -> pd.Series:
    """Rotula cada alerta conforme o tamanho da sequencia consecutiva a que pertence."""
    grupo = (alertas != alertas.shift()).cumsum()
    tam = alertas.groupby(grupo).transform("size")
    rot = np.where(~alertas, "", np.where(tam >= PERSISTENCIA_MIN, "Persistente",
                                           np.where(tam >= CURTA_MIN, "Curta", "Pontual")))
    return pd.Series(rot, index=alertas.index)


def treinar_e_avaliar():
    df = features_temporais(carregar())
    treino, calib, teste = particionar(df)
    # o treino (55% iniciais) e anterior ao inicio minimo das rampas (60%) -> apenas normal
    assert df.loc[treino, "falha"].eq(0).all()
    calib_normal = calib & df["falha"].eq(0)

    resultados = {}
    modelos = {}
    for nome, cols in {"pontual": SENSORES, "temporal": FEATURES}.items():
        sc = StandardScaler().fit(df.loc[treino, cols])
        iso = IsolationForest(n_estimators=300, max_samples="auto", random_state=42, n_jobs=-1)
        iso.fit(sc.transform(df.loc[treino, cols]))
        score = -iso.score_samples(sc.transform(df[cols]))          # maior = mais anomalo
        ref = np.sort(score[calib_normal.values])
        limiar = float(np.percentile(ref, 95))
        y = (df.loc[teste, "falha"] != 0).astype(int).values
        s = score[teste.values]
        p = (s >= limiar).astype(int)
        cm = confusion_matrix(y, p)
        resultados[nome] = {
            "limiar": round(limiar, 4),
            "acuracia": round(accuracy_score(y, p), 3),
            "precisao": round(precision_score(y, p), 3),
            "recall": round(recall_score(y, p), 3),
            "f1": round(f1_score(y, p), 3),
            "roc_auc": round(roc_auc_score(y, s), 3),
            "pr_auc": round(average_precision_score(y, s), 3),
            "matriz": cm.tolist(),
            "taxa_falso_alerta": round(cm[0, 1] / cm[0].sum(), 4),
        }
        modelos[nome] = (sc, iso, limiar, ref, score)

    sc, iso, limiar, ref, score = modelos["temporal"]
    df["score"] = score
    df["percentil"] = np.searchsorted(ref, score, side="right") / len(ref) * 100
    df["alerta"] = df["score"] >= limiar
    df["severidade"] = df["percentil"].map(severidade)
    df["persistencia"] = df.groupby("motor_id", group_keys=False)["alerta"].apply(classificar_persistencia)

    base = df.loc[treino, SENSORES]
    baseline = {s: {"unidade": UNIDADES[s], "media": round(base[s].mean(), 2),
                    "desvio": round(base[s].std(), 2), "p1": round(base[s].quantile(.01), 2),
                    "p99": round(base[s].quantile(.99), 2)} for s in SENSORES}
    z = (df[SENSORES] - base.mean()) / base.std()
    df["sensor_principal"] = z.abs().idxmax(axis=1)

    SAIDA.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": sc, "modelo": iso, "limiar": limiar, "ref_calibracao": ref,
                 "features": FEATURES, "janela": JANELA, "baseline": baseline},
                SAIDA / "detector_anomalias.joblib", compress=3)
    cols = ["id", "motor_id", "tag", "timestamp", *SENSORES, "falha", "score", "percentil",
            "alerta", "severidade", "persistencia", "sensor_principal"]
    df[cols].to_csv(SAIDA / "resultados_anomalias.csv", index=False)

    te = df[teste]
    ranking = (te.groupby("tag").agg(alertas=("alerta", "sum"), leituras=("alerta", "size"),
                                     sensor=("sensor_principal",
                                             lambda x: x[te.loc[x.index, "alerta"]].mode().iat[0]
                                             if te.loc[x.index, "alerta"].any() else "-"))
               .assign(taxa=lambda d: (100 * d.alertas / d.leituras).round(1))
               .sort_values(["taxa", "alertas"], ascending=False))
    ranking.to_csv(SAIDA / "ranking_ativos.csv")
    alert_te = te[te.alerta]
    resumo = {
        "metricas": resultados,
        "baseline": baseline,
        "particoes": {"treino": int(treino.sum()), "calibracao_normal": int(calib_normal.sum()),
                      "teste": int(teste.sum())},
        "alertas_teste": int(len(alert_te)),
        "persistencia": alert_te["persistencia"].value_counts().to_dict(),
        "sensor_principal_alertas": alert_te["sensor_principal"].value_counts().to_dict(),
        "top5_ranking": ranking.head(5).reset_index().to_dict(orient="records"),
    }
    (SAIDA / "metricas.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False,
                                                    default=lambda o: o.item()), encoding="utf-8")
    return resumo


if __name__ == "__main__":
    r = treinar_e_avaliar()
    print(json.dumps(r, indent=2, ensure_ascii=False, default=lambda o: o.item()))
