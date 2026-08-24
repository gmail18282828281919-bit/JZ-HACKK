import React, { useState, useEffect } from 'react';
import { View, ScrollView, Text, TextInput, TouchableOpacity, Alert, AsyncStorage, StyleSheet, SafeAreaView } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';

const STORAGE_KEY = '@bluecord_auth';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0015',
  },
  scrollView: {
    flex: 1,
  },
  wrapper: {
    padding: 20,
    alignItems: 'center',
  },
  logoContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#ff0080',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 30,
    marginBottom: 25,
    shadowColor: '#ff0080',
    shadowOpacity: 0.8,
    shadowRadius: 25,
    elevation: 15,
  },
  logoText: {
    fontSize: 50,
    fontWeight: 'bold',
    color: '#fff',
  },
  title: {
    fontSize: 32,
    fontWeight: '900',
    color: '#ff0080',
    marginBottom: 8,
    letterSpacing: 2,
  },
  version: {
    fontSize: 12,
    color: '#72767d',
    marginBottom: 30,
    fontStyle: 'italic',
  },
  tabsContainer: {
    flexDirection: 'row',
    marginBottom: 24,
    borderBottomWidth: 2,
    borderBottomColor: '#3a0050',
    width: '100%',
  },
  tab: {
    flex: 1,
    paddingVertical: 14,
    alignItems: 'center',
    borderBottomWidth: 3,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: '#ff0080',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#888',
  },
  tabTextActive: {
    color: '#ff0080',
    fontSize: 14,
  },
  inputGroup: {
    marginBottom: 16,
    width: '100%',
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: '#b9bbbe',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  input: {
    backgroundColor: '#1a0025',
    borderWidth: 2,
    borderColor: '#4a0080',
    borderRadius: 8,
    padding: 14,
    color: '#fff',
    fontSize: 14,
    marginBottom: 4,
  },
  inputFocus: {
    borderColor: '#ff0080',
  },
  hint: {
    fontSize: 12,
    color: '#72767d',
    marginTop: 4,
  },
  button: {
    width: '100%',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonPrimary: {
    backgroundColor: '#ff0080',
    shadowColor: '#ff0080',
    shadowOpacity: 0.6,
    shadowRadius: 15,
    elevation: 8,
  },
  buttonSecondary: {
    backgroundColor: '#1a0025',
    borderWidth: 2,
    borderColor: '#ff0080',
    shadowColor: '#ff0080',
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 5,
  },
  buttonText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
  buttonTextSecondary: {
    color: '#ff0080',
  },
  divider: {
    fontSize: 12,
    color: '#72767d',
    marginVertical: 16,
  },
  settingsGroup: {
    backgroundColor: '#1a0025',
    borderRadius: 12,
    padding: 18,
    marginBottom: 18,
    width: '100%',
    borderWidth: 1,
    borderColor: '#4a0080',
  },
  settingsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#b9bbbe',
    marginBottom: 16,
  },
  checkboxContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#ff0080',
    marginRight: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxChecked: {
    backgroundColor: '#ff0080',
  },
  checkboxText: {
    color: '#dbdee1',
    fontSize: 14,
  },
  select: {
    backgroundColor: '#1a0025',
    borderWidth: 2,
    borderColor: '#4a0080',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    marginBottom: 12,
  },
  backupInfo: {
    backgroundColor: 'rgba(255, 0, 128, 0.1)',
    borderLeftWidth: 4,
    borderLeftColor: '#ff0080',
    padding: 14,
    borderRadius: 8,
    marginTop: 14,
  },
  backupInfoText: {
    color: '#b9bbbe',
    fontSize: 12,
    marginBottom: 6,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 20,
    borderTopWidth: 1,
    borderTopColor: '#3a0050',
  },
  footerLink: {
    color: '#ff0080',
    fontSize: 12,
    marginHorizontal: 8,
  },
  footerDot: {
    color: '#72767d',
  },
  statusMessage: {
    padding: 14,
    borderRadius: 8,
    marginTop: 16,
    borderLeftWidth: 4,
  },
  statusSuccess: {
    backgroundColor: 'rgba(0, 209, 102, 0.1)',
    borderLeftColor: '#00d166',
  },
  statusError: {
    backgroundColor: 'rgba(255, 107, 107, 0.1)',
    borderLeftColor: '#ff6b6b',
  },
  statusInfo: {
    backgroundColor: 'rgba(255, 0, 128, 0.1)',
    borderLeftColor: '#ff0080',
  },
  statusText: {
    fontSize: 13,
    fontWeight: '500',
  },
  statusTextSuccess: {
    color: '#00d166',
  },
  statusTextError: {
    color: '#ff6b6b',
  },
  statusTextInfo: {
    color: '#ff0080',
  },
});

