# Bannière animée

Deux façons d'animer l'illustration `source.png`.

## 1. La page web — `banner.html`

Ouvre le fichier dans un navigateur (double-clic suffit, l'image est intégrée
dedans, aucun fichier à côté n'est nécessaire).

- quatre couches à couper/remettre : pétales, zoom lent, reflet, signature ;
- la signature est masquée par défaut ; si tu l'actives, le texte se modifie
  en cliquant dessus ;
- le curseur **Densité** règle le nombre de pétales ;
- **Mode capture** affiche la bannière seule, plein écran, pour l'enregistrer ;
- **Télécharger en PNG** exporte la bannière seule en `1983 × 793`, avec les
  pétales et le reflet tels qu'ils sont à l'instant du clic, et rien d'autre.

## 2. Les fichiers prêts à l'emploi

| Fichier | Taille | Usage |
| --- | --- | --- |
| `banner.mp4` | 1920 × 768 | version animée, 8 s en boucle — s'enregistre dans la galerie du téléphone |
| `banner-1983x793.png` | 1983 × 793 | image fixe pleine résolution, sans texte |
| `banner-discord-680x240.png` | 1360 × 480 | bannière de profil Discord (×2) |
| `banner-discord.gif` | 680 × 240 | bannière de profil Discord |
| `banner-wide.gif` | 960 × 384 | en-tête large (2.5:1, le format d'origine) |

Les deux bouclent sans saut : pétales, zoom et reflet reviennent exactement à
leur point de départ à la dernière image.

### Les régénérer

```sh
pip install pillow imageio-ffmpeg
python3 banner/make_gif.py banner/source.png -o banner/banner-discord.gif --preset discord
python3 banner/make_gif.py banner/source.png -o banner/banner.mp4 --preset hd --fps 24
```

L'extension de `-o` décide du format : `.gif` (Discord, forums) ou `.mp4`
(H.264, ce que lisent les galeries de téléphone).

Options : `--preset discord|server|wide`, `--frames`, `--fps`, `--petals`,
`--seed`. Plus d'images = plus fluide mais fichier plus lourd — Discord refuse
au-delà de 10 Mo.
