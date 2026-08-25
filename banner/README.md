# Bannière animée

Deux façons d'animer l'illustration `source.png`.

## 1. La page web — `banner.html`

Ouvre le fichier dans un navigateur (double-clic suffit, l'image est intégrée
dedans, aucun fichier à côté n'est nécessaire).

- quatre couches à couper/remettre : pétales, zoom lent, reflet, signature ;
- la signature (« JZ » / « omega ») se modifie en cliquant dessus ;
- le curseur **Densité** règle le nombre de pétales ;
- **Mode capture** affiche la bannière seule, plein écran, pour l'enregistrer.

## 2. Les GIF prêts à l'emploi

| Fichier | Taille | Usage |
| --- | --- | --- |
| `banner-discord.gif` | 680 × 240 | bannière de profil Discord |
| `banner-wide.gif` | 960 × 384 | en-tête large (2.5:1, le format d'origine) |

Les deux bouclent sans saut : pétales, zoom et reflet reviennent exactement à
leur point de départ à la dernière image.

### Les régénérer

```sh
pip install pillow
python3 banner/make_gif.py banner/source.png -o banner/banner-discord.gif --preset discord
```

Options : `--preset discord|server|wide`, `--frames`, `--fps`, `--petals`,
`--seed`. Plus d'images = plus fluide mais fichier plus lourd — Discord refuse
au-delà de 10 Mo.
