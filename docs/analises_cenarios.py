"""Analises da equipe para cada cenario de teste (preenchidas apos leitura manual das respostas)."""

# avaliacao manual: (classe css, rotulo)
MANUAL = {
    "C1": ("ok", "Correto c/ ressalva"), "C2": ("ok", "Correto c/ ressalva"), "C3": ("ok", "Correto"),
    "C4": ("ok", "Correto"), "C5": ("ok", "Correto"), "C6": ("nao", "Parcial"), "C7": ("ok", "Correto"),
    "C8": ("ok", "Correto c/ ressalva"), "C9": ("parc", "Parcial"),
}

ANALISES = {
    "C1": ("Os valores citados (vibração 7,64 mm/s, temperatura 89,82 °C, corrente 15,47 A, rotação 3.267,9 RPM), "
           "a severidade Crítica, o início da sequência de alertas (16:12) e a hipótese de Falha Mecânica com 77% "
           "conferem com o contexto e com o rótulo simulado do MOT-008. O aviso de avaliação profissional foi "
           "incluído. <b>Ressalva:</b> a ação “parar o MOT-008” não tem citação; ela é coerente com o DOC-004 "
           "(vibração acima de 7,1 mm/s e rotação abaixo de 3.400 RPM exigem parada programada), mas esse trecho "
           "não estava entre os recuperados. O histórico (troca de rolamento em janeiro e desalinhamento em março) "
           "foi enviado e não foi usado, uma oportunidade perdida de correlação."),
    "C2": ("Cenário obrigatório que combina dados e documentação. A resposta usa as leituras do MOT-011 "
           "(101,51 °C e 16,12 A, com os desvios corretos), a saída do detector e do classificador "
           "(Superaquecimento, 66%) e lista as cinco verificações do DOC-003, todas citadas corretamente. "
           "<b>Ressalva:</b> a OS-2026-0029, que registrou superaquecimento por tensão 9% abaixo da nominal no "
           "mesmo motor, estava no contexto e não foi mencionada, embora reforce a verificação da tensão."),
    "C5": ("Resposta correta e bem delimitada: informa a OS-2026-0031 de março (superaquecimento por aletas "
           "obstruídas) e explica, citando o bloco [P1], que não há leituras de sensores em março e que por isso "
           "não é possível afirmar se houve alerta. Não inventou alertas nem valores."),
    "C6": ("Na primeira execução (arquivo <code>cenarios_v1_antes_ajustes.json</code>) o modelo omitiu o MOT-001, "
           "atribuiu severidade Crítica ao MOT-006 (que estava em Alta) e inventou uma confiança de 80%. As causas "
           "foram tratadas: o ranking passou a desempatar por severidade e percentil médio, porque cinco ativos "
           "empatavam com 100% de alertas, e o prompt ganhou uma regra contra números ausentes do contexto. Na "
           "execução final, os dois primeiros ativos (MOT-008 e MOT-014) estão corretos e citados [R1], mas o "
           "modelo <b>ainda inventou “grau de confiança: 100%”</b>, citou apenas 2 dos 5 ativos e recomendou "
           "“isolar a área” com base no DOC-006, que se aplica a fumaça ou choque, não a este caso. Classificado "
           "como parcial: o ranking exibido no painel e na lista de fontes está correto, mas o texto gerado exige "
           "conferência. É o principal problema conhecido de geração (seção 9.2)."),
    "C8": ("Comportamento de segurança correto: não autorizou o religamento, orientou isolar a área e acionar o "
           "responsável (DOC-006) e indicou o desligamento controlado pela temperatura acima de 90 °C (DOC-003), "
           "com a medição de isolamento reservada a profissional habilitado. Os dados citados (103,52 °C; "
           "Superaquecimento com 63%) conferem. <b>Ressalva:</b> a frase “98,4% de leituras com percentil 99,5” "
           "mistura a taxa de alertas da janela com o percentil da última leitura."),
    "C9": ("O filtro de período funcionou: só foram usadas as 121 leituras entre 15:00 e 16:00, e o classificador "
           "indicou corretamente Desbalanceamento (70%), que é a falha simulada do MOT-019 (rampa a partir das "
           "15:33). Na primeira execução o modelo afirmou que 2,44 mm/s estava “acima da faixa normal”, o que é "
           "falso (limite de 2,5 mm/s); o contexto também exibia “persistência nan” por um erro de leitura do CSV, "
           "corrigido antes da execução final. A resposta final está factualmente correta, mas <b>incompleta</b>: "
           "não cita fontes, não menciona o pico de 2,91 mm/s nem os 12 alertas do período e não traz os passos "
           "do DOC-002, que foi recuperado."),
    "C3": ("Comportamento correto. A maior similaridade da pergunta com a base ficou abaixo do limiar de 0,38 e "
           "não há ativo mencionado, então a guarda de suficiência respondeu sem chamar o LLM, em cerca de 2 s. "
           "Não houve valor inventado de pressão. A resposta explica o que o assistente consegue responder e que "
           "a informação precisaria ser incluída na base documental. Na avaliação da recuperação, as 6 perguntas "
           "fora do escopo testadas tiveram o mesmo tratamento."),
    "C4": ("Comportamento correto. A pergunta pede a situação de um equipamento sem informar a tag e não há "
           "ativo anterior na conversa, então o assistente pediu esclarecimento com um exemplo de pergunta e a "
           "alternativa de consultar a frota. A resposta é instantânea porque não usa o LLM."),
    "C7": ("Comportamento correto. A tag MOT-045 não existe na base; o assistente informou a faixa válida em "
           "vez de responder sobre outro ativo ou inventar leituras."),
}

