# Building BlueCord APK

Cette guide explique comment créer l'APK Android de BlueCord.

## 🚀 Méthode 1 : Build APK Local (Recommandé)

### Prérequis
- Node.js 16+ instalé
- Java Development Kit (JDK) 11+
- Android SDK avec API 30+
- 10 GB d'espace disque libre

### Installation complète

```bash
# 1. Installer les dépendances globales
npm install -g eas-cli expo-cli

# 2. Aller dans le dossier mobile
cd mobile

# 3. Installer les dépendances
npm install

# 4. Initialiser Expo (si première fois)
npx expo-cli start

# 5. Builder l'APK
npx eas-cli build --platform android --local
```

**Résultat:** Fichier APK généré dans `/mobile/dist/`

---

## ☁️ Méthode 2 : Build Cloud (Plus Facile)

### Étapes

```bash
# 1. Se connecter à Expo
npx eas-cli login

# 2. Initialiser le projet
cd mobile
npx eas-cli build:configure --platform android

# 3. Builder sur les serveurs Expo
npx eas-cli build --platform android

# 4. Télécharger l'APK généré
# Un lien de téléchargement sera fourni après le build
```

**Avantages:**
- Pas besoin d'installer Android SDK
- Plus rapide et fiable
- 30 minutes de build gratuit par mois

---

## 🔧 Méthode 3 : Build APK Directe (Sans Expo)

Si vous avez Android Studio d'installé :

```bash
cd mobile

# Générer le APK signé
npx react-native run-android --variant release

# Ou avec Gradle
./android/gradlew build -DversionCode=1 -DversionName=2.7.4
```

---

## 📱 Installation sur Téléphone

### Option A : Via Câble USB
```bash
# Brancher le téléphone en USB
adb install -r bluecord-2.7.4.apk
```

### Option B : Fichier Direct
1. Copier le fichier `.apk` sur le téléphone
2. Ouvrir le gestionnaire de fichiers
3. Taper sur le fichier `.apk` pour installer

### Option C : Partage Internet
```bash
# Partager le fichier via serveur local
python3 -m http.server 8000
# Puis accéder depuis le téléphone: http://192.168.x.x:8000/bluecord.apk
```

---

## 📋 Configuration APK

Fichier: `eas.json` (à créer si besoin)

```json
{
  "build": {
    "production": {
      "android": {
        "buildType": "apk"
      }
    },
    "preview": {
      "android": {
        "buildType": "apk"
      }
    },
    "development": {
      "android": {
        "buildType": "apk"
      }
    }
  }
}
```

---

## 🐛 Troubleshooting

### Erreur: "No Android SDK found"
```bash
# Installer Android SDK
npx expo-cli doctor

# Ou définir manuellement
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/tools
```

### Erreur: "Build timeout"
- Augmenter le timeout dans `eas.json`
- Utiliser la méthode cloud au lieu de local

### APK ne s'installe pas
- Vérifier que "Sources inconnues" est activé dans Paramètres
- Réduire la taille en supprimant les assets inutiles
- Vérifier la version minimum Android (minSdkVersion: 21)

### Erreur de permission
```bash
# Donner les permissions à gradlew
chmod +x android/gradlew
```

---

## 📊 Taille APK

- **APK seul:** ~50 MB
- **Avec assets:** ~100 MB
- **Minifié:** ~30 MB

### Optimiser la taille
```bash
# Supprimer les assets inutiles
rm -rf node_modules/.cache

# Minifier le code
npx react-native bundle --platform android --dev false --entry-file index.js --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res
```

---

## 🔐 Signer l'APK

Pour distribuer officiellement :

```bash
# 1. Créer une clé de signature
keytool -genkey -v -keystore bluecord-key.keystore -keyalg RSA -keysize 2048 -validity 10000 -alias bluecord-key

# 2. Configurer dans eas.json
{
  "submit": {
    "production": {
      "android": {
        "serviceAccount": "./key.json"
      }
    }
  }
}

# 3. Builder avec signature
npx eas-cli build --platform android
```

---

## ✅ Vérifier le Build

```bash
# Vérifier les permissions
aapt dump permissions bluecord-2.7.4.apk

# Vérifier la signature
jarsigner -verify bluecord-2.7.4.apk

# Vérifier les dépendances
aapt dump badging bluecord-2.7.4.apk
```

---

## 📤 Upload sur Play Store

```bash
# 1. Créer un compte développeur Google Play ($25)
# 2. Créer une application
# 3. Préparer les assets (icône, screenshots, etc.)
# 4. Uploader l'APK signé
# 5. Soumettre pour révision

npx eas-cli submit --platform android --path ./bluecord-2.7.4.apk
```

---

## 💡 Tips & Tricks

### Fast Build
```bash
# Build optimisé pour développement
npx eas-cli build --platform android --wait=false
```

### Debug APK
```bash
# APK avec debug info
npx react-native run-android --variant debug
```

### Test Before Build
```bash
# Tester en local avant de builder
npx expo-cli start --android
```

---

## 📞 Support

- 📖 Docs: https://docs.expo.dev
- 🐛 Issues: GitHub Issues
- 💬 Community: Expo Discord

---

**Bon build!** 🎉
