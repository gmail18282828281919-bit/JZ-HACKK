# JZ-AI — application Android

Client de chat pour ton serveur [JZ-AI](../ai/README.md). Kotlin, vues classiques
(pas de Compose), réponses en **streaming** token par token, **pièces jointes**
(fichiers, code, documents, images).

## Récupérer l'apk sans rien installer

Le workflow [`build-apk.yml`](../.github/workflows/build-apk.yml) compile l'apk à
chaque push sur `apk/`.

1. Va sur l'onglet **Actions** du dépôt GitHub.
2. Ouvre le dernier run **Build APK** (coche verte).
3. En bas, section **Artifacts** → télécharge **JZ-AI-apk**.
4. Décompresse le `.zip`, tu obtiens `app-debug.apk`.
5. Sur le téléphone : autorise « installer des applis inconnues » pour ton
   navigateur ou explorateur de fichiers, puis ouvre le `.apk`.

Tu peux aussi lancer le build à la main : **Actions → Build APK → Run workflow**.

## Configurer l'app

Au premier lancement, la fenêtre de réglages s'ouvre :

| Champ | Valeur |
|---|---|
| Adresse du serveur | `http://127.0.0.1:8000` (Termux sur le même téléphone) |
| Clé d'API | ta clé `jz-…` (`cat ~/jz-key.txt` dans Termux) |

La barre sous le titre indique `Connecté à jz-mini-1 (echo, sans vision)` quand
tout va bien. Le menu **⋮** permet de revenir aux réglages ou d'effacer la
conversation.

## Joindre un fichier

Le bouton **📎** ouvre le sélecteur de fichiers Android. Le fichier est envoyé au
serveur, qui en extrait le texte (code, PDF, DOCX, CSV, HTML…) et le donne au
modèle. Touche la pastille du fichier pour la retirer avant d'envoyer.

Limites : 8 Mio par fichier, 8 fichiers par message. Si tu n'écris rien, l'app
demande simplement « Analyse ce fichier. »

Les images ne sont réellement *lues* que si le serveur tourne avec un modèle
vision — sinon le modèle te dira qu'il ne peut pas les voir, au lieu d'inventer.
Voir [la section vision](../ai/README.md#images).

## Compiler soi-même

```bash
cd apk
./gradlew assembleDebug     # ou : gradle assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```

Nécessite le SDK Android et Java 17.

## Notes

- **La clé n'est pas dans l'apk.** Elle est saisie par l'utilisateur et rangée
  dans les SharedPreferences privées de l'app. Un apk se décompile trivialement :
  n'y mets jamais de secret.
- `usesCleartextTraffic="true"` est activé car le serveur est en HTTP simple —
  y compris pour `127.0.0.1`, qu'Android bloquerait sinon depuis Android 9.
- L'apk produit est un build **debug**, signé avec la clé de debug d'Android.
  C'est fait pour tester, pas pour le Play Store.