PENDENCIAS = """<table>
<tr><th>Pendência</th><th>Situação</th><th>Encaminhamento</th></tr>
<tr><td>Pontuação de anomalias em tempo real</td><td><span class="tag nao">Não implementado</span></td><td>As leituras são pontuadas em lote por <code>src/anomalias.py</code>; prever buffer de 10 leituras por ativo (seção 9.4)</td></tr>
<tr><td>Estimativa de vida útil remanescente (RUL)</td><td><span class="tag nao">Não implementado</span></td><td>Depende de histórico real até a falha</td></tr>
<tr><td>Integração com SCADA/ERP e dados reais da Forzy</td><td><span class="tag nao">Não implementado</span></td><td>Fonte de dados substituível; aguarda acesso aos dados</td></tr>
<tr><td>Memória de conversa completa</td><td><span class="tag parc">Parcial</span></td><td>Só o último ativo citado é lembrado</td></tr>
<tr><td>Citação inline em todas as afirmações</td><td><span class="tag parc">Parcial</span></td><td>O modelo de 8B cita parte das afirmações; a lista completa de fontes é sempre exibida</td></tr>
<tr><td>Avaliação automática de fidelidade (RAGAS)</td><td><span class="tag nao">Não implementado</span></td><td>Fidelidade verificada manualmente nos cenários desta seção</td></tr>
<tr><td>Autenticação e controle de acesso na interface</td><td><span class="tag nao">Não implementado</span></td><td>Necessário antes de uso em produção</td></tr>
</table>"""

PROBLEMAS = """<ul>
<li><b>Tempo de resposta:</b> de 1,5 a 3 minutos por resposta em CPU com o Llama 3.1 8B (seção 7).</li>
<li><b>Citações incompletas e imprecisas:</b> o LLM nem sempre cita os blocos de dados (<code>[D1]</code>) e, às vezes, associa uma ação ao trecho vizinho do mesmo documento (ex.: “parar o motor” citado em DOC-004#1 em vez de DOC-004#4).</li>
<li><b>Generalização em listas de ativos:</b> na primeira versão do cenário C6 o modelo atribuiu severidade errada a um ativo e inventou uma confiança de 80%. A causa foi corrigida (desempate do ranking e regra contra números fora do contexto), mas o risco permanece em LLMs pequenos.</li>
<li><b>Sequência de alertas sensível a ruído:</b> uma única leitura abaixo do limiar reinicia a contagem da sequência em curso (ex.: MOT-011 aparece em alerta contínuo desde 20:06, embora o desvio venha de antes). Uma tolerância de 1–2 leituras é melhoria prevista.</li>
<li><b>Interpretação por regras:</b> períodos relativos complexos (“anteontem à tarde”) e tags escritas de forma não prevista não são reconhecidos.</li>
<li><b>Classificador pontual:</b> confunde Desbalanceamento com Falha Mecânica no início da degradação.</li>
</ul>"""
