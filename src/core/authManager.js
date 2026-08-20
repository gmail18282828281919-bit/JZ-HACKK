/**
 * Authentication Manager - Custom Discord login interface
 * Replaces Discord's default login with Bluecord-style authentication
 */

export class AuthManager {
  constructor() {
    this.isAuthenticated = false;
    this.currentToken = null;
    this.storageKey = 'discord-mod-auth';
    this.proxySettings = {
      enabled: false,
      host: '',
      port: '',
      protocol: 'http'
    };
  }

  async initialize() {
    console.log('[AuthManager] Initializing...');

    // Check if already logged in
    const saved = localStorage.getItem(this.storageKey);
    if (saved) {
      const data = JSON.parse(saved);
      this.currentToken = data.token;
      this.proxySettings = data.proxy || this.proxySettings;
      this.isAuthenticated = true;
      console.log('[AuthManager] ✓ Loaded saved credentials');
    }

    // Check if Discord page is login screen
    if (this.isDiscordLoginPage()) {
      console.log('[AuthManager] Discord login page detected');
      this.replaceLoginUI();
    }
  }

  isDiscordLoginPage() {
    const url = window.location.href;
    return url.includes('discord.com') && !localStorage.getItem('token');
  }

  replaceLoginUI() {
    // Wait for Discord to load, then replace the UI
    setTimeout(() => {
      const app = document.querySelector('[data-app-mount]');
      if (app) {
        app.innerHTML = '';
        this.createLoginInterface();
      }
    }, 1000);
  }

  createLoginInterface() {
    const container = document.createElement('div');
    container.id = 'bluecord-login-container';
    container.innerHTML = this.getLoginHTML();
    document.body.appendChild(container);

    // Inject styles
    this.injectLoginStyles();

    // Attach event listeners
    this.attachEventListeners();
  }

  getLoginHTML() {
    return `
      <div class="bluecord-login-wrapper">
        <div class="bluecord-login-card">
          <!-- Header -->
          <div class="login-header">
            <div class="logo-circle">
              <svg viewBox="0 0 127 127" fill="none">
                <path d="M107.7 8.07A105.3 105.3 0 00107 8 102 102 0 0 0 7.6 107a102 102 0 0 0 148.3 0 102 102 0 0 0-48.2-98.93z" fill="#5865f2"/>
                <path d="M51 97.4c-4.7 0-8.5-4-8.5-8.8s3.9-8.8 8.5-8.8c4.8 0 8.6 3.9 8.6 8.8.1 4.8-3.8 8.8-8.6 8.8zm31.3 0c-4.7 0-8.5-4-8.5-8.8s3.9-8.8 8.5-8.8c4.8 0 8.6 3.9 8.6 8.8 0 4.8-3.8 8.8-8.6 8.8zm-23-49.5c0-1.5 1.2-2.8 2.8-2.8h12.2c1.5 0 2.8 1.2 2.8 2.8v18.8c0 1.6-1.2 2.8-2.8 2.8H61c-1.5 0-2.8-1.2-2.8-2.8v-18.8z" fill="#fff"/>
              </svg>
            </div>
            <h1>Welcome To BlueCord</h1>
            <p class="version">Version 2.7.4</p>
          </div>

          <!-- Tabs -->
          <div class="login-tabs">
            <button class="tab-btn active" data-tab="login">Login</button>
            <button class="tab-btn" data-tab="settings">Settings</button>
            <button class="tab-btn" data-tab="backup">Backup</button>
          </div>

          <!-- Login Tab -->
          <div class="tab-content active" id="login-tab">
            <div class="input-group">
              <label>Token</label>
              <input type="password" id="token-input" placeholder="Enter your Discord token">
              <small>Your authentication token</small>
            </div>

            <div class="input-group">
              <label>Device ID (Optional)</label>
              <input type="text" id="device-id-input" placeholder="Auto-generated">
              <small>Leave empty for auto-generation</small>
            </div>

            <button class="btn btn-primary" id="login-btn">
              <span>Se connecter</span>
            </button>

            <button class="btn btn-secondary" id="signup-btn">
              S'inscrire
            </button>

            <div class="divider">ou</div>

            <button class="btn btn-secondary" id="register-btn">
              Create New Account
            </button>
          </div>

          <!-- Settings Tab -->
          <div class="tab-content" id="settings-tab">
            <div class="settings-group">
              <h3>Proxy Settings</h3>

              <div class="input-group">
                <label>
                  <input type="checkbox" id="proxy-enabled" />
                  Enable Proxy
                </label>
              </div>

              <div class="input-group">
                <label>Protocol</label>
                <select id="proxy-protocol">
                  <option value="http">HTTP</option>
                  <option value="https">HTTPS</option>
                  <option value="socks5">SOCKS5</option>
                </select>
              </div>

              <div class="input-group">
                <label>Host</label>
                <input type="text" id="proxy-host" placeholder="127.0.0.1">
              </div>

              <div class="input-group">
                <label>Port</label>
                <input type="number" id="proxy-port" placeholder="8080">
              </div>

              <button class="btn btn-primary" id="save-proxy-btn">Save Proxy Settings</button>
            </div>
          </div>

          <!-- Backup Tab -->
          <div class="tab-content" id="backup-tab">
            <div class="backup-group">
              <h3>Account Backup & Restore</h3>

              <div class="backup-actions">
                <button class="btn btn-secondary" id="backup-export-btn">
                  📥 Export Account Data
                </button>

                <button class="btn btn-secondary" id="backup-import-btn">
                  📤 Import Account Data
                </button>
                <input type="file" id="backup-file-input" accept=".json" style="display:none">
              </div>

              <div class="backup-info">
                <p>💾 Backup your account credentials securely</p>
                <p>⚠️ Never share your backup file with anyone</p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="login-footer">
            <a href="#" id="forgot-password">Forgot Password?</a>
            <span>•</span>
            <a href="#" id="help-link">Help</a>
          </div>

          <!-- Status -->
          <div id="status-message" class="status-message"></div>
        </div>
      </div>
    `;
  }

