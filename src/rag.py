"""
rag.py — Preparacao, indexacao e recuperacao de documentos (camada R do RAG)
FIAP x Forzy | Challenge IA | Grupo 4M

Fontes indexadas:
  - docs_tecnicos/*.md  -> manuais, POPs de troubleshooting, plano preventivo, seguranca, guia de IA
  - dados/historico_manutencao.csv -> uma "ficha" textual por ordem de servico (OS)

Estrategia:
  - chunking por secao (cabecalho "## ") com divisao adicional por paragrafo se > MAX_CHARS
  - cada chunk carrega metadados: doc_id, titulo, tipo, secao, ativos, data, origem
  - busca HIBRIDA:
      densa  -> embeddings semanticos (Ollama embeddinggemma, 768 dim, cosseno)
      lexica -> TF-IDF de palavras (1-2 gramas) + TF-IDF de n-gramas de caracteres (3-5)
    fusao das duas listas por Reciprocal Rank Fusion (RRF, k=60)
  - porta de relevancia: trecho so e evidencia se o cosseno denso >= LIMIAR_DENSO
  - expansao de consulta (lexica) com sinonimos do dominio (ex.: "esquentando" -> temperatura)
  - se o Ollama estiver indisponivel, cai para busca so lexica (LIMIAR_RELEVANCIA)
  - filtros pre-recuperacao por ativo, tipo de documento e periodo (OS)

Uso:
    python src/rag.py --indexar
    python src/rag.py --buscar "o que fazer com vibracao alta" --ativo MOT-008
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

import llm

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs_tecnicos"
OS_CSV = RAIZ / "dados" / "historico_manutencao.csv"
INDICE = RAIZ / "modelos" / "rag" / "indice.joblib"

MAX_CHARS = 1200
PESO_PALAVRA, PESO_CHAR = 0.6, 0.4
LIMIAR_RELEVANCIA = 0.10   # porta lexica (modo degradado, sem embeddings)
LIMIAR_DENSO = 0.38        # porta densa, calibrada em testes/avaliar_recuperacao.py (22 consultas)
RRF_K = 60

STOP = set("""a o e é de da do das dos em no na nos nas um uma uns umas para por com sem que se ao aos
as os ou como qual quais quando onde ser estar esta este esse essa isso isto ha há mais menos muito
sua seu suas seus meu minha me nao não sim ja já foi sao são tem ter pelo pela pelos pelas entre sobre
apos após ate até deve devem pode podem""".split())

SINONIMOS = {
    "esquent": "temperatura superaquecimento",
    "quente": "temperatura superaquecimento",
    "aquec": "temperatura superaquecimento",
    "trepid": "vibracao",
    "trem": "vibracao",
    "vibrand": "vibracao",
    "balanc": "desbalanceamento vibracao",
    "amper": "corrente",
    "consumo": "corrente",
    "giro": "rotacao",
    "velocidade": "rotacao",
    "rpm": "rotacao",
    "rolament": "rolamento mancal falha mecanica",
    "barulh": "ruido rolamento",
    "ruido": "ruido rolamento",
    "graxa": "lubrificacao relubrificacao",
    "lubrific": "lubrificacao relubrificacao",
    "desligar": "parada seguranca",
    "choque": "seguranca nr-10 eletrico",
    "fumaca": "seguranca parada imediata",
    "queimado": "seguranca parada imediata",
    "limite": "limites alarme nominal",
    "nominal": "valores nominais referencia",
}


def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt.lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\-\.,/ ]+", " ", txt)


def expandir_consulta(q: str) -> str:
    qn = normalizar(q)
    extras = [v for k, v in SINONIMOS.items() if k in qn]
    return qn + " " + " ".join(extras)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    titulo: str
    tipo: str
    secao: str
    texto: str
    ativos: list[str] = field(default_factory=lambda: ["todos"])
    data: str | None = None
    origem: str = "SIMULADO"


def _front_matter(md: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", md, re.S)
    meta = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
    return {k.strip(): v.strip() for k, v in meta.items()}, m.group(2)


def _dividir(texto: str) -> list[str]:
    if len(texto) <= MAX_CHARS:
        return [texto]
    partes, atual = [], ""
    for par in texto.split("\n\n"):
        if atual and len(atual) + len(par) > MAX_CHARS:
            partes.append(atual.strip())
            atual = atual.split("\n\n")[-1]          # sobreposicao de 1 paragrafo
        atual += "\n\n" + par
    partes.append(atual.strip())
    return partes


def preparar_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for arq in sorted(DOCS.glob("*.md")):
        meta, corpo = _front_matter(arq.read_text(encoding="utf-8"))
        ativos = [a.strip() for a in meta.get("ativos", "todos").split(",")]
        secoes = re.split(r"\n(?=## )", corpo)
        for sec in secoes:
            sec = sec.strip()
            if not sec.startswith("## "):          # aviso de documento simulado: nao indexa
                continue
            titulo_sec, _, texto = sec.partition("\n")
            texto = re.sub(r"\s+\n", "\n", texto).strip()
            if len(texto) < 60:                     # descarta fragmentos sem conteudo util
                continue
            for i, parte in enumerate(_dividir(texto)):
                n = len([c for c in chunks if c.doc_id == meta["doc_id"]]) + 1
                chunks.append(Chunk(f"{meta['doc_id']}#{n}", meta["doc_id"], meta["titulo"],
                                    meta["tipo"], titulo_sec[3:].strip(), parte, ativos,
                                    origem=meta.get("origem", "SIMULADO")))
    os_df = pd.read_csv(OS_CSV, dtype=str).fillna("")
    for r in os_df.itertuples():
        texto = (f"Ordem de servico {r.os_id} do motor {r.tag}, tipo {r.tipo}, aberta em {r.data_abertura}"
                 f"{', fechada em ' + r.data_fechamento if r.data_fechamento else ''}, status {r.status}. "
                 f"Falha relacionada: {r.falha_relacionada}. Descricao: {r.descricao}. "
                 f"Causa raiz: {r.causa_raiz}. Acao executada: {r.acao}. Horas de parada: {r.horas_parada}.")
        chunks.append(Chunk(r.os_id, r.os_id, f"Ordem de serviço {r.os_id}", "ordem_servico",
                            r.tag, texto, [r.tag], r.data_abertura, r.origem))
    return chunks


class IndiceRAG:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        corpus = [normalizar(f"{c.titulo} {c.secao} {c.texto}") for c in chunks]
        self.vp = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words=list(STOP))
        self.vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.Mp = self.vp.fit_transform(corpus)
        self.Mc = self.vc.fit_transform(corpus)
        try:
            self.E = llm.embeddings([f"title: {c.titulo} - {c.secao} | text: {c.texto}" for c in chunks])
            self.embed_model = llm.EMBED_MODEL
        except Exception as e:  # sem Ollama: indice so lexico
            print(f"[rag] embeddings indisponiveis ({e.__class__.__name__}); usando so busca lexica")
            self.E, self.embed_model = None, None

    def _scores(self, consulta: str):
        q = expandir_consulta(consulta)
        lex = (PESO_PALAVRA * (self.Mp @ self.vp.transform([q]).T).toarray().ravel()
               + PESO_CHAR * (self.Mc @ self.vc.transform([q]).T).toarray().ravel())
        den = None
        if self.E is not None:
            try:
                den = self.E @ llm.embeddings([consulta], consulta=True)[0]
            except Exception:
                den = None
        return lex, den

    def buscar(self, consulta: str, k: int = 4, ativo: str | None = None,
               tipos: list[str] | None = None, periodo: tuple[date, date] | None = None,
               incluir_os: bool = True) -> list[dict]:
        lex, den = self._scores(consulta)
        rank_lex = np.argsort(np.argsort(-lex))
        if den is not None:
            rank_den = np.argsort(np.argsort(-den))
            rrf = 1 / (RRF_K + rank_lex + 1) + 1 / (RRF_K + rank_den + 1)
            porta, limiar = den, LIMIAR_DENSO
        else:
            rrf, porta, limiar = lex, lex, LIMIAR_RELEVANCIA
        res = []
        for i in np.argsort(-rrf):
            c = self.chunks[i]
            if ativo and "todos" not in c.ativos and ativo not in c.ativos:
                continue
            if c.tipo == "ordem_servico" and not incluir_os:
                continue
            if tipos and c.tipo not in tipos:
                continue
            if periodo and c.data and not (periodo[0] <= date.fromisoformat(c.data) <= periodo[1]):
                continue
            if porta[i] < limiar:
                continue
            res.append({**c.__dict__, "score": round(float(porta[i]), 3),
                        "score_lexico": round(float(lex[i]), 3), "rrf": round(float(rrf[i]), 4)})
            if len(res) == k:
                break
        return res

    def melhor_score(self, consulta: str) -> float:
        lex, den = self._scores(consulta)
        return float((den if den is not None else lex).max())


def indexar() -> IndiceRAG:
    idx = IndiceRAG(preparar_chunks())
    INDICE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(idx, INDICE, compress=3)
    return idx


def carregar_indice() -> IndiceRAG:
    if not INDICE.exists():
        return indexar()
    return joblib.load(INDICE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--indexar", action="store_true")
    ap.add_argument("--buscar")
    ap.add_argument("--ativo")
    a = ap.parse_args()
    if a.indexar:
        idx = indexar()
        tipos = pd.Series([c.tipo for c in idx.chunks]).value_counts().to_dict()
        print(f"Indice criado: {len(idx.chunks)} chunks -> {tipos}")
        print(f"Vocabulario: {len(idx.vp.vocabulary_)} termos (palavras) / {len(idx.vc.vocabulary_)} n-gramas")
        print(f"Embeddings: {idx.embed_model} {None if idx.E is None else idx.E.shape}")
    if a.buscar:
        for r in carregar_indice().buscar(a.buscar, ativo=a.ativo):
            print(f"[{r['score']:.3f}] {r['chunk_id']:14s} {r['secao'][:40]:40s} | {r['texto'][:90]}")
