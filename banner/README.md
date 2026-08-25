# Bannière animée

Deux façons d'animer l'illustration `source.png`.

## 1. La page web — `banner.html`

Ouvre le fichier dans un navigateur (double-clic suffit, l'image est intégrée
dedans, aucun fichier à côté n'est nécessaire).

- couches à couper/remettre : pétales, mouvement, signature (coupée par
  défaut) ;
- la signature est masquée par défaut ; si tu l'actives, le texte se modifie
  en cliquant dessus ;
- le curseur **Densité** règle le nombre de pétales ;
- **Mode capture** affiche la bannière seule, plein écran, pour l'enregistrer ;
- **GIF animé** télécharge la bannière animée en `1200 × 480` ;
- **PNG** exporte l'image fixe en `1983 × 793`, avec les pétales et le reflet
  tels qu'ils sont à l'instant du clic.

## 2. Les fichiers prêts à l'emploi

| Fichier | Taille | Usage |
| --- | --- | --- |
| `banner-4k.mp4` | 3840 × 1536 | version animée 4K, 30 i/s, 10 s |
| `banner.mp4` | 1920 × 768 | même chose en 1080p, plus léger |
| `banner-1983x793.png` | 1983 × 793 | image fixe pleine résolution, sans texte |
| `banner-discord-680x240.png` | 1360 × 480 | bannière de profil Discord (×2) |
| `banner.gif` | 960 × 384 | GIF animé pleine largeur, 8 Mo |
| `banner-discord.gif` | 680 × 240 | bannière de profil Discord, 4,9 Mo |
| `banner-wide.gif` | 960 × 384 | en-tête large (2.5:1, le format d'origine) |

Tout boucle sans saut : le vent, les pétales et le reflet reviennent exactement
à leur point de départ à la dernière image.

Trois zones bougent séparément, chacune avec un masque à bords doux :

| Zone | Mouvement |
| --- | --- |
| décor (branches, fleurs, ciel) | ondulation de vent à deux fréquences |
| tête | part à gauche, revient, avec un léger balancement |
| bras | part à droite pendant que la tête part à gauche |
| œil fermé | s'ouvre quand la tête part, se referme au retour |

L'œil ouvert n'existe pas dans l'illustration : `make_open_eye.py` le
reconstruit en recopiant l'autre œil, retourné, redimensionné et posé avec un
masque à bords doux. Le générateur fond les deux images l'une dans l'autre au
fil de la boucle.

```sh
python3 banner/make_open_eye.py banner/source.png -o banner/source-open.png
python3 banner/make_gif.py banner/source.png --open-eyes banner/source-open.png \
    -o banner/banner.gif --preset wide
```

Tout est en sinus d'un tour complet, donc la dernière image retombe exactement
sur la première. `--wind 0` fige l'image, `--wind 0.01` double l'amplitude.

L'image de départ fait 1983 px de large : le 4K est un agrandissement, il
n'invente pas de détail, mais le mouvement et l'encodage, eux, sont bien en 4K.

Un pétale met exactement une boucle à traverser la hauteur : c'est donc la
durée de la boucle (`--frames` ÷ `--fps`) qui règle la vitesse de chute.
Boucle longue = chute lente.

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
