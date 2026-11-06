"""Reavalia o classificador Random Forest da Sprint 2 (modelos/sprint2) no mesmo split 70/30."""
import json, sqlite3, warnings
from pathlib import Path
import joblib, pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
M = RAIZ / "modelos" / "sprint2"
rf, sc, cfg = (joblib.load(M / f) for f in ("modelo_falhas.joblib", "scaler.joblib", "modelo_config.joblib"))
with sqlite3.connect(RAIZ / "dados" / "motor.db") as c:
    df = pd.read_sql("SELECT * FROM leituras ORDER BY motor_id, timestamp", c)
te = df[df.groupby("motor_id").cumcount() >= 1500 * 0.7]
pred = rf.predict(sc.transform(te[cfg["ordem_sensores"]].values))
nomes = [cfg["classes"][i] for i in range(4)]
rep = classification_report(te.falha, pred, target_names=nomes, output_dict=True, digits=3)
out = {"f1_macro": round(f1_score(te.falha, pred, average="macro"), 3),
       "acuracia": round(rep["accuracy"], 3),
       "por_classe": {n: {k: round(rep[n][k], 3) for k in ("precision", "recall", "f1-score", "support")} for n in nomes},
       "matriz": confusion_matrix(te.falha, pred).tolist()}
(M / "metricas_classificador.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(out, indent=2, ensure_ascii=False))
