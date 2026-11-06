"""
capturar_telas.py — Capturas de tela da interface Streamlit para as evidencias (Playwright + Edge/Chrome)

Pre-requisito: app em execucao (streamlit run app.py --server.headless true) e Ollama ativo.
Uso: python testes/capturar_telas.py [--url http://localhost:8501]
"""
import argparse
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

EV = Path(__file__).resolve().parents[1] / "evidencias"


def esperar_resposta(pg, n=1, timeout=420_000):
    pg.wait_for_function(f"document.body.innerText.split('⏱️').length > {n}", timeout=timeout)
    pg.wait_for_timeout(1500)


def main(url):
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": 1400, "height": 2000}, device_scale_factor=1)

        # 1) consulta de anomalia com fontes expandidas
        pg = ctx.new_page()
        pg.goto(f"{url}/?q={quote('Como está o MOT-008 agora? Há alguma anomalia?')}")
        esperar_resposta(pg)
        pg.screenshot(path=EV / "tela_01_resposta_mot008.png", full_page=True)
        pg.get_by_text("Fontes consultadas").first.click()
        pg.wait_for_timeout(1200)
        pg.screenshot(path=EV / "tela_02_fontes_consultadas.png", full_page=True)

        # 2) pergunta ambigua seguida de pergunta fora do escopo (respostas sem LLM)
        pg = ctx.new_page()
        pg.goto(url)
        pg.wait_for_selector("textarea", timeout=60_000)
        for i, q in enumerate(["Como está o motor? Está normal?",
                               "Qual é a pressão de descarga recomendada para o compressor GA55?"], 1):
            pg.locator("textarea").fill(q)
            pg.keyboard.press("Enter")
            esperar_resposta(pg, i)
        pg.screenshot(path=EV / "tela_03_ambigua_insuficiente.png", full_page=True)

        # 3) painel da frota
        pg.get_by_role("tab", name="📊 Painel da frota").click()
        pg.wait_for_timeout(4000)
        pg.screenshot(path=EV / "tela_04_painel_frota.png", full_page=True)
        b.close()
    print("capturas salvas em", EV)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    main(ap.parse_args().url)
