# BANCO.md — Documentação do banco `motor.db`
## FIAP × Forzy | Challenge IA | Sprint 2 — Manutenção Preditiva

---

## Origem

Os dados são gerados sinteticamente pelo script `gerar_banco.py`, simulando o
comportamento físico de motores **WEG W22 Monofásico 3CV** (2 polos, 3600 RPM,
110-127/220-254V, IP55), com base nos seguintes princípios:

- Leituras normais geradas dentro dos limites nominais com ruído gaussiano;
- Falhas introduzidas com **rampa progressiva de deterioração** (início entre 60–80% da série);
- Semente fixa (`seed=42`) para reprodutibilidade.

| Atributo | Valor |
|---|---|
| Arquivo | `motor.db` (SQLite 3) |
| Total de leituras | 30.000 (20 motores × 1.500 leituras) |
| Intervalo entre leituras | 30 segundos (~12,5 h por motor) |

---

## Schema

### Tabela `tipos_falha`

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo` | INTEGER | Chave primária (0–3) |
| `nome` | TEXT | Nome da classe de falha |
| `descricao` | TEXT | Descrição do modo de falha |

| Código | Nome | Descrição |
|---|---|---|
| 0 | Normal | Operação dentro dos parâmetros nominais |
| 1 | Desbalanceamento | Vibração excessiva e rotação instável por desequilíbrio do rotor |
| 2 | Superaquecimento | Temperatura e corrente acima do limite nominal por sobrecarga térmica |
| 3 | Falha Mecânica | Queda de rotação com vibração, temperatura e corrente anômalas |

### Tabela `motores`

| Coluna | Tipo | Descrição |
|---|---|---|
| `motor_id` | INTEGER | Chave primária (1–20) |
| `fabricante` | TEXT | WEG |
| `modelo` | TEXT | W22 |
| `potencia_hp` | REAL | 3.0 |
| `tensao_v` | TEXT | Faixa de tensão |
| `tag` | TEXT | Identificador do ativo (ex: MOT-001) |

### Tabela `leituras`

| Coluna | Tipo | Unidade | Faixa nominal |
|---|---|---|---|
| `id` | INTEGER | — | PK autoincrement |
| `motor_id` | INTEGER | — | FK → motores |
| `timestamp` | TEXT | ISO 8601 | — |
| `temperatura` | REAL | °C | ~65 |
| `vibracao` | REAL | mm/s | ~1.8 |
| `corrente` | REAL | A | ~11.5 |
| `rotacao` | REAL | RPM | ~3600 |
| `falha` | INTEGER | — | FK → tipos_falha |

---

## Assinatura de cada falha

| Falha | Temperatura | Vibração | Corrente | Rotação |
|---|---|---|---|---|
| Desbalanceamento | — | ↑↑ | — | ↓ instável |
| Superaquecimento | ↑↑ | — | ↑ | — |
| Falha Mecânica | ↑ | ↑↑ | ↑ | ↓↓ |

O rótulo `falha` é atribuído por leitura: vale `0` (Normal) enquanto o motor
opera dentro dos limites e passa a valer a classe correspondente a partir do
início da rampa de deterioração.
