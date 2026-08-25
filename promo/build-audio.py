#!/usr/bin/env python3
"""Génère la voix off française et l'assemble sur la durée de la vidéo."""
import json, subprocess, os, sys, wave, contextlib

ICI    = os.path.dirname(os.path.abspath(__file__))
VOIX   = os.environ.get("VOIX", "/tmp/claude-0/-home-user-JZ-HACKK/94986eff-3085-57c3-be49-20a04d5308df/scratchpad/voices/fr_FR-siwis-medium.onnx")
TMP    = "/tmp/claude-0/-home-user-JZ-HACKK/94986eff-3085-57c3-be49-20a04d5308df/scratchpad/vo"
DECAL  = float(os.environ.get("DECAL", 0.9))    # secondes coupées au début de la vidéo
VITESSE= float(os.environ.get("VITESSE", 1.18)) # accélération appliquée à la vidéo
import imageio_ffmpeg; FF = imageio_ffmpeg.get_ffmpeg_exe()

os.makedirs(TMP, exist_ok=True)
marks = json.load(open(os.path.join(ICI, "marks.json"), encoding="utf-8"))

def duree(w):
    with contextlib.closing(wave.open(w)) as f:
        return f.getnframes() / f.getframerate()

pistes = []
print(f"{'#':>2} {'début':>7} {'durée':>6} {'place':>7}  texte")
for i, m in enumerate(marks):
    wav = os.path.join(TMP, f"l{i}.wav")
    subprocess.run([sys.executable, "-m", "piper", "-m", VOIX, "-f", wav],
                   input=m["texte"].encode(), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    debut = max(0.0, (m["t"] - DECAL) / VITESSE)
    d = duree(wav)
    dispo = ((marks[i+1]["t"] - DECAL) / VITESSE - debut) if i+1 < len(marks) else 99
    alerte = "  ⚠ dépasse sur la suivante" if d > dispo + 0.15 else ""
    print(f"{i:>2} {debut:7.2f} {d:6.2f} {dispo:7.2f}  {m['texte'][:52]}{alerte}")
    pistes.append((debut, wav, d))

# mixage : chaque réplique décalée à sa position, le tout fondu ensemble
entrees, filtres, labels = [], [], []
for i, (debut, wav, _) in enumerate(pistes):
    entrees += ["-i", wav]
    filtres.append(f"[{i}:a]adelay={int(debut*1000)}|{int(debut*1000)},volume=1.6[a{i}]")
    labels.append(f"[a{i}]")
mix = ";".join(filtres) + ";" + "".join(labels) + f"amix=inputs={len(pistes)}:normalize=0:dropout_transition=0[out]"
sortie = os.path.join(TMP, "voix.wav")
subprocess.run([FF, "-y", *entrees, "-filter_complex", mix, "-map", "[out]",
                "-ar", "48000", "-ac", "2", sortie, "-loglevel", "error"], check=True)
print("\nvoix off :", sortie, f"({duree(sortie):.1f}s)")
