# Assistente de Manutenção Preditiva — Forzy

**FIAP × Forzy | Challenge IA | Sprint 4 — Generative IA & Advanced Net | Grupo 4M**

Arthur Pedreca de Almeida Vasco (RM 565215) · Bruno Lanchariche Fitipaldi Lopes (RM 564129) ·
Gustavo Civita Gonçalves (RM 561932) · Rafael de Paiva Ramos (RM 563978) · Thiago Santana Danyluk (RM 562286)

---

## Visão geral

Solução de IA que apoia a manutenção de uma frota de 20 motores elétricos (MOT-001 a MOT-020). Ela combina:

| Componente | Origem | Função |
|---|---|---|
| Classificador de falhas (Random Forest) | Sprint 2 | Indica qual falha conhecida é mais compatível com a leitura atual |
| Baseline + detector de anomalias (Isolation Forest temporal) | Sprint 3 | Mede o desvio em relação ao comportamento normal (percentil, severidade, persistência, sensor de maior desvio) |
| RAG (recuperação híbrida + LLM) | Sprint 4 | Recupera trechos de manuais, POPs e ordens de serviço, filtrados por ativo e período |
| Assistente conversacional (Streamlit) | Sprint 4 | Responde perguntas sobre sensores, anomalias, falhas, histórico e procedimentos, citando as fontes |

> ⚠️ **Dados simulados:** as leituras de sensores (`motor.db`), os documentos técnicos (`docs_tecnicos/`) e as
> ordens de serviço (`historico_manutencao.csv`) foram **gerados pelo grupo** para fins acadêmicos. As métricas
> validam o método, não o desempenho em produção.

Documentação completa: [`docs/Documentacao_Final_Sprint4_Grupo4M.pdf`](docs/Documentacao_Final_Sprint4_Grupo4M.pdf).

## Estrutura dos arquivos

```
forzy-assistente/
├── app.py                         # Interface web (Streamlit): chat + painel da frota
├── requirements.txt               # Dependências Python com versões fixadas
├── .env.example                   # Variáveis de ambiente (sem credenciais)
├── dados/
│   ├── gerar_banco.py             # Gera motor.db (20 motores × 1.500 leituras, seed 42)
│   ├── motor.db                   # Base SQLite de sensores (SIMULADA)
│   ├── BANCO.md                   # Schema e assinaturas de falha
│   └── historico_manutencao.csv   # 23 ordens de serviço (SIMULADAS)
├── docs_tecnicos/                 # Base documental do RAG (7 documentos .md com metadados)
├── src/
│   ├── anomalias.py               # Baseline + Isolation Forest temporal (Sprint 3) -> modelos/sprint3
│   ├── avaliar_classificador.py   # Reavalia o Random Forest da Sprint 2
│   ├── rag.py                     # Chunking, indexação híbrida (embeddings + TF-IDF), busca com filtros
│   ├── dados_operacionais.py      # Consulta de sensores, saídas dos modelos e histórico de OS
│   ├── llm.py                     # Clientes Ollama/Groq (geração e embeddings)
│   ├── assistente.py              # Orquestrador: interpretação, guardas, contexto, RAG, geração
│   ├── gerar_figuras.py           # Gráficos de evidência
│   └── agente_sprint2_legado.py   # Agente da Sprint 2 (function calling via Groq), mantido como referência
├── modelos/
│   ├── sprint2/                   # modelo_falhas.joblib, scaler.joblib, modelo_config.joblib, métricas
│   ├── sprint3/                   # detector_anomalias.joblib, resultados_anomalias.csv, ranking, métricas
│   └── rag/indice.joblib          # Índice do RAG (gerado)
├── notebooks/                     # EDA e treinamento da Sprint 2
├── testes/
│   ├── avaliar_recuperacao.py     # Hit@1, Hit@3, MRR e bloqueio de perguntas fora do escopo
│   ├── cenarios.py                # 9 cenários ponta a ponta (entrada, esperado, obtido)
│   └── capturar_telas.py          # capturas de tela da interface (Playwright + Edge)
├── evidencias/                    # Gráficos, JSON dos testes, logs e capturas de tela
└── docs/                          # Documentação final (PDF e fonte HTML)
```

## Como executar

### 1. Pré-requisitos
- Python 3.11+ (validado em 3.14.5) e Git
- [Ollama](https://ollama.com) ≥ 0.40 instalado e em execução
- ~6 GB livres (modelos) e 8 GB de RAM; GPU é opcional

### 2. Instalação
```bash
git clone https://github.com/brunofitipaldi/forzy-assistente.git
cd forzy-assistente
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
ollama pull llama3.1
ollama pull embeddinggemma
copy .env.example .env          # opcional (Linux/Mac: cp)
```

### 3. Preparação dos dados e modelos
Os artefatos já estão versionados. Para reproduzir tudo do zero:
```bash
cd dados && python gerar_banco.py && cd ..   # gera dados/motor.db
python src/anomalias.py               # baseline + detector -> modelos/sprint3 (F1 0,947)
python src/avaliar_classificador.py   # métricas do Random Forest (F1 macro 0,728)
python src/rag.py --indexar           # chunking + embeddings + TF-IDF -> modelos/rag/indice.joblib
```

### 4. Execução
```bash
streamlit run app.py                                  # interface web em http://localhost:8501
python src/assistente.py "Como está o MOT-008?"       # pergunta única no terminal
python src/assistente.py                              # chat no terminal
```

### 5. Testes
```bash
python testes/avaliar_recuperacao.py   # avaliação da recuperação
python testes/cenarios.py              # cenários ponta a ponta (~4 min por resposta em CPU)
python src/gerar_figuras.py            # regenera os gráficos de evidências/
```

### Usando o Groq em vez do Ollama (opcional)
Defina `LLM_BACKEND=groq`, `LLM_MODEL=llama-3.1-8b-instant` e `GROQ_API_KEY` no `.env` e instale `groq`.
Os embeddings continuam no Ollama. Não versione a chave.

## Principais resultados

| Item | Resultado |
|---|---|
| Detector de anomalias (teste, 9.000 leituras) | Precisão 0,954 · Recall 0,939 · F1 0,947 · ROC-AUC 0,982 · falso alerta 4,24% |
| Classificador de falhas (teste) | F1 macro 0,728 · acurácia 0,823 (recall de Desbalanceamento 0,296) |
| Recuperação (16 perguntas + 6 fora do escopo) | Hit@1 0,625 · Hit@3 0,812 · MRR 0,719 · 6/6 perguntas fora do escopo bloqueadas |
| Cenários ponta a ponta (9) | 9/9 nas verificações automáticas; 7/9 corretos na avaliação manual (C6 e C9 parciais) — `evidencias/cenarios.json` |

## Limitações principais
Dados 100% simulados (um modelo de motor, 12,5 h de operação); LLM local lento em CPU (~1,5–3,5 min por
resposta) e ainda capaz de inventar números em listas de ativos; base documental pequena (7 documentos + 23 OS); detector pontuado em lote, não em streaming.
Detalhes e próximos passos na seção 9 da documentação.
