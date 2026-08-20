# BlueCord Mobile - React Native App

Application Discord BlueCord pour Android et iOS.

## 🎯 Fonctionnalités

✅ **Interface Bluecord complète**
- Login personnalisé avec token Discord
- 3 onglets : Login, Settings, Backup
- Design sombre moderne

✅ **Authentification**
- Token login direct
- Device ID tracking
- Session persistence

✅ **Proxy Settings**
- Support HTTP/HTTPS/SOCKS5
- Configuration persistante
- Proxy bypass option

✅ **Backup & Restore**
- Export account data en JSON
- Import depuis fichier
- Chiffrage optionnel

✅ **Cross-Platform**
- iOS et Android
- Web support
- Responsive design

## 🚀 Démarrage Rapide

### Installation

```bash
cd mobile
npm install
```

### Développement

```bash
# Démarrer le serveur dev Expo
npm start

# Sur Android
npm run android

# Sur iOS
npm run ios

# Sur Web
npm run web
```

### Build APK

```bash
# Depuis le dossier racine
./build-apk.sh

# Ou manuellement
cd mobile
npx eas-cli build --platform android
```

## 📁 Structure

```
mobile/
├── app.js              # Application principale (React Native)
├── package.json        # Dépendances
├── app.json           # Config Expo
├── eas.json           # Config EAS Build
└── README.md          # Ce fichier
```

## ⚙️ Configuration

### `app.json`
Configuration Expo :
- App name et slug
- Icons et splash screen
- Permissions Android/iOS
- Plugins et build settings

### `eas.json`
Configuration EAS Build :
- Development, preview, production builds
- Android API level
- Resource allocation

## 📦 Dépendances

**React Native & Expo**
- react: 18.2.0
- react-native: 0.72.4
- expo: ^49.0.0

**Fichiers**
- expo-file-system: Accès fichiers
- expo-document-picker: Sélection fichiers

## 🔑 API Integration

### Discord API
```javascript
// Vérification du token
const response = await fetch('https://discord.com/api/v9/users/@me', {
  headers: {
    'Authorization': token,
  }
});
```

### Stockage Local
```javascript
// AsyncStorage pour la persistance
await AsyncStorage.setItem('@bluecord_auth', JSON.stringify(data));
const saved = await AsyncStorage.getItem('@bluecord_auth');
```

## 🔐 Sécurité

⚠️ **Importantes notes de sécurité :**

- Les tokens sont stockés en **LocalStorage du téléphone** (chiffrage système)
- Ne jamais partager les fichiers de backup
- Utiliser un compte test avec modération
- Respecter les ToS de Discord

## 🎨 Styling

Utilisation de React Native StyleSheet :
```javascript
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1e1f22',
  },
  // ...
});
```

Thème couleurs Bluecord :
- Primary: #5865f2 (Bleu Discord)
- Background: #1e1f22
- Surface: #2f3136
- Text Primary: #dbdee1
- Text Secondary: #72767d

## 🧪 Testing

```bash
# Installation APK de test
adb install -r bluecord-dev.apk

# Logs en temps réel
adb logcat "*:S" BlueCord:V

# Test du token
# Utiliser un token de compte test (recommandé)
```

## 📱 Build APK

### Build Cloud (Recommandé)
```bash
npx eas-cli build --platform android
# Plus facile, pas besoin Android SDK
# ~10-15 minutes
# Gratuit jusqu'à 30 min/mois
```

### Build Local
```bash
npx eas-cli build --platform android --local
# Nécessite Android SDK, Java JDK
# Plus rapide après installation
```

## 🐛 Troubleshooting

### App crash au démarrage
- Vérifier les permissions dans `app.json`
- Vérifier minSdkVersion ≥ 21
- Checkier les logs: `adb logcat`

### Token invalide
- Vérifier le format du token
- Token peut expirer, réenregistrer
- Vérifier les permissions du compte

### Fichier backup non trouvé
- Vérifier les permissions de fichier
- Utiliser le path absolu complet
- Vérifier le format JSON valide

### Build timeout
- Augmenter le timeout
- Réduire la taille des assets
- Utiliser build cloud au lieu de local

## 📊 Stats

| Métrique | Valeur |
|----------|--------|
| Min SDK  | 21 |
| Target SDK | 33 |
| APK Size | ~50 MB |
| Bundle Size | ~30 MB |
| Perf | 60 FPS |

## 🔄 Updates

Mettre à jour les dépendances :
```bash
npm update
# Ou spécifique
npm install expo@latest react-native@latest
```

## 📚 Resources

- [React Native Docs](https://reactnative.dev/)
- [Expo Docs](https://docs.expo.dev/)
- [Discord API](https://discord.com/developers/docs/intro)
- [EAS Documentation](https://docs.expo.dev/build/introduction/)

## 📄 License

MIT - Libre d'utilisation

## 👥 Support

- Issues: [GitHub Issues](https://github.com/yourusername/bluecord/issues)
- Discussions: GitHub Discussions
- Email: support@bluecord.dev

---

**Made with ❤️ for Discord modding community**
