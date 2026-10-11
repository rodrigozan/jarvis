"""Modo show: duas palmas -> jingle -> interface web -> conversa por voz.

Variáveis de ambiente:
  JARVIS_CLAP_THRESH  pico mínimo (0.0-1.0) para contar como palma. Padrão 0.35.
                      Maior = menos sensível; menor = mais sensível.
  JARVIS_MIC          índice ou parte do nome do microfone (ver --listar).

Uso:
  jarvis-show              espera as duas palmas
  jarvis-show --calibrar   mostra o nível do microfone em tempo real
  jarvis-show --listar     lista os microfones disponíveis
"""

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parent.parent
JINGLE = ROOT / "voz" / "assets" / "jingle.mp3"
WEB_URL = "http://127.0.0.1:8000"

RATE = 16000
BLOCK = 320  # 20 ms
THRESH = float(os.environ.get("JARVIS_CLAP_THRESH", "0.35"))
MIC = os.environ.get("JARVIS_MIC") or None
if MIC is not None and MIC.isdigit():
    MIC = int(MIC)

MIN_GAP = 0.12  # s entre as palmas (abaixo disso é eco da mesma palma)
MAX_GAP = 0.9  # s; acima disso não conta como "duas seguidas"


def listar():
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"{i:3d}  {d['name']}")


def calibrar():
    print(f"Limiar atual: {THRESH:.2f}  (Ctrl+C para sair)")
    with sd.InputStream(device=MIC, channels=1, samplerate=RATE, blocksize=BLOCK) as s:
        while True:
            pico = float(np.abs(s.read(BLOCK)[0]).max())
            barra = "#" * int(pico * 50)
            marca = "  <-- PALMA" if pico >= THRESH else ""
            print(f"\r{pico:.2f} {barra:<50}{marca}   ", end="", flush=True)


def esperar_duas_palmas():
    print(f"Escutando... bata palma 2x (limiar {THRESH:.2f}, Ctrl+C para sair)")
    ultima = None
    acima = False
    with sd.InputStream(device=MIC, channels=1, samplerate=RATE, blocksize=BLOCK) as s:
        while True:
            pico = float(np.abs(s.read(BLOCK)[0]).max())
            agora = time.monotonic()
            if pico >= THRESH and not acima:  # borda de subida = início de uma palma
                acima = True
                if ultima is not None and MIN_GAP <= agora - ultima <= MAX_GAP:
                    return
                if ultima is None or agora - ultima > MIN_GAP:
                    ultima = agora
            elif pico < THRESH * 0.5:
                acima = False


def tocar_jingle():
    if not JINGLE.exists():
        return
    try:
        import soundfile as sf

        dados, taxa = sf.read(str(JINGLE))
        sd.play(dados, taxa)
        sd.wait()
    except Exception as e:  # mp3 não suportado pelo libsndfile, por exemplo
        print(f"Não consegui tocar o jingle ({e}); seguindo sem ele.")


def servidor_no_ar():
    try:
        urllib.request.urlopen(WEB_URL, timeout=2)
        return True
    except Exception:
        return False


def abrir_interface():
    if not servidor_no_ar():
        print("Subindo a interface web...")
        subprocess.run(["uv", "run", "jarvis", "start"], cwd=ROOT)
        for _ in range(40):
            if servidor_no_ar():
                break
            time.sleep(1)
    webbrowser.open(WEB_URL)


def main():
    if "--listar" in sys.argv:
        return listar()
    if "--calibrar" in sys.argv:
        return calibrar()
    esperar_duas_palmas()
    print("Palmas detectadas!")
    tocar_jingle()
    abrir_interface()
    os.chdir(ROOT)
    os.execvp("uv", ["uv", "run", "jarvis", "chat", "--voice"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
