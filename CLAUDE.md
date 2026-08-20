# Discord BlueCord Mod - Project Documentation

## Project Overview

This is a Discord client modification framework inspired by Bluecord v2.7.4, providing:
- Custom login interface with token authentication
- Theme management system
- UI enhancements and customization
- Proxy support
- Account backup/restore functionality

## Architecture

### Core Modules

```
src/
├── index.js                 - Main entry point
├── core/
│   ├── authManager.js      - Custom login UI & authentication
│   ├── themeManager.js     - Theme loading and management
│   ├── uiModifier.js       - UI enhancements and CSS injection
│   └── configManager.js    - Configuration persistence
└── api/
    └── api.js              - Public API exposed to window.DiscordMod
```

### Key Features

**AuthManager**
- Replaces Discord's login screen with custom UI
- Token-based authentication
- Proxy configuration (HTTP/HTTPS/SOCKS5)
- Account backup/restore in JSON format
- Device ID tracking

**ThemeManager**
- Loads themes from manifest.json
- Enables/disables themes dynamically
- Manages multiple simultaneous themes
- CSS-based theming system

**UIModifier**
- Custom scrollbars styling
- Typography enhancements
- Button animations
- Theme-aware styling
- Observer for theme changes

**ConfigManager**
- LocalStorage-based persistence
- Nested key access (dot notation)
- Import/export functionality
- Default configuration fallback

## Building

```bash
# Development
npm run dev     # Watch mode with rebuild

# Production
npm run build   # Minified output
```

Output: `dist/index.js`

## Installation Methods

1. **DevTools Console** - Direct script injection
2. **Tampermonkey** - Userscript manager
3. **Browser Extension** - Manifest v3 extension
4. **Direct File** - File:// protocol (local use)

See INSTALLATION.md for detailed setup.

## Usage

### Basic Commands

```javascript
// Info
DiscordMod.info()
DiscordMod.help()

// Themes
DiscordMod.themes.list()
DiscordMod.themes.enable('dracula')
DiscordMod.themes.toggle('nord')

// Configuration
DiscordMod.config.get('key')
DiscordMod.config.set('key', value)

// Notifications
DiscordMod.notify('Title', 'Message', 'success')

// UI
DiscordMod.ui.addFeature('name', 'css code')
```

## Adding Custom Themes

1. Create directory: `themes/your-theme/`
2. Add `theme.css` file
3. Update `themes/manifest.json`

Example theme structure:

```css
:root {
  --theme-primary: #5865f2;
  --theme-background: #1e1f22;
  --theme-text-primary: #dbdee1;
  /* ... more variables ... */
}

/* Your styles */
```

## File Structure

```
discord-mod/
├── src/                     # Source code
│   ├── core/               # Core modules
│   └── api/                # Public API
├── themes/                 # Theme definitions
│   ├── manifest.json       # Theme registry
│   ├── dark-blue/
│   ├── nord/
│   └── dracula/
├── dist/                   # Built output (generated)
├── webpack.config.js       # Build configuration
├── package.json           # Dependencies
├── README.md              # User documentation
├── INSTALLATION.md        # Setup guide
└── CLAUDE.md             # This file
```

## Configuration Storage

Settings stored in LocalStorage under key: `discord-mod-config`

Structure:
```json
{
  "enabledThemes": ["dracula"],
  "uiEnhancements": {
    "customScrollbars": true,
    "enhancedTypography": true,
    "improvedButtons": true,
    "smoothAnimations": true
  },
  "accessibility": {
    "reduceMotion": false,
    "highContrast": false
  },
  "notifications": {
    "showOnModLoad": true,
    "verboseLogging": false
  }
}
```

Auth data stored under: `discord-mod-auth`

## Security Considerations

- **Tokens**: Never hardcode, always prompt user
- **Storage**: Uses browser LocalStorage (client-side only)
- **CORS**: May encounter CORS on some API calls
- **TOS**: Discord modification may violate terms

## Development Workflow

1. Make changes to source files in `src/`
2. Run `npm run dev` for watching
3. Test in Discord console: `DiscordMod.info()`
4. Build for distribution: `npm run build`

## Testing

Test interactively in Discord console:

```javascript
// Check mod loaded
console.log(window.DiscordMod)

// Test theme
DiscordMod.themes.enable('dracula')
DiscordMod.themes.disabled()

// Test config
DiscordMod.config.set('test', true)

// Inspect UI
document.getElementById('bluecord-login-container')
```

## Future Enhancements

- [ ] Plugin system
- [ ] More pre-built themes
- [ ] Theme editor UI
- [ ] Cloud sync for settings
- [ ] Custom command system
- [ ] Message filters/transformers
- [ ] Rich notification center
- [ ] Settings panel UI

## Dependencies

- webpack 5 - Bundler
- No runtime dependencies (vanilla JS)

## License

MIT License

## Notes

- Module system uses ES6 imports (requires bundler)
- No jQuery or external libraries required
- Compatible with modern browsers (Chrome, Firefox, Edge)
- LocalStorage access required for full functionality
- Network requests for API calls may be blocked by CORS

## Debugging

Enable verbose logging:

```javascript
DiscordMod.config.set('notifications.verboseLogging', true)
```

Check browser console for all `[DiscordMod]` prefixed messages.

## Version History

- **2.7.4** - Initial release
  - Custom login UI
  - Theme system
  - UI enhancements
  - Config management
  - Proxy support