export default function App() {
  const [activeTab, setActiveTab] = useState('login');
  const [token, setToken] = useState('');
  const [deviceId, setDeviceId] = useState('');
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [proxyProtocol, setProxyProtocol] = useState('http');
  const [proxyHost, setProxyHost] = useState('');
  const [proxyPort, setProxyPort] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSavedCredentials();
  }, []);

  const loadSavedCredentials = async () => {
    try {
      const saved = await AsyncStorage.getItem(STORAGE_KEY);
      if (saved) {
        const data = JSON.parse(saved);
        setToken(data.token || '');
        setDeviceId(data.deviceId || '');
        if (data.proxy) {
          setProxyEnabled(data.proxy.enabled);
          setProxyProtocol(data.proxy.protocol);
          setProxyHost(data.proxy.host);
          setProxyPort(data.proxy.port);
        }
      }
    } catch (error) {
      console.error('Error loading credentials:', error);
    }
  };

  const showStatus = (message, type = 'info') => {
    setStatus({ message, type });
    setTimeout(() => setStatus(null), 3000);
  };

  const loginWithToken = async () => {
    if (!token.trim()) {
      showStatus('Please enter a token', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('https://discord.com/api/v9/users/@me', {
        headers: {
          'Authorization': token.trim(),
        },
      });

      if (!response.ok) {
        throw new Error('Invalid token');
      }

      const user = await response.json();
      const authData = {
        token: token.trim(),
        deviceId: deviceId || generateDeviceId(),
        userId: user.id,
        username: user.username,
        loginTime: new Date().toISOString(),
        proxy: {
          enabled: proxyEnabled,
          protocol: proxyProtocol,
          host: proxyHost,
          port: proxyPort,
        },
      };

      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(authData));
      showStatus(`Welcome back, ${user.username}!`, 'success');

      setTimeout(() => {
        Alert.alert('Success', 'Logged in! You can now use Discord.');
      }, 1500);
    } catch (error) {
      showStatus('Login failed: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const saveProxySettings = async () => {
    try {
      const saved = await AsyncStorage.getItem(STORAGE_KEY);
      const data = saved ? JSON.parse(saved) : {};
      data.proxy = {
        enabled: proxyEnabled,
        protocol: proxyProtocol,
        host: proxyHost,
        port: proxyPort,
      };
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      showStatus('Proxy settings saved!', 'success');
    } catch (error) {
      showStatus('Error saving settings', 'error');
    }
  };

  const exportBackup = async () => {
    try {
      const data = await AsyncStorage.getItem(STORAGE_KEY);
      if (!data) {
        showStatus('No account data to export', 'error');
        return;
      }

      const backup = {
        version: '1.0',
        exported: new Date().toISOString(),
        data: JSON.parse(data),
      };

      const filename = `bluecord-backup-${Date.now()}.json`;
      const filepath = FileSystem.DocumentDirectoryPath + '/' + filename;
      await FileSystem.writeAsStringAsync(filepath, JSON.stringify(backup, null, 2));

      showStatus('Backup exported!', 'success');
      Alert.alert('Success', 'Backup saved to: ' + filepath);
    } catch (error) {
      showStatus('Error exporting backup', 'error');
    }
  };

  const importBackup = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/json',
      });

      if (result.type === 'success') {
        const content = await FileSystem.readAsStringAsync(result.uri);
        const backup = JSON.parse(content);

        if (!backup.data || !backup.data.token) {
          showStatus('Invalid backup file', 'error');
          return;
        }

        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(backup.data));
        showStatus('Backup restored!', 'success');
        await loadSavedCredentials();
      }
    } catch (error) {
      showStatus('Error importing backup', 'error');
    }
  };

  const generateDeviceId = () => {
    return 'device_' + Math.random().toString(36).substr(2, 9);
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.wrapper}>
        {/* Header */}
        <View style={styles.logoContainer}>
          <Text style={styles.logoText}>🎮</Text>
        </View>
        <Text style={styles.title}>JZ5</Text>
        <Text style={styles.version}>v3.0.0 - Pro</Text>

        {/* Tabs */}
        <View style={styles.tabsContainer}>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'login' && styles.tabActive]}
            onPress={() => setActiveTab('login')}
          >
            <Text style={[styles.tabText, activeTab === 'login' && styles.tabTextActive]}>
              Login
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'settings' && styles.tabActive]}
            onPress={() => setActiveTab('settings')}
          >
            <Text style={[styles.tabText, activeTab === 'settings' && styles.tabTextActive]}>
              Settings
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'backup' && styles.tabActive]}
            onPress={() => setActiveTab('backup')}
          >
            <Text style={[styles.tabText, activeTab === 'backup' && styles.tabTextActive]}>
              Backup
            </Text>
          </TouchableOpacity>
        </View>

        {/* Login Tab */}
        {activeTab === 'login' && (
          <View style={{ width: '100%' }}>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Token</Text>
              <TextInput
                style={styles.input}
                placeholder="Enter your Discord token"
                placeholderTextColor="#72767d"
                value={token}
                onChangeText={setToken}
                secureTextEntry
              />
              <Text style={styles.hint}>Your authentication token</Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Device ID (Optional)</Text>
              <TextInput
                style={styles.input}
                placeholder="Auto-generated"
                placeholderTextColor="#72767d"
                value={deviceId}
                onChangeText={setDeviceId}
              />
              <Text style={styles.hint}>Leave empty for auto-generation</Text>
            </View>

            <TouchableOpacity
              style={[styles.button, styles.buttonPrimary]}
              onPress={loginWithToken}
              disabled={loading}
            >
              <Text style={styles.buttonText}>
                {loading ? '⏳ Signing In...' : '🚀 SIGN IN'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity style={[styles.button, styles.buttonSecondary]}>
              <Text style={[styles.buttonText, styles.buttonTextSecondary]}>
                📝 Create Account
              </Text>
            </TouchableOpacity>

            <Text style={styles.divider}>———— or ————</Text>

            <TouchableOpacity style={[styles.button, styles.buttonSecondary]}>
              <Text style={[styles.buttonText, styles.buttonTextSecondary]}>
                👤 Guest Login
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <View style={{ width: '100%' }}>
            <View style={styles.settingsGroup}>
              <Text style={styles.settingsTitle}>Proxy Settings</Text>

              <View style={styles.checkboxContainer}>
                <TouchableOpacity
                  style={[styles.checkbox, proxyEnabled && styles.checkboxChecked]}
                  onPress={() => setProxyEnabled(!proxyEnabled)}
                >
                  {proxyEnabled && <Text style={{ color: '#fff' }}>✓</Text>}
                </TouchableOpacity>
                <Text style={styles.checkboxText}>Enable Proxy</Text>
              </View>

              {proxyEnabled && (
                <>
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Protocol</Text>
                    <View style={styles.select}>
                      <TouchableOpacity onPress={() => setProxyProtocol('http')}>
                        <Text style={{ color: '#dbdee1' }}>
                          {proxyProtocol === 'http' ? '✓ ' : ''}HTTP
                        </Text>
                      </TouchableOpacity>
                    </View>
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Host</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="127.0.0.1"
                      placeholderTextColor="#72767d"
                      value={proxyHost}
                      onChangeText={setProxyHost}
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Port</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="8080"
                      placeholderTextColor="#72767d"
                      value={proxyPort}
                      onChangeText={setProxyPort}
                      keyboardType="number-pad"
                    />
                  </View>
                </>
              )}

              <TouchableOpacity
                style={[styles.button, styles.buttonPrimary]}
                onPress={saveProxySettings}
              >
                <Text style={styles.buttonText}>💾 SAVE SETTINGS</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Backup Tab */}
        {activeTab === 'backup' && (
          <View style={{ width: '100%' }}>
            <View style={styles.settingsGroup}>
              <Text style={styles.settingsTitle}>Account Backup & Restore</Text>

              <TouchableOpacity
                style={[styles.button, styles.buttonSecondary]}
                onPress={exportBackup}
              >
                <Text style={[styles.buttonText, styles.buttonTextSecondary]}>
                  ⬇️ EXPORT BACKUP
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.button, styles.buttonSecondary]}
                onPress={importBackup}
              >
                <Text style={[styles.buttonText, styles.buttonTextSecondary]}>
                  ⬆️ IMPORT BACKUP
                </Text>
              </TouchableOpacity>

              <View style={styles.backupInfo}>
                <Text style={styles.backupInfoText}>
                  💾 Backup your account credentials securely
                </Text>
                <Text style={styles.backupInfoText}>
                  ⚠️ Never share your backup file with anyone
                </Text>
              </View>
            </View>
          </View>
        )}

        {/* Status Message */}
        {status && (
          <View
            style={[
              styles.statusMessage,
              status.type === 'success' && styles.statusSuccess,
              status.type === 'error' && styles.statusError,
              status.type === 'info' && styles.statusInfo,
            ]}
          >
            <Text
              style={[
                styles.statusText,
                status.type === 'success' && styles.statusTextSuccess,
                status.type === 'error' && styles.statusTextError,
                status.type === 'info' && styles.statusTextInfo,
              ]}
            >
              {status.message}
            </Text>
          </View>
        )}

        {/* Footer */}
        <View style={styles.footer}>
          <TouchableOpacity>
            <Text style={styles.footerLink}>Forgot Password?</Text>
          </TouchableOpacity>
          <Text style={styles.footerDot}>•</Text>
          <TouchableOpacity>
            <Text style={styles.footerLink}>Help</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
