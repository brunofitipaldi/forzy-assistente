"""
agente_manutencao.py — Agente conversacional de manutencao preditiva
FIAP x Forzy | Challenge IA | Sprint 2

Chat com function calling que expoe o modelo Random Forest treinado
(modelo_falhas.joblib) como ferramenta. O usuario descreve as leituras de um
motor WEG W22 em linguagem natural e o agente retorna o diagnostico.

Tool registrada (assinatura conforme enunciado):
    prever_falha_motor(rotacao_rpm, vibracao_mm_s, temperatura_c, corrente_a)

O modelo carregado e treinado nos 4 sensores brutos, exatamente os parametros
que a tool recebe — garantindo coerencia entre treino e consulta pontual.

Backends: Groq (nuvem, gratis) com LLaMA 3.1 [padrao] ou Ollama local (llama3.1).
A API da Anthropic exige creditos pagos; por isso usamos Groq.

Uso:
    python agente_manutencao.py            # chat interativo
    python agente_manutencao.py --demo     # 3 cenarios: normal, falha clara, ambiguo
"""
import os, json, argparse
import numpy as np, joblib

MODELO = joblib.load("modelo_falhas.joblib")
SCALER = joblib.load("scaler.joblib")
CONFIG = joblib.load("modelo_config.joblib")
CLASSES = CONFIG["classes"]
ORDEM = CONFIG["ordem_sensores"]   # ['rotacao','vibracao','temperatura','corrente']

ASSINATURAS = {
    1: "vibracao elevada e rotacao instavel (desbalanceamento do rotor)",
    2: "temperatura e corrente acima do nominal (sobrecarga termica)",
    3: "vibracao + temperatura + corrente anomalas com queda de rotacao",
}


def prever_falha_motor(rotacao_rpm, vibracao_mm_s, temperatura_c, corrente_a):
    """Tool de function calling: recebe as 4 leituras e retorna o diagnostico."""
    leituras = {"rotacao": rotacao_rpm, "vibracao": vibracao_mm_s,
                "temperatura": temperatura_c, "corrente": corrente_a}
    x = SCALER.transform([[leituras[s] for s in ORDEM]])
    cod = int(MODELO.predict(x)[0])
    probs = MODELO.predict_proba(x)[0]
    dist = {CLASSES[int(c)]: round(float(p), 3) for c, p in zip(MODELO.classes_, probs)}
    top = float(max(probs))
    # sensor que mais difere do nominal (contribuicao dominante)
    nominal = {"rotacao": 3600, "vibracao": 1.8, "temperatura": 65, "corrente": 11.5}
    desvios = {k: abs(v - nominal[k]) / nominal[k] for k, v in leituras.items()}
    sensor_chave = max(desvios, key=desvios.get)
    nivel = "INCERTO" if top < 0.6 else ("NORMAL" if cod == 0 else "RISCO")
    return {
        "classe_prevista": CLASSES[cod], "codigo": cod, "confianca": round(top, 3),
        "nivel": nivel, "distribuicao": dist,
        "padrao_associado": ASSINATURAS.get(cod, "operacao dentro do esperado"),
        "sensor_mais_relevante": sensor_chave,
        "leituras": leituras,
    }


TOOLS = [{
    "type": "function",
    "function": {
        "name": "prever_falha_motor",
        "description": ("Preve a condicao de um motor WEG W22 a partir das leituras dos sensores. "
                        "Use sempre que o usuario informar rotacao, vibracao, temperatura e corrente."),
        "parameters": {
            "type": "object",
            "properties": {
                "rotacao_rpm": {"type": "number", "description": "Rotacao em RPM"},
                "vibracao_mm_s": {"type": "number", "description": "Vibracao RMS em mm/s"},
                "temperatura_c": {"type": "number", "description": "Temperatura em graus Celsius"},
                "corrente_a": {"type": "number", "description": "Corrente eletrica em Amperes"},
            },
            "required": ["rotacao_rpm", "vibracao_mm_s", "temperatura_c", "corrente_a"],
        },
    },
}]

SYSTEM = (
    "Voce e o assistente tecnico da plataforma Forzy de manutencao preditiva de motores WEG W22. "
    "Quando o usuario informar leituras de sensores, use a ferramenta prever_falha_motor. "
    "Na resposta: (1) cite a classe prevista e a confianca; (2) explique quais sensores levaram ao "
    "diagnostico usando 'sensor_mais_relevante' e 'padrao_associado'; (3) se 'nivel' for INCERTO, "
    "comunique claramente a incerteza, mostre a distribuicao de probabilidades e recomende coletar "
    "mais leituras antes de agir. Seja direto e tecnico."
)


def chamar_groq(mensagens):
    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return client.chat.completions.create(
        model="llama-3.1-8b-instant", messages=mensagens, tools=TOOLS, tool_choice="auto")


def responder(historico):
    msg = chamar_groq(historico).choices[0].message
    if msg.tool_calls:
        historico.append({"role": "assistant", "content": msg.content or "",
                          "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            resultado = prever_falha_motor(**args)
            historico.append({"role": "tool", "tool_call_id": tc.id,
                              "name": "prever_falha_motor",
                              "content": json.dumps(resultado, ensure_ascii=False)})
        final = chamar_groq(historico).choices[0].message.content
        historico.append({"role": "assistant", "content": final})
        return final
    historico.append({"role": "assistant", "content": msg.content})
    return msg.content


def chat_interativo():
    print("Agente de Manutencao Preditiva — Forzy (digite 'sair' para encerrar)\n")
    hist = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            user = input("Voce: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in {"sair", "exit", "quit"}:
            break
        hist.append({"role": "user", "content": user})
        print("Agente:", responder(hist), "\n")


def modo_demo():
    cenarios = [
        ("Operacao normal",
         "Motor MOT-001: rotacao 3598 RPM, vibracao 1.8 mm/s, temperatura 64 C e corrente 11.4 A."),
        ("Falha clara (superaquecimento)",
         "Leituras: rotacao 3592 RPM, vibracao 1.9 mm/s, temperatura 99 C, corrente 18.5 A. O que houve?"),
        ("Leituras ambiguas",
         "Motor com rotacao 3548 RPM, vibracao 2.4 mm/s, temperatura 76 C e corrente 12.5 A. Esta tudo bem?"),
    ]
    for i, (rotulo, c) in enumerate(cenarios, 1):
        print(f"\n{'='*65}\nCENARIO {i} — {rotulo}\n{'='*65}\nVoce: {c}")
        hist = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": c}]
        print("Agente:", responder(hist))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agente de Manutencao Preditiva WEG W22 — FIAP x Forzy Sprint 2")
    parser.add_argument("--demo", action="store_true", help="Executa os 3 cenarios de demonstracao")
    args = parser.parse_args()
    modo_demo() if args.demo else chat_interativo()
