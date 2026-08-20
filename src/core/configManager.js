/**
 * Configuration Manager - Handles mod settings and persistence
 */

export class ConfigManager {
  constructor() {
    this.config = {
      enabledThemes: [],
      uiEnhancements: {
        customScrollbars: true,
        enhancedTypography: true,
        improvedButtons: true,
        smoothAnimations: true
      },
      accessibility: {
        reduceMotion: false,
        highContrast: false
      },
      notifications: {
        showOnModLoad: true,
        verboseLogging: false
      }
    };
    this.storageKey = 'discord-mod-config';
  }

  async loadConfig() {
    try {
      const stored = localStorage.getItem(this.storageKey);
      if (stored) {
        const loaded = JSON.parse(stored);
        this.config = { ...this.config, ...loaded };
        console.log('[ConfigManager] ✓ Config loaded from storage');
      }
    } catch (error) {
      console.error('[ConfigManager] Failed to load config:', error);
      console.log('[ConfigManager] Using default config');
    }
  }

  saveConfig() {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.config));
      console.log('[ConfigManager] ✓ Config saved');
      return true;
    } catch (error) {
      console.error('[ConfigManager] Failed to save config:', error);
      return false;
    }
  }

  get(key, defaultValue = null) {
    const keys = key.split('.');
    let value = this.config;

    for (const k of keys) {
      value = value?.[k];
      if (value === undefined) return defaultValue;
    }

    return value;
  }

  set(key, value) {
    const keys = key.split('.');
    const lastKey = keys.pop();

    let obj = this.config;
    for (const k of keys) {
      obj[k] = obj[k] || {};
      obj = obj[k];
    }

    obj[lastKey] = value;
    this.saveConfig();
    return true;
  }

  addTheme(themeId) {
    if (!this.config.enabledThemes.includes(themeId)) {
      this.config.enabledThemes.push(themeId);
      this.saveConfig();
      return true;
    }
    return false;
  }

  removeTheme(themeId) {
    const index = this.config.enabledThemes.indexOf(themeId);
    if (index !== -1) {
      this.config.enabledThemes.splice(index, 1);
      this.saveConfig();
      return true;
    }
    return false;
  }

  reset() {
    this.config = {
      enabledThemes: [],
      uiEnhancements: {
        customScrollbars: true,
        enhancedTypography: true,
        improvedButtons: true,
        smoothAnimations: true
      },
      accessibility: {
        reduceMotion: false,
        highContrast: false
      },
      notifications: {
        showOnModLoad: true,
        verboseLogging: false
      }
    };
    this.saveConfig();
    console.log('[ConfigManager] ✓ Config reset to defaults');
  }

  export() {
    return JSON.stringify(this.config, null, 2);
  }

  import(jsonString) {
    try {
      const imported = JSON.parse(jsonString);
      this.config = { ...this.config, ...imported };
      this.saveConfig();
      return true;
    } catch (error) {
      console.error('[ConfigManager] Failed to import config:', error);
      return false;
    }
  }
}
