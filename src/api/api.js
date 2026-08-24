/**
 * Public API - Exposes mod functionality to the global scope
 * Available as window.DiscordMod
 */

export class API {
  constructor(mod) {
    this.mod = mod;
    this.version = mod.version;
  }

  // Theme Management
  themes = {
    list: () => this.mod.themeManager.listThemes(),
    enable: (id) => this.mod.themeManager.enableTheme(id),
    disable: (id) => this.mod.themeManager.disableTheme(id),
    toggle: (id) => this.mod.themeManager.toggleTheme(id),
    get: (id) => this.mod.themeManager.getTheme(id),
    enabled: () => this.mod.themeManager.getEnabledThemesInfo()
  };

  // Configuration
  config = {
    get: (key, def) => this.mod.configManager.get(key, def),
    set: (key, value) => this.mod.configManager.set(key, value),
    reset: () => this.mod.configManager.reset(),
    export: () => this.mod.configManager.export(),
    import: (json) => this.mod.configManager.import(json)
  };

  // UI Modifications
  ui = {
    addFeature: (name, element) => this.mod.uiModifier.addFeature(name, element),
    removeFeature: (name) => this.mod.uiModifier.removeFeature(name),
    updateTheme: () => this.mod.uiModifier.updateForTheme()
  };

  // General Info
  info = () => ({
    version: this.version,
    ready: this.mod.ready,
    themes: this.mod.themeManager.listThemes().length,
    enabledThemes: this.mod.themeManager.getEnabledThemes().length
  });

  // Utilities
  notify = (title, message, type = 'info') => {
    this.createNotification(title, message, type);
  };

  createNotification(title, message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `discord-mod-notification discord-mod-notification-${type}`;
    notification.innerHTML = `
      <div class="notification-content">
        <strong>${title}</strong>
        <p>${message}</p>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `
      .discord-mod-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px;
        border-radius: 4px;
        background: #2c2f33;
        color: #dbdee1;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 10000;
        animation: slideIn 300ms ease-out;
        min-width: 300px;
      }

      .discord-mod-notification-success {
        background: #43b581;
        color: white;
      }

      .discord-mod-notification-error {
        background: #f04747;
        color: white;
      }

      .discord-mod-notification-warning {
        background: #faa61a;
        color: #2c2f33;
      }

      .discord-mod-notification-info {
        background: #5865f2;
        color: white;
      }

      .notification-content strong {
        display: block;
        margin-bottom: 4px;
      }

      .notification-content p {
        margin: 0;
        font-size: 13px;
      }

      @keyframes slideIn {
        from {
          transform: translateX(400px);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
    `;

    if (!document.getElementById('discord-mod-notification-styles')) {
      style.id = 'discord-mod-notification-styles';
      document.head.appendChild(style);
    }

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.animation = 'slideOut 300ms ease-in forwards';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // Console helpers
  help = () => {
    const help = `
╔════════════════════════════════════════════════════════════╗
║             JZScord Mod - API Reference                    ║
╠════════════════════════════════════════════════════════════╣
║
║  THEMES:
║  • DiscordMod.themes.list()        - List all themes
║  • DiscordMod.themes.enable(id)    - Enable a theme
║  • DiscordMod.themes.disable(id)   - Disable a theme
║  • DiscordMod.themes.toggle(id)    - Toggle a theme
║  • DiscordMod.themes.enabled()     - Get enabled themes
║
║  CONFIG:
║  • DiscordMod.config.get(key)      - Get config value
║  • DiscordMod.config.set(key, val) - Set config value
║  • DiscordMod.config.reset()       - Reset to defaults
║  • DiscordMod.config.export()      - Export config JSON
║  • DiscordMod.config.import(json)  - Import config JSON
║
║  UI:
║  • DiscordMod.ui.addFeature(name, css)  - Add CSS feature
║  • DiscordMod.ui.removeFeature(name)    - Remove feature
║  • DiscordMod.ui.updateTheme()          - Refresh theme
║
║  UTILITIES:
║  • DiscordMod.info()         - Get mod info
║  • DiscordMod.notify(t, m)   - Show notification
║  • DiscordMod.help()         - Show this help
║
╚════════════════════════════════════════════════════════════╝
    `;
    console.log(help);
  };
}
