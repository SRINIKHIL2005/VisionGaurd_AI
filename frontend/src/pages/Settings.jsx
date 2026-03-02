import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Settings as SettingsIcon, MessageCircle, Save, AlertCircle, CheckCircle, HelpCircle, ExternalLink, Eye, EyeOff, Send } from 'lucide-react';
import authService from '../services/authService';

function Settings() {
  const [user, setUser] = useState(null);
  const [telegramSettings, setTelegramSettings] = useState({
    enabled: false,
    bot_token: '',
    chat_id: '',
    cooldown_minutes: 3,
    retention_days: 10
  });
  const [assistantSettings, setAssistantSettings] = useState({
    enabled: false,
    name: 'Jarvis',
    voice: 'male',
    web_control_enabled: false
  });
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantSaveStatus, setAssistantSaveStatus] = useState(null);
  const [showTutorial, setShowTutorial] = useState(false);
  const [showBotToken, setShowBotToken] = useState(false);
  const [showChatId, setShowChatId] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const currentUser = authService.getCurrentUser();
    setUser(currentUser);
    
    const fetchSettings = async () => {
      try {
        const axios = authService.getAuthAxios();
        const response = await axios.get('/user/telegram-settings');
        if (response.data.settings) {
          setTelegramSettings({
            enabled: response.data.settings.enabled || false,
            bot_token: response.data.settings.bot_token || '',
            chat_id: response.data.settings.chat_id || '',
            cooldown_minutes: response.data.settings.cooldown_minutes || 3,
            retention_days: response.data.settings.retention_days || 10
          });
        }
      } catch (error) {
        console.error('Failed to fetch settings:', error);
      }
    };

    const fetchAssistantSettings = async () => {
      try {
        const axios = authService.getAuthAxios();
        const response = await axios.get('/user/assistant-settings');
        if (response.data.settings) {
          setAssistantSettings({
            enabled: !!response.data.settings.enabled,
            name: response.data.settings.name || 'Jarvis',
            voice: response.data.settings.voice || 'male',
            web_control_enabled: !!response.data.settings.web_control_enabled
          });
        }
      } catch (error) {
        console.error('Failed to fetch assistant settings:', error);
      }
    };
    
    fetchSettings();
    fetchAssistantSettings();
  }, []);

  const handleAssistantChange = (e) => {
    const { name, value, type, checked } = e.target;

    setAssistantSaveStatus(null);

    const updated = {
      ...assistantSettings,
      [name]: type === 'checkbox' ? checked : value
    };

    setAssistantSettings(updated);

    // Auto-save on toggle changes to match Telegram UX
    if (name === 'enabled' || name === 'voice' || name === 'web_control_enabled') {
      saveAssistantSettingsToBackend(updated);
    }
  };

  const saveAssistantSettingsToBackend = async (settings) => {
    setAssistantLoading(true);
    setAssistantSaveStatus(null);

    try {
      const axios = authService.getAuthAxios();
      const payload = {
        enabled: !!settings.enabled,
        name: 'Jarvis',
        voice: settings.voice || 'male',
        web_control_enabled: !!settings.web_control_enabled
      };
      await axios.put('/user/assistant-settings', payload);

      setAssistantSettings(payload);
      try {
        window.dispatchEvent(new CustomEvent('visionguard:assistant-settings', { detail: payload }));
      } catch {
        // ignore
      }
      setAssistantSaveStatus({
        type: 'success',
        message: payload.enabled
          ? `AI Assistant enabled as “${payload.name}”`
          : 'AI Assistant disabled'
      });
    } catch (error) {
      setAssistantSaveStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to save assistant settings'
      });
      // Revert toggle on failure
      if (settings.enabled) {
        setAssistantSettings({
          ...settings,
          enabled: false
        });
      }
    }

    setAssistantLoading(false);
  };

  const handleAssistantSave = async () => {
    const payload = {
      enabled: !!assistantSettings.enabled,
      name: 'Jarvis',
      voice: assistantSettings.voice || 'male',
      web_control_enabled: !!assistantSettings.web_control_enabled
    };

    await saveAssistantSettingsToBackend(payload);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    
    // For toggle: validate and auto-save
    if (name === 'enabled' && checked) {
      if (!telegramSettings.bot_token || !telegramSettings.chat_id) {
        setSaveStatus({
          type: 'error',
          message: 'Please fill in Bot Token and Chat ID first, then click Save Settings'
        });
        return;
      }
    }
    
    // Clear error when user starts filling required fields
    if ((name === 'bot_token' || name === 'chat_id') && value) {
      setSaveStatus(null);
    }
    
    const updatedSettings = {
      ...telegramSettings,
      [name]: type === 'checkbox' ? checked : value
    };
    
    setTelegramSettings(updatedSettings);
    
    // Auto-save when toggle is enabled
    if (name === 'enabled' && checked) {
      saveSettingsToBackend(updatedSettings);
    }
  };

  const saveSettingsToBackend = async (settings) => {
    setLoading(true);
    setSaveStatus(null);

    try {
      const axios = authService.getAuthAxios();
      await axios.put('/user/telegram-settings', settings);
      
      console.log('✅ Telegram settings saved:', settings);
      
      // If enabling notifications, automatically send test message
      if (settings.enabled) {
        try {
          const testResponse = await axios.post('/user/test-telegram');
          setSaveStatus({ 
            type: 'success', 
            message: '✅ Enabled! Test message sent to your Telegram. Check your app!' 
          });
        } catch (testError) {
          console.error('❌ Test notification failed:', testError);
          const errorMsg = testError.response?.data?.detail || 'Failed to send test notification';
          setSaveStatus({
            type: 'error',
            message: `⚠️ Settings saved but test failed: ${errorMsg}`
          });
        }
      } else {
        setSaveStatus({ type: 'success', message: 'Telegram notifications disabled' });
      }
    } catch (error) {
      console.error('❌ Failed to save settings:', error);
      setSaveStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to save settings'
      });
      // Revert toggle on failure
      setTelegramSettings({
        ...settings,
        enabled: false
      });
    }

    setLoading(false);
  };

  const handleSave = async () => {
    // Validate if trying to enable without required fields
    if (telegramSettings.enabled && (!telegramSettings.bot_token || !telegramSettings.chat_id)) {
      setSaveStatus({
        type: 'error',
        message: 'Bot Token and Chat ID are required when notifications are enabled'
      });
      return;
    }

    await saveSettingsToBackend(telegramSettings);
  };

  const handleTestNotification = async () => {
    setTesting(true);
    setSaveStatus(null);

    try {
      const axios = authService.getAuthAxios();
      const response = await axios.post('/user/test-telegram');
      
      setSaveStatus({ 
        type: 'success', 
        message: response.data.message || 'Test notification sent! Check your Telegram app!' 
      });
    } catch (error) {
      setSaveStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to send test notification'
      });
    }

    setTesting(false);
  };

  return (
    <div className="max-w-4xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl">
            <SettingsIcon className="w-8 h-8 text-white" />
          </div>
          Account Settings
        </h1>
        <p className="text-gray-600 mt-2">
          Configure your Telegram notifications and preferences
        </p>
      </motion.div>

      {/* Telegram Notification Guide Banner */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl shadow-lg p-6 text-white mb-6"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 bg-white/20 rounded-xl backdrop-blur">
            <MessageCircle className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold mb-2">
              🔔 Real-Time Telegram Notifications
            </h3>
            <p className="text-blue-50 mb-3">
              Get instant alerts on your phone when unknown faces are detected by the AI system. 
              Works automatically in the background - no need to keep the app open!
            </p>
            <div className="bg-white/10 backdrop-blur rounded-lg p-4 space-y-2">
              <p className="text-sm font-semibold">✨ How it works:</p>
              <ol className="text-sm space-y-1 text-blue-50">
                <li>1️⃣ Create your personal Telegram bot (takes 2 minutes)</li>
                <li>2️⃣ Enter bot token and chat ID below</li>
                <li>3️⃣ Enable notifications - that's it!</li>
                <li>4️⃣ Receive instant alerts whenever unknown faces are detected</li>
              </ol>
              <p className="text-xs text-blue-100 mt-3 italic">
                💡 Once enabled, notifications work continuously - even when you're away from your computer. 
                You can disable anytime from this page.
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="space-y-6">
        {/* User Info Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-2xl shadow-lg p-6"
        >
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Account Information
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Full Name</span>
              <span className="font-medium text-gray-900">{user?.full_name}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Email</span>
              <span className="font-medium text-gray-900">{user?.email}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-gray-600">User ID</span>
              <span className="font-mono text-sm text-gray-500">{user?.user_id}</span>
            </div>
          </div>
        </motion.div>

        {/* Telegram Settings Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl shadow-lg p-6"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <MessageCircle className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  Telegram Notifications
                </h2>
                <p className="text-sm text-gray-600">
                  Receive alerts for unknown face detections
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowTutorial(!showTutorial)}
              className="flex items-center gap-2 px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            >
              <HelpCircle className="w-5 h-5" />
              How to setup?
            </button>
          </div>

          {/* Tutorial Expansion */}
          {showTutorial && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-6"
            >
              <h3 className="font-semibold text-blue-900 mb-4 flex items-center gap-2">
                <HelpCircle className="w-5 h-5" />
                How to Setup Telegram Bot (Step-by-Step)
              </h3>
              <ol className="space-y-3 text-sm text-blue-900">
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-xs">
                    1
                  </span>
                  <div>
                    <strong>Create a Telegram Bot:</strong>
                    <ul className="mt-1 ml-4 space-y-1 text-blue-800">
                      <li>• Open Telegram and search for <code className="bg-white px-2 py-0.5 rounded">@BotFather</code></li>
                      <li>• Send <code className="bg-white px-2 py-0.5 rounded">/newbot</code> command</li>
                      <li>• Choose a name for your bot (e.g., "My VisionGuard Bot")</li>
                      <li>• Choose a username ending in "bot" (e.g., "myname_visionguard_bot")</li>
                      <li>• Copy the <strong>Bot Token</strong> you receive</li>
                    </ul>
                  </div>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-xs">
                    2
                  </span>
                  <div>
                    <strong>Get Your Chat ID:</strong>
                    <ul className="mt-1 ml-4 space-y-1 text-blue-800">
                      <li>• Search for your bot in Telegram</li>
                      <li>• Start a chat by clicking "Start"</li>
                      <li>• Send any message to your bot</li>
                      <li>• Open: <a href="https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">https://api.telegram.org/bot&lt;YOUR_BOT_TOKEN&gt;/getUpdates</a></li>
                      <li>• Find <code className="bg-white px-2 py-0.5 rounded">"chat":{'{'}{"id"}:123456789{'}'}</code> in the response</li>
                      <li>• Copy your Chat ID (the number)</li>
                    </ul>
                  </div>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-xs">
                    3
                  </span>
                  <div>
                    <strong>Enter Settings Below:</strong>
                    <ul className="mt-1 ml-4 space-y-1 text-blue-800">
                      <li>• Paste your Bot Token in "Bot Token" field</li>
                      <li>• Paste your Chat ID in "Chat ID" field</li>
                      <li>• Enable notifications</li>
                      <li>• Click "Save Settings"</li>
                    </ul>
                  </div>
                </li>
              </ol>
              <div className="mt-4 pt-4 border-t border-blue-300">
                <a
                  href="https://core.telegram.org/bots"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 flex items-center gap-2 text-sm font-medium"
                >
                  <ExternalLink className="w-4 h-4" />
                  Official Telegram Bot Documentation
                </a>
              </div>
            </motion.div>
          )}

          {/* Save Status */}
          {saveStatus && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`mb-4 px-4 py-3 rounded-lg flex items-center gap-2 ${
                saveStatus.type === 'success'
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              {saveStatus.type === 'success' ? (
                <CheckCircle className="w-5 h-5 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
              )}
              <span className="text-sm">{saveStatus.message}</span>
            </motion.div>
          )}

          <div className="space-y-6">
            {/* Enable Toggle */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  Enable Telegram Notifications
                  {telegramSettings.enabled && (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-semibold rounded-full">
                      ACTIVE
                    </span>
                  )}
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  {telegramSettings.enabled 
                    ? '✅ Active! You will receive Telegram alerts for unknown faces'
                    : '⚠️ 1. Fill Bot Token & Chat ID below → 2. Toggle ON → 3. Click Save'
                  }
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  name="enabled"
                  checked={telegramSettings.enabled}
                  onChange={handleChange}
                  className="sr-only peer"
                />
                <div className="relative w-14 h-8 bg-gray-300 peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[4px] after:start-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>

            {/* Bot Token - Only visible when toggle is on */}
            {(telegramSettings.enabled || telegramSettings.bot_token) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bot Token
                <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showBotToken ? "text" : "password"}
                  name="bot_token"
                  value={telegramSettings.bot_token || ''}
                  onChange={handleChange}
                  placeholder="••••••••••••••••••••••••••••••"
                  className="w-full px-4 py-3 pr-12 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowBotToken(!showBotToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 focus:outline-none"
                >
                  {showBotToken ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Get this from @BotFather on Telegram
              </p>
            </div>
            )}

            {/* Chat ID - Only visible when toggle is on */}
            {(telegramSettings.enabled || telegramSettings.chat_id) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Chat ID
                <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showChatId ? "text" : "password"}
                  name="chat_id"
                  value={telegramSettings.chat_id || ''}
                  onChange={handleChange}
                  placeholder="••••••••••"
                  className="w-full px-4 py-3 pr-12 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowChatId(!showChatId)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 focus:outline-none"
                >
                  {showChatId ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Your personal Telegram chat ID (numeric)
              </p>
            </div>
            )}

            {/* Advanced Settings */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Cooldown Minutes
                </label>
                <input
                  type="number"
                  name="cooldown_minutes"
                  value={telegramSettings.cooldown_minutes}
                  onChange={handleChange}
                  min="1"
                  max="60"
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Wait time before re-notifying same face
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Retention Days
                </label>
                <input
                  type="number"
                  name="retention_days"
                  value={telegramSettings.retention_days}
                  onChange={handleChange}
                  min="1"
                  max="365"
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Keep unknown face images for X days
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-4">
              {/* Test Notification Button */}
              {telegramSettings.enabled && (
                <button
                  onClick={handleTestNotification}
                  disabled={testing || loading}
                  className="bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 focus:ring-4 focus:ring-green-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {testing ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <Send className="w-5 h-5" />
                      Test Notification
                    </>
                  )}
                </button>
              )}
              
              {/* Save Button */}
              <button
                onClick={handleSave}
                disabled={loading}
                className={`${telegramSettings.enabled ? '' : 'col-span-2'} bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 rounded-lg font-medium hover:from-blue-700 hover:to-purple-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2`}
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-5 h-5" />
                    Save Settings
                  </>
                )}
              </button>
            </div>
          </div>
        </motion.div>

        {/* AI Assistant Settings Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-white rounded-2xl shadow-lg p-6"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-100 rounded-lg">
              <SettingsIcon className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">AI Assistant</h2>
              <p className="text-sm text-gray-600">Enable and name your surveillance assistant</p>
            </div>
          </div>

          {/* Assistant Save Status */}
          {assistantSaveStatus && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`mt-4 mb-4 px-4 py-3 rounded-lg flex items-center gap-2 ${
                assistantSaveStatus.type === 'success'
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              {assistantSaveStatus.type === 'success' ? (
                <CheckCircle className="w-5 h-5 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
              )}
              <span className="text-sm">{assistantSaveStatus.message}</span>
            </motion.div>
          )}

          <div className="space-y-6">
            {/* Enable Toggle */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  Enable AI Assistant
                  {assistantSettings.enabled && (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-semibold rounded-full">
                      ACTIVE
                    </span>
                  )}
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  {assistantSettings.enabled
                    ? '✅ Active! Jarvis features can speak and narrate alerts'
                    : 'Turn this ON to enable Jarvis-style narration'
                  }
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  name="enabled"
                  checked={assistantSettings.enabled}
                  onChange={handleAssistantChange}
                  className="sr-only peer"
                />
                <div className="relative w-14 h-8 bg-gray-300 peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[4px] after:start-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-purple-600"></div>
              </label>
            </div>

            <p className="text-sm text-gray-700">
              Wake phrase: <span className="font-semibold">Hey Jarvis</span>
            </p>

            {/* Web Control Toggle */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-purple-100">
              <div>
                <h3 className="font-medium text-gray-900 flex items-center gap-2">
                  Web Control Mode
                  {assistantSettings.web_control_enabled && (
                    <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs font-semibold rounded-full">
                      ACTIVE
                    </span>
                  )}
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  {assistantSettings.web_control_enabled
                    ? '✅ Jarvis can navigate pages, start Live CCTV, and control the UI with your voice'
                    : 'Enable to let Jarvis navigate pages and control features via voice commands'
                  }
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Example: "Go to Live CCTV", "Open Settings", "Start live monitoring"
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer ml-4 flex-shrink-0">
                <input
                  type="checkbox"
                  name="web_control_enabled"
                  checked={assistantSettings.web_control_enabled}
                  onChange={handleAssistantChange}
                  className="sr-only peer"
                />
                <div className="relative w-14 h-8 bg-gray-300 peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[4px] after:start-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-purple-600"></div>
              </label>
            </div>

            {/* Voice Preference */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Voice
              </label>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="radio"
                    name="voice"
                    value="male"
                    checked={assistantSettings.voice === 'male'}
                    onChange={handleAssistantChange}
                    className="text-purple-600 focus:ring-purple-500"
                  />
                  Male
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="radio"
                    name="voice"
                    value="female"
                    checked={assistantSettings.voice === 'female'}
                    onChange={handleAssistantChange}
                    className="text-purple-600 focus:ring-purple-500"
                  />
                  Female
                </label>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Uses installed Windows voices. If the chosen voice isn’t available, it falls back automatically.
              </p>
            </div>

            {/* Save Button */}
            <button
              onClick={handleAssistantSave}
              disabled={assistantLoading}
              className="bg-gradient-to-r from-purple-600 to-pink-600 text-white py-3 rounded-lg font-medium hover:from-purple-700 hover:to-pink-700 focus:ring-4 focus:ring-purple-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {assistantLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Assistant Settings
                </>
              )}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );

}
export default Settings;

