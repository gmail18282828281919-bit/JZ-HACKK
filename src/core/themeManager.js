/**
 * Theme Manager - Loads, manages and applies Discord themes
 */

export class ThemeManager {
  constructor() {
    this.themes = new Map();
    this.activeThemes = new Set();
    this.themesPath = '/themes';
  }

  async loadThemes() {
    console.log('[ThemeManager] Loading themes...');

    try {
      const response = await fetch(`${this.themesPath}/manifest.json`);
      const manifest = await response.json();

      for (const theme of manifest.themes) {
        await this.loadTheme(theme);
      }

      // Load enabled themes from config
      const enabledThemes = this.getEnabledThemes();
      for (const themeId of enabledThemes) {
        this.enableTheme(themeId);
      }

      console.log(`[ThemeManager] ✓ Loaded ${this.themes.size} themes`);
    } catch (error) {
      console.warn('[ThemeManager] Could not load theme manifest:', error);
    }
  }

  async loadTheme(themeConfig) {
    try {
      const cssResponse = await fetch(`${this.themesPath}/${themeConfig.id}/theme.css`);
      const css = await cssResponse.text();

      this.themes.set(themeConfig.id, {
        ...themeConfig,
        css,
        enabled: false
      });

      console.log(`[ThemeManager] ✓ Theme loaded: ${themeConfig.name}`);
    } catch (error) {
      console.error(`[ThemeManager] Failed to load theme ${themeConfig.id}:`, error);
    }
  }

  enableTheme(themeId) {
    const theme = this.themes.get(themeId);
    if (!theme) {
      console.warn(`[ThemeManager] Theme not found: ${themeId}`);
      return false;
    }

    if (this.activeThemes.has(themeId)) {
      return true;
    }

    const style = document.createElement('style');
    style.id = `discord-mod-theme-${themeId}`;
    style.textContent = theme.css;
    document.head.appendChild(style);

    theme.enabled = true;
    this.activeThemes.add(themeId);

    console.log(`[ThemeManager] ✓ Theme enabled: ${theme.name}`);
    return true;
  }

  disableTheme(themeId) {
    const style = document.getElementById(`discord-mod-theme-${themeId}`);
    if (style) {
      style.remove();
    }

    const theme = this.themes.get(themeId);
    if (theme) {
      theme.enabled = false;
    }

    this.activeThemes.delete(themeId);
    console.log(`[ThemeManager] ✓ Theme disabled: ${themeId}`);
    return true;
  }

  toggleTheme(themeId) {
    const theme = this.themes.get(themeId);
    if (!theme) return false;

    if (this.activeThemes.has(themeId)) {
      this.disableTheme(themeId);
    } else {
      this.enableTheme(themeId);
    }
    return true;
  }

  getTheme(themeId) {
    return this.themes.get(themeId);
  }

  listThemes() {
    return Array.from(this.themes.values()).map(t => ({
      id: t.id,
      name: t.name,
      description: t.description,
      author: t.author,
      enabled: t.enabled
    }));
  }

  getEnabledThemes() {
    return Array.from(this.activeThemes);
  }

  getEnabledThemesInfo() {
    return Array.from(this.activeThemes).map(id => this.themes.get(id));
  }
}
