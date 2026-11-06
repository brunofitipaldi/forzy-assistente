"""
gerar_banco.py — Gerador da base de dados sintética de telemetria de motores
FIAP x Forzy | Challenge IA | Sprint 2

Gera o arquivo SQLite `motor.db` simulando o comportamento físico de motores
WEG W22 Monofásico 3CV (2 polos, 3600 RPM, 110-127/220-254V, IP55).

Estrutura:
    20 motores x 1.500 leituras = 30.000 registros
    Intervalo entre leituras: 30 segundos (~12,5 h por motor)

Classes de falha:
    0 - Normal
    1 - Desbalanceamento  (vibração elevada, rotação instável)
    2 - Superaquecimento  (temperatura e corrente crescentes)
    3 - Falha Mecânica    (vibração + temperatura + corrente anômalas, queda de RPM)

Princípios da simulação:
    - Leituras normais geradas dentro dos limites nominais com ruído gaussiano
    - Falhas introduzidas com rampa progressiva de deterioração (início entre 60-80% da série)
"""

import sqlite3
import numpy as np
from datetime import datetime, timedelta

RNG = np.random.default_rng(42)  # reprodutibilidade

# ----------------------------------------------------------------------------
# Parâmetros nominais do motor WEG W22 Monofásico 3CV
# ----------------------------------------------------------------------------
TEMP_NOMINAL = 65.0      # °C
TEMP_STD = 3.0
VIB_NOMINAL = 1.8        # mm/s (RMS)
VIB_STD = 0.3
CORR_NOMINAL = 11.5      # A
CORR_STD = 0.6
RPM_NOMINAL = 3600.0     # rpm
RPM_STD = 25.0

N_MOTORES = 20
N_LEITURAS = 1500
INTERVALO_S = 30

# Proporção de motores por classe de falha (distribuição realista, ~maioria normal)
DISTRIB_FALHA = {
    0: 0.50,   # Normal
    1: 0.20,   # Desbalanceamento
    2: 0.18,   # Superaquecimento
    3: 0.12,   # Falha mecânica
}


def _rampa(n, inicio_frac, intensidade):
    """Cria uma rampa de deterioração que começa em inicio_frac da série."""
    rampa = np.zeros(n)
    inicio = int(n * inicio_frac)
    passo = np.linspace(0, intensidade, n - inicio)
    rampa[inicio:] = passo
    return rampa


def gerar_serie(falha, n=N_LEITURAS):
    """Gera as 4 séries de sensores (temp, vib, corrente, rpm) para um motor."""
    temp = RNG.normal(TEMP_NOMINAL, TEMP_STD, n)
    vib = RNG.normal(VIB_NOMINAL, VIB_STD, n)
    corr = RNG.normal(CORR_NOMINAL, CORR_STD, n)
    rpm = RNG.normal(RPM_NOMINAL, RPM_STD, n)

    inicio = RNG.uniform(0.60, 0.80)

    if falha == 1:  # Desbalanceamento
        vib += _rampa(n, inicio, 4.5)
        rpm -= _rampa(n, inicio, 120) * RNG.uniform(0.8, 1.2, n)
    elif falha == 2:  # Superaquecimento
        temp += _rampa(n, inicio, 35.0)
        corr += _rampa(n, inicio, 5.0)
    elif falha == 3:  # Falha mecânica
        vib += _rampa(n, inicio, 6.0)
        temp += _rampa(n, inicio, 20.0)
        corr += _rampa(n, inicio, 4.0)
        rpm -= _rampa(n, inicio, 300)

    # rótulo por leitura: 0 enquanto normal, classe de falha após o início da rampa
    rotulo = np.zeros(n, dtype=int)
    if falha != 0:
        rotulo[int(n * inicio):] = falha

    return temp, vib, corr, rpm, rotulo


