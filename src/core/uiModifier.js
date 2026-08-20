/**
 * UI Modifier - Applies visual and functional modifications to Discord
 */

export class UIModifier {
  constructor() {
    this.modifications = new Map();
    this.observers = new Map();
  }

  applyModifications() {
    this.modifyScrollbars();
    this.enhanceTypography();
    this.improveButtonStyles();
    this.observeThemeChanges();
  }

  modifyScrollbars() {
    const style = document.createElement('style');
    style.id = 'mod-scrollbars';
    style.textContent = `
      /* Custom scrollbars */
      ::-webkit-scrollbar {
        width: 10px;
      }

      ::-webkit-scrollbar-track {
        background: transparent;
      }

      ::-webkit-scrollbar-thumb {
        background: #4f545c;
        border-radius: 5px;
        border: 2px solid transparent;
        background-clip: padding-box;
      }

      ::-webkit-scrollbar-thumb:hover {
        background-color: #72767d;
        background-clip: padding-box;
      }

      /* Firefox */
      * {
        scrollbar-color: #4f545c transparent;
        scrollbar-width: thin;
      }
    `;
    document.head.appendChild(style);
    this.modifications.set('scrollbars', style);
  }

  enhanceTypography() {
    const style = document.createElement('style');
    style.id = 'mod-typography';
    style.textContent = `
      /* Improved typography */
      * {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }

      body, html {
        font-family: 'Segoe UI', 'Helvetica Neue', 'Trebuchet MS', sans-serif;
      }

      /* Better text rendering */
      p, span, div {
        letter-spacing: 0.3px;
      }

      /* Code blocks */
      code, pre {
        font-family: 'Fira Code', 'Courier New', monospace;
      }
    `;
    document.head.appendChild(style);
    this.modifications.set('typography', style);
  }

  improveButtonStyles() {
    const style = document.createElement('style');
    style.id = 'mod-buttons';
    style.textContent = `
      /* Enhanced buttons */
      button {
        transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: 500;
        cursor: pointer;
      }

      button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      }

      button:active {
        transform: translateY(0);
      }

      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
      }
    `;
    document.head.appendChild(style);
    this.modifications.set('buttons', style);
  }

  observeThemeChanges() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
          console.log('[UIModifier] Theme changed:', mutation.target.getAttribute('data-theme'));
          this.updateForTheme();
        }
      }
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    this.observers.set('themeObserver', observer);
  }

  updateForTheme() {
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    console.log('[UIModifier] Applying theme-specific styles for:', theme);

    const style = document.getElementById('mod-theme-specific');
    if (style) style.remove();

    const newStyle = document.createElement('style');
    newStyle.id = 'mod-theme-specific';

    if (theme === 'light') {
      newStyle.textContent = `
        :root[data-theme="light"] {
          --mod-text-primary: #2c2e31;
          --mod-text-secondary: #72767d;
          --mod-bg-primary: #ffffff;
          --mod-bg-secondary: #f2f3f5;
        }
      `;
    } else {
      newStyle.textContent = `
        :root[data-theme="dark"],
        :root {
          --mod-text-primary: #dbdee1;
          --mod-text-secondary: #949ba4;
          --mod-bg-primary: #313338;
          --mod-bg-secondary: #2c2f33;
        }
      `;
    }

    document.head.appendChild(newStyle);
  }

  addFeature(name, element) {
    if (this.modifications.has(name)) {
      console.warn(`[UIModifier] Feature already exists: ${name}`);
      return false;
    }

    if (element instanceof HTMLElement) {
      document.head.appendChild(element);
    } else if (typeof element === 'string') {
      const style = document.createElement('style');
      style.textContent = element;
      document.head.appendChild(style);
    }

    this.modifications.set(name, element);
    return true;
  }

  removeFeature(name) {
    const feature = this.modifications.get(name);
    if (feature && feature instanceof HTMLElement) {
      feature.remove();
    }
    this.modifications.delete(name);
    return true;
  }

  destroy() {
    this.modifications.forEach((element) => {
      if (element instanceof HTMLElement) {
        element.remove();
      }
    });
    this.modifications.clear();

    this.observers.forEach((observer) => {
      observer.disconnect();
    });
    this.observers.clear();
  }
}