  injectLoginStyles() {
    const style = document.createElement('style');
    style.id = 'bluecord-login-styles';
    style.textContent = `
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      .bluecord-login-wrapper {
        width: 100%;
        height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #1a1b22 0%, #2c2f33 100%);
        font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
        color: #dbdee1;
      }

      .bluecord-login-card {
        background: #36393f;
        border-radius: 8px;
        padding: 40px;
        width: 100%;
        max-width: 420px;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
      }

      .login-header {
        text-align: center;
        margin-bottom: 30px;
      }

      .logo-circle {
        width: 100px;
        height: 100px;
        margin: 0 auto 20px;
        border-radius: 50%;
        background: #5865f2;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(88, 101, 242, 0.4);
      }

      .logo-circle svg {
        width: 60px;
        height: 60px;
      }

      .login-header h1 {
        font-size: 24px;
        font-weight: 700;
        color: #00d166;
        margin-bottom: 4px;
      }

      .login-header .version {
        font-size: 12px;
        color: #72767d;
      }

      .login-tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 20px;
        border-bottom: 2px solid #2c2f33;
      }

      .tab-btn {
        flex: 1;
        padding: 12px;
        background: none;
        border: none;
        color: #72767d;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        border-bottom: 3px solid transparent;
        transition: all 200ms;
      }

      .tab-btn:hover {
        color: #b9bbbe;
      }

      .tab-btn.active {
        color: #5865f2;
        border-bottom-color: #5865f2;
      }

      .tab-content {
        display: none;
      }

      .tab-content.active {
        display: block;
      }

      .input-group {
        margin-bottom: 16px;
      }

      .input-group label {
        display: block;
        font-size: 12px;
        font-weight: 700;
        color: #b9bbbe;
        margin-bottom: 8px;
        text-transform: uppercase;
      }

      .input-group input,
      .input-group select {
        width: 100%;
        padding: 10px 12px;
        background: #2f3136;
        border: 1px solid #202225;
        border-radius: 4px;
        color: #dbdee1;
        font-size: 14px;
        transition: all 200ms;
      }

      .input-group input::placeholder {
        color: #72767d;
      }

      .input-group input:focus,
      .input-group select:focus {
        border-color: #5865f2;
        outline: none;
        box-shadow: 0 0 0 3px rgba(88, 101, 242, 0.1);
      }

      .input-group small {
        display: block;
        font-size: 12px;
        color: #72767d;
        margin-top: 4px;
      }

      .btn {
        width: 100%;
        padding: 12px;
        border: none;
        border-radius: 4px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 200ms;
        margin-bottom: 10px;
      }

      .btn-primary {
        background: #5865f2;
        color: white;
      }

      .btn-primary:hover {
        background: #7289da;
        box-shadow: 0 4px 12px rgba(88, 101, 242, 0.4);
        transform: translateY(-2px);
      }

      .btn-primary:active {
        transform: translateY(0);
      }

      .btn-secondary {
        background: #2f3136;
        color: #dbdee1;
        border: 1px solid #202225;
      }

      .btn-secondary:hover {
        background: #40444b;
        border-color: #5865f2;
      }

      .btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .divider {
        text-align: center;
        color: #72767d;
        margin: 16px 0;
        font-size: 12px;
      }

      .settings-group,
      .backup-group {
        padding: 16px;
        background: #2f3136;
        border-radius: 4px;
        margin-bottom: 16px;
      }

      .settings-group h3,
      .backup-group h3 {
        margin-bottom: 16px;
        font-size: 14px;
        color: #b9bbbe;
      }

      .backup-actions {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 16px;
      }

      .backup-info {
        background: rgba(88, 101, 242, 0.1);
        padding: 12px;
        border-radius: 4px;
        border-left: 3px solid #5865f2;
      }

      .backup-info p {
        font-size: 12px;
        color: #b9bbbe;
        margin-bottom: 4px;
      }

      .login-footer {
        text-align: center;
        margin-top: 20px;
        font-size: 12px;
      }

      .login-footer a {
        color: #5865f2;
        text-decoration: none;
      }

      .login-footer a:hover {
        text-decoration: underline;
      }

      .login-footer span {
        color: #72767d;
        margin: 0 8px;
      }

      .status-message {
        margin-top: 16px;
        padding: 12px;
        border-radius: 4px;
        font-size: 13px;
        display: none;
      }

      .status-message.show {
        display: block;
      }

      .status-message.success {
        background: rgba(67, 181, 129, 0.1);
        color: #43b581;
        border-left: 3px solid #43b581;
      }

      .status-message.error {
        background: rgba(240, 71, 71, 0.1);
        color: #f04747;
        border-left: 3px solid #f04747;
      }

      .status-message.warning {
        background: rgba(250, 166, 26, 0.1);
        color: #faa61a;
        border-left: 3px solid #faa61a;
      }

      .status-message.info {
        background: rgba(88, 101, 242, 0.1);
        color: #5865f2;
        border-left: 3px solid #5865f2;
      }

      @media (max-width: 480px) {
        .bluecord-login-card {
          padding: 20px;
        }

        .logo-circle {
          width: 80px;
          height: 80px;
        }

        .login-header h1 {
          font-size: 20px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  attachEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tabName = e.target.getAttribute('data-tab');
        this.switchTab(tabName);
      });
    });

    // Login
    document.getElementById('login-btn')?.addEventListener('click', () => {
      this.loginWithToken();
    });

    // Signup
    document.getElementById('signup-btn')?.addEventListener('click', () => {
      this.showMessage('Redirecting to Discord signup...', 'info');
      setTimeout(() => {
        window.location.href = 'https://discord.com/register';
      }, 1500);
    });

    // Proxy settings
    document.getElementById('save-proxy-btn')?.addEventListener('click', () => {
      this.saveProxySettings();
    });

    // Backup/Restore
    document.getElementById('backup-export-btn')?.addEventListener('click', () => {
      this.exportBackup();
    });

    document.getElementById('backup-import-btn')?.addEventListener('click', () => {
      document.getElementById('backup-file-input').click();
    });

    document.getElementById('backup-file-input')?.addEventListener('change', (e) => {
      this.importBackup(e);
    });

    // Footer links
    document.getElementById('forgot-password')?.addEventListener('click', (e) => {
      e.preventDefault();
      this.showMessage('Password reset: Go to discord.com/login', 'info');
    });

    // Token input enter key
    document.getElementById('token-input')?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.loginWithToken();
      }
    });
  }

  switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
      tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`)?.classList.add('active');
    document.querySelector(`[data-tab="${tabName}"]`)?.classList.add('active');
  }

  async loginWithToken() {
    const token = document.getElementById('token-input').value.trim();
    const deviceId = document.getElementById('device-id-input').value || this.generateDeviceId();

    if (!token) {
      this.showMessage('Please enter a token', 'error');
      return;
    }

    this.showMessage('Logging in...', 'info');

    try {
      // Validate token with Discord API
      const response = await fetch('https://discord.com/api/v9/users/@me', {
        headers: {
          'Authorization': token
        }
      });

      if (!response.ok) {
        throw new Error('Invalid token');
      }

      const user = await response.json();

      // Save credentials
      const authData = {
        token,
        deviceId,
        userId: user.id,
        username: user.username,
        discriminator: user.discriminator,
        loginTime: new Date().toISOString()
      };

      localStorage.setItem(this.storageKey, JSON.stringify(authData));
      localStorage.setItem('token', token);

      this.currentToken = token;
      this.isAuthenticated = true;

      this.showMessage(`Welcome back, ${user.username}!`, 'success');

      // Redirect to Discord
      setTimeout(() => {
        window.location.href = 'https://discord.com/channels/@me';
      }, 1500);
    } catch (error) {
      console.error('[AuthManager] Login error:', error);
      this.showMessage('Login failed: ' + error.message, 'error');
    }
  }

  saveProxySettings() {
    this.proxySettings = {
      enabled: document.getElementById('proxy-enabled').checked,
      protocol: document.getElementById('proxy-protocol').value,
      host: document.getElementById('proxy-host').value,
      port: document.getElementById('proxy-port').value
    };

    const authData = JSON.parse(localStorage.getItem(this.storageKey) || '{}');
    authData.proxy = this.proxySettings;
    localStorage.setItem(this.storageKey, JSON.stringify(authData));

    this.showMessage('Proxy settings saved!', 'success');
  }

  exportBackup() {
    const data = localStorage.getItem(this.storageKey);
    if (!data) {
      this.showMessage('No account data to export', 'error');
      return;
    }

    const backup = {
      version: '1.0',
      exported: new Date().toISOString(),
      data: JSON.parse(data)
    };

    const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bluecord-backup-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    this.showMessage('Backup exported!', 'success');
  }

  importBackup(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const backup = JSON.parse(e.target.result);
        if (!backup.data || !backup.data.token) {
          throw new Error('Invalid backup file');
        }

        localStorage.setItem(this.storageKey, JSON.stringify(backup.data));
        localStorage.setItem('token', backup.data.token);

        this.currentToken = backup.data.token;
        this.isAuthenticated = true;

        this.showMessage('Backup restored! Redirecting...', 'success');
        setTimeout(() => {
          window.location.href = 'https://discord.com/channels/@me';
        }, 1500);
      } catch (error) {
        this.showMessage('Failed to import backup: ' + error.message, 'error');
      }
    };
    reader.readAsText(file);
  }

  showMessage(text, type = 'info') {
    const msg = document.getElementById('status-message');
    if (msg) {
      msg.textContent = text;
      msg.className = `status-message show ${type}`;
    }
  }

  generateDeviceId() {
    return 'device_' + Math.random().toString(36).substr(2, 9);
  }
}
