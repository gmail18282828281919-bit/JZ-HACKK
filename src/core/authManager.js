/**
 * Authentication Manager - Custom Discord login interface
 * Replaces Discord's default login with JZScord-style authentication
 */

import { JZS_LOGO } from '../assets/logoData.js';

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
              <img src="${JZS_LOGO}" alt="JZScord" class="logo-img" />
            </div>
            <h1>JZScord</h1>
            <p class="version">Version 3.0.0</p>
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
              Créer un compte
            </button>

            <div class="divider">OU</div>

            <button class="btn btn-secondary" id="register-btn">
              Connexion invité
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
        position: relative;
        width: 100%;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: radial-gradient(circle at 20% 0%, #0b3a82 0%, rgba(11,58,130,0) 45%),
                    radial-gradient(circle at 100% 100%, #123a6b 0%, rgba(18,58,107,0) 40%),
                    linear-gradient(160deg, #0a1a3f 0%, #06122b 45%, #000000 100%);
        font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
        color: #e6ecff;
        overflow: hidden;
      }

      /* Subtle animated glow blobs */
      .bluecord-login-wrapper::before,
      .bluecord-login-wrapper::after {
        content: '';
        position: absolute;
        width: 480px;
        height: 480px;
        border-radius: 50%;
        filter: blur(120px);
        opacity: 0.35;
        pointer-events: none;
      }
      .bluecord-login-wrapper::before {
        background: #1e5fff;
        top: -160px;
        left: -120px;
      }
      .bluecord-login-wrapper::after {
        background: #00224f;
        bottom: -180px;
        right: -140px;
        opacity: 0.6;
      }

      .bluecord-login-card {
        position: relative;
        z-index: 1;
        background: linear-gradient(155deg, rgba(15,30,66,0.92) 0%, rgba(7,15,33,0.94) 60%, rgba(0,0,0,0.96) 100%);
        border: 1px solid rgba(80,130,255,0.18);
        border-radius: 20px;
        padding: 40px;
        width: 100%;
        max-width: 440px;
        box-shadow: 0 24px 60px rgba(0,0,0,0.55),
                    0 0 0 1px rgba(255,255,255,0.02) inset,
                    0 1px 0 rgba(255,255,255,0.06) inset;
        backdrop-filter: blur(12px);
      }

      .login-header {
        text-align: center;
        margin-bottom: 28px;
      }

      .logo-circle {
        width: 108px;
        height: 108px;
        margin: 0 auto 18px;
        border-radius: 26px;
        background: linear-gradient(150deg, #0d2a5e 0%, #050c1c 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        border: 1px solid rgba(90,140,255,0.35);
        box-shadow: 0 10px 30px rgba(20,70,180,0.45),
                    0 0 0 6px rgba(30,95,255,0.06);
      }

      .logo-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .login-header h1 {
        font-size: 30px;
        font-weight: 800;
        letter-spacing: 0.5px;
        background: linear-gradient(90deg, #ffffff 0%, #6ea8ff 60%, #2f6bff 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
      }

      .login-header .version {
        font-size: 12px;
        color: #6f86b8;
        letter-spacing: 1px;
      }

      .login-tabs {
        display: flex;
        gap: 6px;
        margin-bottom: 22px;
        padding: 5px;
        background: rgba(5,12,30,0.6);
        border: 1px solid rgba(80,130,255,0.12);
        border-radius: 12px;
      }

      .tab-btn {
        flex: 1;
        padding: 10px;
        background: none;
        border: none;
        color: #7d92c0;
        font-size: 13px;
        font-weight: 700;
        cursor: pointer;
        border-radius: 8px;
        transition: all 200ms ease;
      }

      .tab-btn:hover {
        color: #cdd9f5;
      }

      .tab-btn.active {
        color: #ffffff;
        background: linear-gradient(180deg, #2f6bff 0%, #1c49c9 100%);
        box-shadow: 0 6px 16px rgba(31,90,240,0.45);
      }

      .tab-content {
        display: none;
        animation: fadeIn 260ms ease;
      }

      .tab-content.active {
        display: block;
      }

      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
      }

      .input-group {
        margin-bottom: 16px;
      }

      .input-group label {
        display: block;
        font-size: 11px;
        font-weight: 700;
        color: #93a6d1;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.6px;
      }

      .input-group input,
      .input-group select {
        width: 100%;
        padding: 13px 14px;
        background: rgba(6,14,32,0.85);
        border: 1px solid rgba(80,130,255,0.22);
        border-radius: 12px;
        color: #e6ecff;
        font-size: 14px;
        transition: all 180ms ease;
      }

      .input-group input::placeholder {
        color: #52618a;
      }

      .input-group input:focus,
      .input-group select:focus {
        border-color: #2f6bff;
        outline: none;
        background: rgba(9,20,45,0.95);
        box-shadow: 0 0 0 4px rgba(47,107,255,0.15);
      }

      .input-group small {
        display: block;
        font-size: 12px;
        color: #5d6f9c;
        margin-top: 5px;
      }

      .btn {
        position: relative;
        width: 100%;
        padding: 14px;
        border: none;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.3px;
        cursor: pointer;
        transition: transform 160ms ease, box-shadow 200ms ease, background 200ms ease;
        margin-bottom: 12px;
        overflow: hidden;
      }

      .btn:active {
        transform: translateY(1px) scale(0.995);
      }

      .btn-primary {
        background: linear-gradient(180deg, #3b74ff 0%, #1b46c4 100%);
        color: #ffffff;
        box-shadow: 0 10px 24px rgba(31,90,240,0.45);
      }

      .btn-primary:hover {
        background: linear-gradient(180deg, #4d81ff 0%, #244fda 100%);
        box-shadow: 0 14px 30px rgba(31,90,240,0.6);
        transform: translateY(-2px);
      }

      .btn-secondary {
        background: rgba(12,24,52,0.7);
        color: #cdd9f5;
        border: 1px solid rgba(90,140,255,0.3);
      }

      .btn-secondary:hover {
        background: rgba(20,40,86,0.9);
        border-color: #3b74ff;
        box-shadow: 0 8px 20px rgba(20,60,160,0.35);
        transform: translateY(-2px);
      }

      .btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
      }

      .divider {
        display: flex;
        align-items: center;
        text-align: center;
        color: #56679a;
        margin: 18px 0;
        font-size: 12px;
        letter-spacing: 1px;
      }
      .divider::before,
      .divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(90,140,255,0.3), transparent);
      }
      .divider::before { margin-right: 12px; }
      .divider::after  { margin-left: 12px; }

      .settings-group,
      .backup-group {
        padding: 18px;
        background: rgba(6,14,32,0.6);
        border: 1px solid rgba(80,130,255,0.14);
        border-radius: 14px;
        margin-bottom: 16px;
      }

      .settings-group h3,
      .backup-group h3 {
        margin-bottom: 16px;
        font-size: 14px;
        color: #aebce0;
      }

      .backup-actions {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 16px;
      }

      .backup-info {
        background: rgba(47,107,255,0.1);
        padding: 12px;
        border-radius: 10px;
        border-left: 3px solid #2f6bff;
      }

      .backup-info p {
        font-size: 12px;
        color: #aebce0;
        margin-bottom: 4px;
      }

      .login-footer {
        text-align: center;
        margin-top: 22px;
        font-size: 12px;
      }

      .login-footer a {
        color: #6ea8ff;
        text-decoration: none;
      }

      .login-footer a:hover {
        text-decoration: underline;
      }

      .login-footer span {
        color: #46567f;
        margin: 0 8px;
      }

      .status-message {
        margin-top: 16px;
        padding: 12px;
        border-radius: 10px;
        font-size: 13px;
        display: none;
      }

      .status-message.show {
        display: block;
      }

      .status-message.success {
        background: rgba(46,204,113,0.12);
        color: #38d67f;
        border-left: 3px solid #38d67f;
      }

      .status-message.error {
        background: rgba(255,71,87,0.12);
        color: #ff6b7a;
        border-left: 3px solid #ff6b7a;
      }

      .status-message.warning {
        background: rgba(250,166,26,0.12);
        color: #ffbe4d;
        border-left: 3px solid #ffbe4d;
      }

      .status-message.info {
        background: rgba(47,107,255,0.12);
        color: #6ea8ff;
        border-left: 3px solid #2f6bff;
      }

      @media (max-width: 480px) {
        .bluecord-login-card {
          padding: 26px 20px;
        }

        .logo-circle {
          width: 88px;
          height: 88px;
          border-radius: 22px;
        }

        .login-header h1 {
          font-size: 25px;
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
    a.download = `jzscord-backup-${Date.now()}.json`;
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
