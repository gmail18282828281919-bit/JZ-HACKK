# Installation Guide - Discord BlueCord Mod

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/discord-bluecord-mod.git
cd discord-bluecord-mod
npm install
npm run build
```

### 2. Inject into Discord

Choose one method:

#### Method A: DevTools Console (Easiest)

1. Open Discord (discord.com)
2. Press `F12` to open DevTools
3. Go to Console tab
4. Paste this code:

```javascript
const script = document.createElement('script');
script.src = 'file:///path/to/discord-mod/dist/index.js';
script.type = 'module';
document.head.appendChild(script);
```

Replace `/path/to/discord-mod/` with your actual path.

#### Method B: Tampermonkey/Greasemonkey (Recommended)

1. Install [Tampermonkey](https://www.tampermonkey.net/) or Greasemonkey
2. Create a new script with this content:

```javascript
// ==UserScript==
// @name Discord BlueCord Mod
// @namespace discord-bluecord-mod
// @version 2.7.4
// @description Discord client modification
// @author YourName
// @match https://discord.com/*
// @grant none
// @run-at document-start
// ==/UserScript==

(function() {
  const script = document.createElement('script');
  script.type = 'module';
  script.textContent = `
    import('./dist/index.js').catch(err => console.error('Failed to load mod:', err));
  `;
  document.head.appendChild(script);
})();
```

3. Save and enable the script

#### Method C: Browser Extension

1. Create `manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "Discord BlueCord Mod",
  "version": "2.7.4",
  "permissions": ["scripting"],
  "host_permissions": [
    "https://discord.com/*"
  ],
  "content_scripts": [{
    "matches": ["https://discord.com/*"],
    "js": ["inject.js"],
    "run_at": "document_start"
  }]
}
```

2. Create `inject.js`:

```javascript
const script = document.createElement('script');
script.type = 'module';
script.src = chrome.runtime.getURL('dist/index.js');
document.head.appendChild(script);
```

3. Load as unpacked extension in Chrome

## Using the Mod

### Login Screen

When you visit Discord, you'll see the BlueCord login interface with:

- 🔑 **Token Login** - Enter your Discord token
- ⚙️ **Proxy Settings** - Configure proxy for anonymous browsing
- 💾 **Backup/Restore** - Save and restore account data
- 📝 **Sign Up** - Register new account

### Getting Your Discord Token

1. Open Discord in DevTools
2. Go to Network tab
3. Make any request (send message, etc.)
4. Look for Authorization header
5. Copy the token value

⚠️ **SECURITY WARNING**: Never share your token with anyone!

### After Login

Once logged in:

- Access mod via console: `DiscordMod`
- Manage themes: `DiscordMod.themes.list()`
- Configure settings: `DiscordMod.config.get/set()`

## Troubleshooting

### Mod not loading

```javascript
// Check if mod is loaded
console.log(window.DiscordMod)

// Check for errors
window.DiscordMod?.info()
```

### Login screen not appearing

- Clear browser cache
- Clear LocalStorage: `localStorage.clear()`
- Disable Discord cache buster

### Themes not applying

1. Check theme exists: `DiscordMod.themes.list()`
2. Enable theme: `DiscordMod.themes.enable('dracula')`
3. Refresh page: `F5` or `Ctrl+R`

### Proxy not working

- Verify proxy server is running
- Check protocol (HTTP/HTTPS/SOCKS5)
- Verify host and port are correct

## Advanced Usage

### Custom Themes

Place custom themes in `themes/your-theme/theme.css`

```css
:root {
  --theme-primary: #5865f2;
  --theme-background: #1e1f22;
  --theme-text-primary: #dbdee1;
}

/* Your theme styles */
```

### Configuration Persistence

Settings are saved to LocalStorage automatically:

```javascript
// Get value
DiscordMod.config.get('notifications.showOnModLoad')

// Set value
DiscordMod.config.set('uiEnhancements.smoothAnimations', true)

// Export
const config = DiscordMod.config.export()
console.log(config)
```

### Custom CSS Injection

```javascript
DiscordMod.ui.addFeature('my-css', `
  .message {
    border-left: 3px solid #5865f2;
    padding-left: 10px;
  }
`)
```

## Performance Tips

- Disable unused themes
- Minimize custom CSS
- Use `:not()` selectors carefully
- Monitor DevTools Performance tab

## Security Considerations

⚠️ **WARNING**: This mod modifies Discord's behavior. Use at your own risk.

- **Token Security**: Never paste untrusted tokens
- **Backup Files**: Keep backups encrypted
- **Updates**: Check for official mod updates regularly
- **ToS**: Modifying Discord may violate Terms of Service

## Support

- 📖 Documentation: See README.md
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions

## FAQ

**Q: Is this safe?**
A: Like any client modification, use at your own risk.

**Q: Will Discord ban me?**
A: Unknown. Use a secondary account if concerned.

**Q: Can I uninstall it?**
A: Yes, simply disable the injection method or uninstall the extension.

**Q: How do I update?**
A: Pull latest changes and rebuild: `git pull && npm run build`

---

Happy modding! 🎨
