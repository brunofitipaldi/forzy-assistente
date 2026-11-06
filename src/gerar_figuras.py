"""
gerar_figuras.py — Gera os graficos de evidencia usados na documentacao (pasta evidencias/)
Uso: python src/gerar_figuras.py   (requer ter executado anomalias.py, avaliar_classificador.py e
                                    testes/avaliar_recuperacao.py)
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
EV = RAIZ / "evidencias"
AZUL, LARANJA, VERM, CINZA, VERDE = "#2a6fb0", "#e08a2c", "#c0392b", "#8a8f98", "#2e8b57"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "figure.dpi": 150})


def salvar(fig, nome):
    fig.tight_layout()
    fig.savefig(EV / nome, bbox_inches="tight")
    plt.close(fig)
    print("ok", nome)


res = pd.read_csv(RAIZ / "modelos/sprint3/resultados_anomalias.csv", parse_dates=["timestamp"])
met = json.loads((RAIZ / "modelos/sprint3/metricas.json").read_text(encoding="utf-8"))
clf = json.loads((RAIZ / "modelos/sprint2/metricas_classificador.json").read_text(encoding="utf-8"))
rec = json.loads((EV / "avaliacao_recuperacao.json").read_text(encoding="utf-8"))

# 1. serie do MOT-008
d = res[res.tag == "MOT-008"]
fig, ax = plt.subplots(2, 1, figsize=(9, 4.6), sharex=True)
ax[0].plot(d.timestamp, d.vibracao, color=AZUL, lw=.8)
ax[0].axhspan(1.12, 2.5, color=VERDE, alpha=.12, label="faixa normal (P1–P99)")
ax[0].set_ylabel("Vibração (mm/s)")
ax[0].legend(loc="upper left", frameon=False)
ax[0].set_title("MOT-008 — vibração e percentil de anomalia ao longo do dia")
ax[1].plot(d.timestamp, d.percentil, color=LARANJA, lw=.8)
ax[1].axhline(95, color=VERM, ls="--", lw=1, label="limiar de alerta (P95)")
ini = d[d.falha > 0].timestamp.min()
for a in ax:
    a.axvline(ini, color=CINZA, ls=":", lw=1)
ax[1].text(ini, 5, " início da rampa\n (rótulo simulado)", color=CINZA, fontsize=8)
ax[1].set_ylabel("Percentil")
ax[1].legend(loc="lower right", frameon=True, framealpha=.95)
ax[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))
salvar(fig, "fig_serie_mot008.png")

# 2. ranking de ativos (periodo de teste)
rk = pd.read_csv(RAIZ / "modelos/sprint3/ranking_ativos.csv").sort_values("taxa")
fig, ax = plt.subplots(figsize=(8, 5))
cores = [VERM if t >= 90 else LARANJA if t >= 20 else CINZA for t in rk.taxa]
ax.barh(rk.tag, rk.taxa, color=cores)
for y, (t, s) in enumerate(zip(rk.taxa, rk.sensor)):
    ax.text(t + 1, y, f"{t:.1f}%  {s if s != '-' else ''}", va="center", fontsize=8)
ax.set_xlabel("% das leituras do período de teste em alerta")
ax.set_xlim(0, 118)
ax.set_title("Ranking de ativos por taxa de alertas (30% finais da base)")
salvar(fig, "fig_ranking_ativos.png")

# 3. matriz de confusao do detector + 4. comparacao pontual x temporal
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [1, 1.5]})
m = np.array(met["metricas"]["temporal"]["matriz"])
axs[0].imshow(m, cmap="Blues")
for i in range(2):
    for j in range(2):
        axs[0].text(j, i, m[i, j], ha="center", va="center", color="white" if m[i, j] > 2000 else "black",
                    fontsize=12, fontweight="bold")
axs[0].set_xticks([0, 1], ["Normal", "Anomalia"])
axs[0].set_yticks([0, 1], ["Normal", "Falha"])
axs[0].set_xlabel("Previsto")
axs[0].set_ylabel("Real")
axs[0].set_title("Isolation Forest temporal — teste")
nomes = ["precisao", "recall", "f1", "roc_auc", "pr_auc"]
x = np.arange(len(nomes))
for k, (mod, cor) in enumerate([("pontual", CINZA), ("temporal", AZUL)]):
    v = [met["metricas"][mod][n] for n in nomes]
    axs[1].bar(x + (k - .5) * .38, v, .38, color=cor, label=f"IF {mod}")
    for xi, vi in zip(x, v):
        axs[1].text(xi + (k - .5) * .38, vi + .004, f"{vi:.3f}", ha="center", fontsize=7)
axs[1].set_xticks(x, ["Precisão", "Recall", "F1", "ROC-AUC", "PR-AUC"])
axs[1].set_ylim(.88, 1.0)
axs[1].legend(frameon=False, loc="lower right")
axs[1].set_title("Detector pontual × temporal")
salvar(fig, "fig_detector_anomalias.png")

# 5. classificador por classe
fig, ax = plt.subplots(figsize=(8, 3.4))
cls = list(clf["por_classe"])
x = np.arange(len(cls))
for k, (n, cor) in enumerate([("precision", AZUL), ("recall", LARANJA), ("f1-score", VERDE)]):
    v = [clf["por_classe"][c][n] for c in cls]
    ax.bar(x + (k - 1) * .26, v, .26, color=cor, label={"precision": "Precisão", "recall": "Recall",
                                                        "f1-score": "F1"}[n])
ax.set_xticks(x, cls)
ax.set_ylim(0, 1.1)
ax.legend(frameon=False, ncol=3, loc="upper center")
ax.set_title(f"Classificador Random Forest (Sprint 2) — F1 macro {clf['f1_macro']}")
salvar(fig, "fig_classificador.png")

# 6. recuperacao: separacao de scores
pos = [d_["melhor_score"] for d_ in rec["detalhes"]]
neg = [d_["melhor_score"] for d_ in rec["negativas"]]
fig, ax = plt.subplots(figsize=(8, 2.6))
ax.scatter(pos, np.full(len(pos), 1) + np.random.default_rng(1).uniform(-.12, .12, len(pos)), color=AZUL,
           label="perguntas do domínio")
ax.scatter(neg, np.zeros(len(neg)) + np.random.default_rng(2).uniform(-.12, .12, len(neg)), color=VERM,
           marker="x", label="perguntas fora do escopo")
ax.axvline(rec["limiar_usado"], color="black", ls="--", lw=1)
ax.text(rec["limiar_usado"] + .005, .5, f"limiar = {rec['limiar_usado']}", fontsize=8)
ax.set_yticks([0, 1], ["fora do escopo", "domínio"])
ax.set_xlabel("Maior similaridade de cosseno (embeddings) entre a pergunta e a base")
ax.set_title(f"Recuperação — Hit@1 {rec['hit@1']} · Hit@3 {rec['hit@3']} · MRR {rec['mrr']}")
ax.set_ylim(-.5, 1.5)
salvar(fig, "fig_recuperacao.png")
