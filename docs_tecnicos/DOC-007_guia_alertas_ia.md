---
doc_id: DOC-007
titulo: Guia de interpretação dos alertas e modelos de IA
tipo: guia
ativos: todos
versao: 1.0
origem: PROJETO
---

> Guia elaborado pelo Grupo 4M a partir dos modelos desenvolvidos nas Sprints 2 e 3.

## 1. Score e percentil de anomalia

O detector de anomalias (Isolation Forest temporal) compara a janela das últimas 10 leituras do motor (5 minutos) com o comportamento normal aprendido. O percentil indica quanto a leitura é rara em relação às leituras normais de calibração; percentil 99 significa que apenas 1% das leituras normais é tão incomum quanto ela. O percentil não é probabilidade de falha.

## 2. Severidade

Normal: percentil abaixo de 95. Atenção: entre 95 e 97. Alta: entre 97 e 99. Crítica: a partir de 99. A severidade orienta a prioridade de inspeção.

## 3. Persistência

Pontual: 1 ou 2 alertas consecutivos, geralmente ruído. Curta: 3 a 9 alertas consecutivos (até 5 minutos). Persistente: 10 ou mais alertas consecutivos, ou seja, desvio contínuo por pelo menos 5 minutos, que deve ser tratado como degradação em curso.

## 4. Sensor de maior desvio

É o sensor cuja leitura está mais distante da média do baseline em número de desvios-padrão. Serve para orientar qual POP consultar, mas é uma explicação heurística e não prova de causa.

## 5. Classificador de falhas conhecidas

O classificador Random Forest indica qual falha conhecida (Desbalanceamento, Superaquecimento ou Falha Mecânica) é mais compatível com a leitura atual, com uma probabilidade. Ele tem boa precisão para Superaquecimento, mas confunde Desbalanceamento com Falha Mecânica no início da degradação. Confiança abaixo de 60% deve ser tratada como incerta.
