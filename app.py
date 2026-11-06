"""
app.py — Interface web do assistente de manutencao preditiva (Streamlit)
FIAP x Forzy | Challenge IA | Grupo 4M

Execucao:  streamlit run app.py
Abas:
  - Assistente: chat com RAG + modelos, fontes consultadas e dados usados
  - Painel da frota: ranking de alertas e serie temporal do score de anomalia por ativo
Parametro de URL opcional: ?q=<pergunta> executa a pergunta ao abrir (usado para demonstracoes).
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
import assistente  # noqa: E402
import dados_operacionais as dop  # noqa: E402
import llm  # noqa: E402

st.set_page_config(page_title="Assistente de Manutenção Forzy", page_icon="🛠️", layout="wide")

if "historico" not in st.session_state:
    st.session_state.historico = []
    st.session_state.sessao = {}

with st.sidebar:
    st.header("🛠️ Assistente Forzy")
    st.caption("Grupo 4M · FIAP × Forzy · Sprint 4")
    ativo_ui = st.selectbox("Ativo em foco (opcional)", ["Automático (pela pergunta)"] + dop.ativos())
    ativo_ui = None if ativo_ui.startswith("Automático") else ativo_ui
    ini, fim = dop.periodo_dados()
    st.markdown(f"**Base de sensores:** {ini:%d/%m/%Y %H:%M} – {fim:%H:%M}  \n"
                f"**LLM:** `{llm.LLM_BACKEND}:{llm.LLM_MODEL}`  \n**Embeddings:** `{llm.EMBED_MODEL}`")
    st.markdown("Ollama: " + ("🟢 disponível" if llm.ollama_disponivel() else "🔴 indisponível"))
    st.info("Dados de sensores, documentos técnicos e ordens de serviço são **simulados** para fins acadêmicos.")
    st.markdown("**Exemplos de perguntas**")
    exemplos = ["Como está o MOT-008 agora?",
                "O MOT-011 está esquentando? O que devo verificar?",
                "Quais motores estão mais críticos agora?",
                "Histórico de manutenção do MOT-019",
                "O que significa severidade crítica?"]
    for ex in exemplos:
        if st.button(ex, width="stretch"):
            st.session_state.pendente = ex
    if st.button("🗑️ Limpar conversa", width="stretch"):
        st.session_state.historico, st.session_state.sessao = [], {}
        st.rerun()

aba_chat, aba_painel = st.tabs(["💬 Assistente", "📊 Painel da frota"])


def mostrar(r):
    st.markdown(r["resposta"].split("\n\n**Fontes consultadas:**")[0])
    meta = f"⏱️ {r['segundos']} s · tipo: `{r['tipo']}`"
    if r["ativos"]:
        meta += f" · ativo(s): {', '.join(r['ativos'])} · período: {r['periodo']}"
    if r["modelo"]:
        meta += f" · modelo: `{r['modelo']}`"
    st.caption(meta)
    if r["fontes"]:
        with st.expander(f"📚 Fontes consultadas ({len(r['fontes'])})"):
            for f in r["fontes"]:
                cit = " ✅ citada" if f["id"] in r.get("citadas", []) else ""
                score = f" · relevância {f['score']:.2f}" if "score" in f else ""
                st.markdown(f"**[{f['id']}]** {f['titulo']} · _{f['tipo']}_{score}{cit}")
                st.code(f["texto"][:700], language="text", wrap_lines=True)


with aba_chat:
    st.title("Assistente de Manutenção Preditiva")
    st.caption("Pergunte sobre sensores, anomalias, falhas, histórico de manutenção e procedimentos dos motores "
               "MOT-001 a MOT-020.")
    for msg in st.session_state.historico:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                mostrar(msg["r"])
            else:
                st.markdown(msg["texto"])

    pergunta = st.chat_input("Digite sua pergunta…")
    q_url = st.query_params.get("q")
    if q_url and not st.session_state.get("q_url_feito"):
        pergunta, st.session_state.q_url_feito = q_url, True
    pergunta = pergunta or st.session_state.pop("pendente", None)
    if pergunta:
        st.session_state.historico.append({"role": "user", "texto": pergunta})
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant"):
            with st.spinner("Consultando dados, modelos e documentação…"):
                r = assistente.responder(pergunta, ativo_ui=ativo_ui, sessao=st.session_state.sessao)
            from dataclasses import asdict
            rd = asdict(r)
            mostrar(rd)
        st.session_state.historico.append({"role": "assistant", "r": rd})

with aba_painel:
    st.subheader("Ranking de ativos — últimos 30 minutos da base")
    rk = pd.DataFrame(dop.ranking_frota(n=20))
    st.dataframe(rk.rename(columns={"tag": "Ativo", "alertas": "Alertas", "leituras": "Leituras",
                                    "percentil_max": "Percentil máx.", "percentil_medio": "Percentil médio", "ultima_severidade": "Última severidade",
                                    "sensor_principal": "Sensor de maior desvio",
                                    "taxa_alertas_pct": "% em alerta"}),
                 hide_index=True, width="stretch")
    tag = st.selectbox("Série temporal do ativo", dop.ativos(), index=7)
    d = dop.leituras()
    d = d[d.tag == tag].set_index("timestamp")
    c1, c2 = st.columns(2)
    c1.markdown("**Percentil de anomalia** (limiar de alerta = 95)")
    c1.line_chart(d["percentil"], height=260)
    sensor = c2.selectbox("Sensor", dop.SENSORES, index=1)
    c2.markdown(f"**{dop.NOMES[sensor]} ({dop.UNID[sensor]})**")
    c2.line_chart(d[sensor], height=225)
