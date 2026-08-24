/**
 * JZScord Mod - Main Injector
 * Initializes the mod and loads themes/plugins
 */

import { ThemeManager } from './core/themeManager.js';
import { UIModifier } from './core/uiModifier.js';
import { ConfigManager } from './core/configManager.js';
import { AuthManager } from './core/authManager.js';
import { API } from './api/api.js';

class DiscordMod {
  constructor() {
    this.version = '3.0.0';
    this.themeManager = null;
    this.uiModifier = null;
    this.configManager = null;
    this.authManager = null;
    this.ready = false;
  }

  async initialize() {
    console.log(`[DiscordMod] v${this.version} - Initializing...`);

    this.configManager = new ConfigManager();
    await this.configManager.loadConfig();

    this.authManager = new AuthManager();
    await this.authManager.initialize();

    this.themeManager = new ThemeManager();
    this.uiModifier = new UIModifier();

    // Expose API globally
    window.DiscordMod = new API(this);

    // Load custom CSS
    this.injectStyles();

    // Load enabled themes
    await this.themeManager.loadThemes();

    // Apply UI modifications
    this.uiModifier.applyModifications();

    this.ready = true;
    console.log('[DiscordMod] ✓ Mod loaded successfully!');
    this.logInfo();
  }

  injectStyles() {
    const style = document.createElement('style');
    style.id = 'discord-mod-styles';
    style.textContent = `
      /* JZScord Mod Base Styles */
      .discord-mod-container {
        --jzscord-primary: #2f6bff;
        --jzscord-secondary: #06122b;
        --jzscord-accent: #6ea8ff;
      }

      /* Better scrollbars */
      ::-webkit-scrollbar {
        width: 8px;
      }

      ::-webkit-scrollbar-track {
        background: transparent;
      }

      ::-webkit-scrollbar-thumb {
        background: #2f6bff;
        border-radius: 4px;
      }

      ::-webkit-scrollbar-thumb:hover {
        background: #6ea8ff;
      }

      /* Smooth animations */
      * {
        transition-property: background-color, color, border-color;
        transition-duration: 200ms;
      }
    `;
    document.head.appendChild(style);
  }

  logInfo() {
    console.log('%c[JZScord]', 'color: #2f6bff; font-weight: bold;', 'Ready!');
    console.log('%cAPI available at:', 'color: #6ea8ff;', 'window.DiscordMod');
  }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const mod = new DiscordMod();
    mod.initialize();
  });
} else {
  const mod = new DiscordMod();
  mod.initialize();
}

export default DiscordMod;