def _classes_dos_motores():
    """Distribui as classes de falha entre os 20 motores."""
    classes = []
    for falha, frac in DISTRIB_FALHA.items():
        classes += [falha] * round(frac * N_MOTORES)
    # ajusta para totalizar exatamente N_MOTORES
    while len(classes) < N_MOTORES:
        classes.append(0)
    classes = classes[:N_MOTORES]
    RNG.shuffle(classes)
    return classes


def criar_banco(caminho="motor.db"):
    conn = sqlite3.connect(caminho)
    cur = conn.cursor()

    cur.executescript("""
        DROP TABLE IF EXISTS leituras;
        DROP TABLE IF EXISTS motores;
        DROP TABLE IF EXISTS tipos_falha;

        CREATE TABLE tipos_falha (
            codigo    INTEGER PRIMARY KEY,
            nome      TEXT NOT NULL,
            descricao TEXT NOT NULL
        );

        CREATE TABLE motores (
            motor_id    INTEGER PRIMARY KEY,
            fabricante  TEXT,
            modelo      TEXT,
            potencia_hp REAL,
            tensao_v    TEXT,
            tag         TEXT
        );

        CREATE TABLE leituras (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            motor_id     INTEGER NOT NULL,
            timestamp    TEXT NOT NULL,
            temperatura  REAL,
            vibracao     REAL,
            corrente     REAL,
            rotacao      REAL,
            falha        INTEGER NOT NULL,
            FOREIGN KEY (motor_id) REFERENCES motores(motor_id),
            FOREIGN KEY (falha)    REFERENCES tipos_falha(codigo)
        );
    """)

    cur.executemany(
        "INSERT INTO tipos_falha (codigo, nome, descricao) VALUES (?, ?, ?)",
        [
            (0, "Normal", "Operacao dentro dos parametros nominais"),
            (1, "Desbalanceamento", "Vibracao excessiva e rotacao instavel por desequilibrio do rotor"),
            (2, "Superaquecimento", "Temperatura e corrente acima do limite nominal por sobrecarga termica"),
            (3, "Falha Mecanica", "Queda de rotacao com vibracao, temperatura e corrente anomalas"),
        ],
    )

    classes = _classes_dos_motores()
    base_ts = datetime(2026, 5, 1, 8, 0, 0)

    total = 0
    for motor_id in range(1, N_MOTORES + 1):
        falha = classes[motor_id - 1]
        cur.execute(
            "INSERT INTO motores (motor_id, fabricante, modelo, potencia_hp, tensao_v, tag) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (motor_id, "WEG", "W22", 3.0, "220-254", f"MOT-{motor_id:03d}"),
        )

        temp, vib, corr, rpm, rotulo = gerar_serie(falha)
        linhas = []
        for i in range(N_LEITURAS):
            ts = base_ts + timedelta(seconds=i * INTERVALO_S)
            linhas.append((
                motor_id,
                ts.isoformat(sep=" "),
                round(float(temp[i]), 2),
                round(float(vib[i]), 3),
                round(float(corr[i]), 2),
                round(float(rpm[i]), 1),
                int(rotulo[i]),
            ))
        cur.executemany(
            "INSERT INTO leituras (motor_id, timestamp, temperatura, vibracao, corrente, rotacao, falha) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            linhas,
        )
        total += len(linhas)

    conn.commit()

    # validação
    cur.execute("SELECT COUNT(*) FROM leituras")
    n = cur.fetchone()[0]
    cur.execute("SELECT falha, COUNT(*) FROM leituras GROUP BY falha ORDER BY falha")
    distrib = cur.fetchall()
    conn.close()

    print(f"Arquivo {caminho} gerado com sucesso.")
    print(f"Total de leituras: {n}")
    print("Distribuicao por classe (rotulo por leitura):")
    nomes = {0: "Normal", 1: "Desbalanceamento", 2: "Superaquecimento", 3: "Falha Mecanica"}
    for cod, qtd in distrib:
        print(f"  {cod} - {nomes[cod]:18s}: {qtd:6d} ({100*qtd/n:.1f}%)")


if __name__ == "__main__":
    criar_banco()
