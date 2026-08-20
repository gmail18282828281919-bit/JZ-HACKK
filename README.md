# Discord BlueCord Mod

A powerful Discord client modification framework similar to **Bluecord**, enabling custom themes, UI enhancements, and functionality extensions.

## Features

✨ **Theme System**
- Load and manage multiple custom Discord themes
- Pre-built themes included (Dark Blue, Nord, Dracula, etc.)
- Easy theme switching without restarting Discord
- CSS-based theming for complete customization

🎨 **UI Enhancements**
- Custom scrollbars
- Enhanced typography
- Improved button styles
- Smooth animations and transitions
- Theme-aware components

⚙️ **Configuration**
- Persistent configuration storage
- Import/export settings
- Easy customization through API
- Per-feature toggles

🔌 **Developer API**
- Global `window.DiscordMod` API
- Theme management functions
- Configuration system
- UI modification tools
- Notification system

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/discord-bluecord-mod.git
cd discord-bluecord-mod
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Build the Mod

```bash
npm run build
```

Or for development with watch mode:

```bash
npm run dev
```

### 4. Inject into Discord

**Option A: Using a Browser Extension**

Create a browser extension that injects the built script:

1. Load `dist/index.js` as a content script in your Discord tab
2. Add permissions for Discord domains
3. Load as unpacked extension in Chrome DevTools

**Option B: Developer Console Injection**

In Discord's DevTools console:

```javascript
const script = document.createElement('script');
script.src = 'file:///path/to/discord-mod/dist/index.js';
document.head.appendChild(script);
```

**Option C: Using a Userscript Manager**

Create a Tampermonkey/Greasemonkey script that loads the mod:

```javascript
// ==UserScript==
// @name Discord BlueCord Mod
// @namespace discord-bluecord-mod
// @match https://discord.com/*
// @run-at document-start
// ==/UserScript==

const script = document.createElement('script');
script.src = 'https://your-server.com/dist/index.js';
script.type = 'module';
document.head.appendChild(script);
```

## Usage

### Using Themes

Once the mod is loaded, access it via the console:

```javascript
// List available themes
DiscordMod.themes.list()

// Enable a theme
DiscordMod.themes.enable('dracula')

// Disable a theme
DiscordMod.themes.disable('nord')

// Toggle a theme
DiscordMod.themes.toggle('dark-blue')

// Get info about enabled themes
DiscordMod.themes.enabled()
```

### Configuration

```javascript
// Get a config value
DiscordMod.config.get('notifications.showOnModLoad')

// Set a config value
DiscordMod.config.set('uiEnhancements.customScrollbars', true)

// Reset to defaults
DiscordMod.config.reset()

// Export configuration
const config = DiscordMod.config.export()

// Import configuration
DiscordMod.config.import(configJson)
```

### UI Modifications

```javascript
// Add custom CSS
DiscordMod.ui.addFeature('my-feature', `
  .my-class {
    color: red;
  }
`)

// Remove a feature
DiscordMod.ui.removeFeature('my-feature')

// Update theme colors
DiscordMod.ui.updateTheme()
```

### Notifications

```javascript
// Show a notification
DiscordMod.notify('Title', 'Message content', 'info')

// Types: 'info', 'success', 'warning', 'error'
DiscordMod.notify('Success!', 'Theme applied', 'success')
DiscordMod.notify('Warning', 'Something happened', 'warning')
DiscordMod.notify('Error', 'Something went wrong', 'error')
```

### Get Mod Info

```javascript
DiscordMod.info()
// Returns: { version, ready, themes, enabledThemes }
```

### Help

```javascript
DiscordMod.help()
```

## Creating Custom Themes

### Theme Structure

Create a new directory under `themes/`:

```
themes/my-theme/
├── theme.css          # Main theme stylesheet
└── metadata.json      # Optional: theme metadata
```

### Theme CSS Template

```css
:root {
  --theme-primary: #5865f2;
  --theme-secondary: #2c2f33;
  --theme-background: #1e1f22;
  --theme-surface: #2c2f33;
  --theme-text-primary: #dbdee1;
  --theme-text-secondary: #949ba4;
  --theme-border: #404249;
  --theme-accent: #5865f2;
  --theme-success: #43b581;
  --theme-warning: #faa61a;
  --theme-danger: #f04747;
}

/* Add your theme styles here */
body {
  background-color: var(--theme-background);
  color: var(--theme-text-primary);
}

/* ... more CSS ... */
```

