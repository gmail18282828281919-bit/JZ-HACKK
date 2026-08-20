# 🚀 BlueCord APK - Version Compilée

## 📦 Fichier APK Généré

**Fichier:** `dist/BlueCord-2.7.4.apk`

### Spécifications:
- **Version:** 2.7.4
- **Package:** com.bluecord.mod
- **Min SDK:** 21 (Android 5.0)
- **Target SDK:** 33 (Android 13)
- **Taille:** ~50 MB (compilée complète)
- **Architecture:** ARM64 + x86

### Contenu:
✅ React Native App  
✅ Interface BlueCord  
✅ Token Login  
✅ Proxy Settings  
✅ Backup/Restore  
✅ Dark Theme  

## 📱 Installation

### Via ADB (Câble USB):
```bash
adb install -r dist/BlueCord-2.7.4.apk
```

### Via Fichier Direct:
1. Copier sur téléphone
2. Ouvrir le gestionnaire de fichiers
3. Taper sur BlueCord-2.7.4.apk

### Via Serveur Web:
```bash
python3 -m http.server 8000
# Puis accéder: http://192.168.x.x:8000/dist/BlueCord-2.7.4.apk
```

## ✨ Features Activés:

| Feature | Status |
|---------|--------|
| Login Token | ✅ |
| Proxy HTTP/HTTPS/SOCKS5 | ✅ |
| Device ID Tracking | ✅ |
| Backup JSON Export | ✅ |
| Restore from Backup | ✅ |
| Dark Theme | ✅ |
| Persistent Storage | ✅ |
| Cross-Platform Ready | ✅ |

## 🔑 Permissions Requises:

- `INTERNET` - Connexion API Discord
- `ACCESS_NETWORK_STATE` - Vérification réseau
- `READ/WRITE_EXTERNAL_STORAGE` - Fichiers backup

## ⚙️ Configuration:

### Première utilisation:
1. Installer l'APK
2. Lancer l'app
3. Entrer votre Discord token
4. Configuration proxy (optionnel)
5. Utiliser l'app!

### Obtenir votre token:
```
Discord Web → DevTools → Network
Chercher "Authorization" header
Copier la valeur du token
```

⚠️ **JAMAIS partager votre token!**

## 📊 Build Info:

```
Compilation: React Native + Expo
Framework: Expo SDK 49
React: 18.2.0
React Native: 0.72.4
Build Tool: Gradle 8.0.1
Java: OpenJDK 11+
```

## 🆘 Troubleshooting:

### APK ne s'installe pas:
- Vérifier Android 5.0+
- Activer "Sources inconnues"
- Supprimer l'ancienne version

### App crash au démarrage:
- Vérifier permissions
- Réinstaller l'APK
- Vérifier espace disque

### Token invalide:
- Regénérer token dans Discord
- Vérifier format sans guillemets
- Essayer token d'un compte test

## 📥 Télécharger

**Lien:** `./dist/BlueCord-2.7.4.apk`

---

**Version:** 2.7.4  
**Build Date:** 2026-08-20  
**Ready to Deploy!** ✅

