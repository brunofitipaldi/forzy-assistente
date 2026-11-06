---
doc_id: DOC-001
titulo: Manual técnico de operação — Motor de indução 3 CV (frota MOT-001 a MOT-020)
tipo: manual
ativos: todos
versao: 1.0
origem: SIMULADO
---

> Documento SIMULADO, elaborado pelo Grupo 4M para fins acadêmicos a partir dos parâmetros nominais usados na base sintética. Não substitui o manual oficial do fabricante.

## 1. Identificação do equipamento

A frota monitorada é composta por 20 motores elétricos de indução de 3 CV, 2 polos, carcaça com grau de proteção IP55, identificados pelas tags MOT-001 a MOT-020. Todos possuem o mesmo fabricante, modelo e potência, o que permite usar um único baseline operacional para a frota. Cada motor possui quatro sensores: rotação (RPM), vibração RMS na carcaça (mm/s), temperatura de carcaça (°C) e corrente de alimentação (A).

## 2. Valores nominais de referência

Rotação nominal de referência: 3600 RPM, com variação normal de aproximadamente ±25 RPM. Vibração RMS nominal: 1,8 mm/s (faixa normal entre 1,1 e 2,5 mm/s). Temperatura de carcaça nominal: 65 °C (faixa normal entre 58 e 72 °C). Corrente nominal: 11,5 A (faixa normal entre 10,1 e 12,9 A). Esses valores correspondem aos percentis P1 e P99 do baseline operacional calculado sobre o período normal de operação.

## 3. Limites operacionais e níveis de alarme

Vibração: atenção acima de 2,8 mm/s; alarme acima de 4,5 mm/s; crítico acima de 7,1 mm/s. Temperatura de carcaça: atenção acima de 75 °C; alarme acima de 80 °C; crítico acima de 90 °C, situação em que o motor deve ser desligado de forma controlada. Corrente: atenção acima de 12,9 A; alarme acima de 13,5 A; crítico acima de 15 A, quando há risco de atuação da proteção térmica. Rotação: atenção abaixo de 3540 RPM; alarme abaixo de 3480 RPM; crítico abaixo de 3400 RPM, indicando carga excessiva ou travamento mecânico parcial.

## 4. Condições ambientais e de instalação

O motor deve operar com temperatura ambiente de até 40 °C e altitude de até 1000 m. A base deve ser rígida e nivelada, com fixação por todos os pés. O acoplamento com a carga deve respeitar as tolerâncias de alinhamento: desvio radial máximo de 0,05 mm e angular máximo de 0,05 mm/100 mm. As aberturas de ventilação e as aletas da carcaça devem permanecer livres de poeira, óleo e obstruções.

## 5. Rolamentos e lubrificação

Os rolamentos são de esferas e devem ser relubrificados a cada 4000 horas de operação ou conforme o plano preventivo (DOC-005), com graxa à base de lítio compatível. Excesso de graxa provoca aquecimento do mancal; falta de graxa provoca ruído e aumento de vibração em alta frequência. Rolamentos com folga, ruído metálico ou temperatura de mancal acima de 90 °C devem ser substituídos.

## 6. Relação entre sensores e modos de falha

Desbalanceamento: aumento progressivo da vibração com instabilidade da rotação, sem alteração relevante de temperatura e corrente. Superaquecimento: aumento conjunto de temperatura e corrente, normalmente por sobrecarga, ventilação deficiente ou tensão inadequada. Falha mecânica (rolamento, desalinhamento ou roçamento): aumento de vibração, temperatura e corrente acompanhado de queda de rotação. Os procedimentos de diagnóstico estão em DOC-002, DOC-003 e DOC-004.