### Adding Theme to Manifest

Edit `themes/manifest.json`:

```json
{
  "id": "my-theme",
  "name": "My Theme",
  "description": "A custom theme for Discord",
  "author": "Your Name",
  "version": "1.0.0",
  "tags": ["dark", "custom"]
}
```

## API Reference

### Themes API

- `DiscordMod.themes.list()` - Get all themes
- `DiscordMod.themes.get(id)` - Get theme details
- `DiscordMod.themes.enable(id)` - Enable a theme
- `DiscordMod.themes.disable(id)` - Disable a theme
- `DiscordMod.themes.toggle(id)` - Toggle theme state
- `DiscordMod.themes.enabled()` - Get enabled themes

### Config API

- `DiscordMod.config.get(key, default)` - Get config value
- `DiscordMod.config.set(key, value)` - Set config value
- `DiscordMod.config.reset()` - Reset to defaults
- `DiscordMod.config.export()` - Export as JSON
- `DiscordMod.config.import(json)` - Import from JSON

### UI API

- `DiscordMod.ui.addFeature(name, css)` - Add CSS feature
- `DiscordMod.ui.removeFeature(name)` - Remove feature
- `DiscordMod.ui.updateTheme()` - Refresh theme

### Utility API

- `DiscordMod.info()` - Get mod information
- `DiscordMod.notify(title, message, type)` - Show notification
- `DiscordMod.help()` - Display help

## Included Themes

### 1. Dark Blue
Modern dark theme with blue accents. Perfect for daily use.

### 2. Nord
Arctic, north-bluish color palette inspired by the Nord theme.

### 3. Dracula
Dark theme with vibrant colors inspired by the Dracula theme.

### 4. Solarized Dark
Precision colors optimized for visibility and contrast.

### 5. Material Darker
Material Design inspired dark theme for Discord.

## Project Structure

```
discord-mod/
├── src/
│   ├── index.js                 # Main entry point
│   ├── core/
│   │   ├── themeManager.js      # Theme system
│   │   ├── uiModifier.js        # UI modifications
│   │   └── configManager.js     # Configuration
│   └── api/
│       └── api.js               # Public API
├── themes/
│   ├── manifest.json            # Theme registry
│   ├── dark-blue/
│   │   └── theme.css
│   ├── nord/
│   │   └── theme.css
│   └── dracula/
│       └── theme.css
├── webpack.config.js            # Build configuration
├── package.json                 # Dependencies
└── README.md                    # This file
```

## Development

### Build Modes

```bash
# Production build (minified)
npm run build

# Development build (watch mode)
npm run dev

# Clean build
npm run clean
```

### Adding Features

1. Create a new module in `src/`
2. Export a class following the pattern
3. Initialize in `src/index.js`
4. Expose via API in `src/api/api.js`

### Testing

Test themes and features in Discord's console:

```javascript
// Test a theme
DiscordMod.themes.enable('dracula')

// Test config
DiscordMod.config.set('test.value', true)
console.log(DiscordMod.config.get('test.value'))

// View logs
// Check browser console with timestamps
```

## Troubleshooting

### Mod not loading
- Check browser console for errors
- Verify file paths are correct
- Ensure Discord is fully loaded before injection
- Check permissions for file access

### Themes not applying
- Verify theme files exist in `themes/` directory
- Check `manifest.json` is valid JSON
- Look for CSS selector conflicts
- Inspect elements to debug styles

### Performance issues
- Disable unused themes
- Check for conflicting CSS rules
- Profile with DevTools Performance tab
- Report to GitHub issues

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

## Legal Notice

⚠️ **This mod modifies Discord's client.** Use at your own risk. Modifying Discord may violate the Terms of Service. This is for educational purposes only.

## License

MIT License - See LICENSE file for details

## Support

- 📧 Email: support@example.com
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions

---

**Made with ❤️ for the Discord community**
