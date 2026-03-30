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
    web_control_enabled: false,
    voice_lock_enabled: false,
  });
  const [loiteringSettings, setLoiteringSettings] = useState({
    min_duration: 5.0,
    position_threshold: 50
  });
  const [voiceEnrolled, setVoiceEnrolled]   = useState(false);
  const [enrollStatus, setEnrollStatus]     = useState(null);
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
            web_control_enabled: !!response.data.settings.web_control_enabled,
            voice_lock_enabled: !!response.data.settings.voice_lock_enabled,
          });
          setVoiceEnrolled(!!response.data.settings.voice_enrolled);
        }
      } catch (error) {
        console.error('Failed to fetch assistant settings:', error);
      }
    };

    const fetchVideoAnalysisSettings = async () => {
      try {
        const axios = authService.getAuthAxios();
        const response = await axios.get('/user/video-analysis-settings');
        if (response.data.settings) {
          setLoiteringSettings({
            min_duration: response.data.settings.min_loitering_duration || 5.0,
            position_threshold: response.data.settings.loitering_position_threshold || 50
          });
        }
      } catch (error) {
        console.error('Failed to fetch video analysis settings:', error);
      }
    };
    
    fetchSettings();
    fetchAssistantSettings();
    fetchVideoAnalysisSettings();
  }, []);

  // Save video analysis settings
  const saveVideoAnalysisSettings = async () => {
    try {
      setLoading(true);
      const axios = authService.getAuthAxios();
      await axios.put('/user/video-analysis-settings', {
        min_loitering_duration: loiteringSettings.min_duration,
        loitering_position_threshold: loiteringSettings.position_threshold
      });
      setSaveStatus({ type: 'success', message: '✅ Video analysis settings saved successfully!' });
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (error) {
      setSaveStatus({ 
        type: 'error', 
        message: error.response?.data?.detail || 'Failed to save video analysis settings' 
      });
    } finally {
      setLoading(false);
    }
  };

  // Handle loitering settings changes
  const handleLoiteringChange = (field, value) => {
    setLoiteringSettings(prev => ({
      ...prev,
      [field]: value
    }));
    setSaveStatus(null);
  };

  const handleAssistantChange = (e) => {
    const { name, value, type, checked } = e.target;

    setAssistantSaveStatus(null);

    const updated = {
      ...assistantSettings,
      [name]: type === 'checkbox' ? checked : value
    };

    setAssistantSettings(updated);

    // Auto-save on toggle changes to match Telegram UX
    if (name === 'enabled' || name === 'voice' || name === 'web_control_enabled' || name === 'voice_lock_enabled') {
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
        web_control_enabled: !!settings.web_control_enabled,
        voice_lock_enabled: !!settings.voice_lock_enabled,
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
      web_control_enabled: !!assistantSettings.web_control_enabled,
      voice_lock_enabled: !!assistantSettings.voice_lock_enabled,
    };

    await saveAssistantSettingsToBackend(payload);
  };

  const handleRemoveVoice = async () => {
    if (!window.confirm('Remove voice enrollment? Voice Lock will be disabled.')) return;
    try {
      const axios = authService.getAuthAxios();
      await axios.delete('/user/enroll-voice');
      setVoiceEnrolled(false);
      setAssistantSettings(s => ({ ...s, voice_lock_enabled: false }));
      setEnrollStatus({ type: 'success', message: 'Voice enrollment removed.' });
    } catch {
      setEnrollStatus({ type: 'error', message: 'Failed to remove voice enrollment.' });
    }
    setTimeout(() => setEnrollStatus(null), 4000);
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
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl">
            <SettingsIcon className="w-8 h-8 text-white" />
          </div>
          Account Settings
        </h1>
        <p className="text-slate-400 mt-2">
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
          className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6"
        >
          <h2 className="text-xl font-semibold text-white mb-4">
            Account Information
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Full Name</span>
              <span className="font-medium text-white">{user?.full_name}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Email</span>
              <span className="font-medium text-white">{user?.email}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-400">User ID</span>
              <span className="font-mono text-sm text-slate-500">{user?.user_id}</span>
            </div>
          </div>
        </motion.div>

        {/* Telegram Settings Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6"
            > 
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-900/30 rounded-lg">
                <MessageCircle className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Telegram Notifications
                </h2>
                <p className="text-sm text-slate-400">
                  Receive alerts for unknown face detections
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowTutorial(!showTutorial)}
              className="flex items-center gap-2 px-4 py-2 text-blue-400 hover:bg-blue-900/20 rounded-lg transition-colors"
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
              className="mb-6 bg-blue-900/20 border border-blue-500/30 rounded-lg p-6"
            >
              <h3 className="font-semibold text-blue-300 mb-4 flex items-center gap-2">
                <HelpCircle className="w-5 h-5" />
                How to Setup Telegram Bot (Step-by-Step)
              </h3>
              <ol className="space-y-3 text-sm text-blue-200">
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-xs">
                    1
                  </span>
                  <div>
                    <strong>Create a Telegram Bot:</strong>
                    <ul className="mt-1 ml-4 space-y-1 text-blue-300">
                      <li>• Open Telegram and search for <code className="bg-slate-800 px-2 py-0.5 rounded text-blue-200">@BotFather</code></li>
                      <li>• Send <code className="bg-slate-800 px-2 py-0.5 rounded text-blue-200">/newbot</code> command</li>
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
                    <ul className="mt-1 ml-4 space-y-1 text-blue-300">
                      <li>• Search for your bot in Telegram</li>
                      <li>• Start a chat by clicking "Start"</li>
                      <li>• Send any message to your bot</li>
                      <li>• Open: <a href="https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates" target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">https://api.telegram.org/bot&lt;YOUR_BOT_TOKEN&gt;/getUpdates</a></li>
                      <li>• Find <code className="bg-slate-800 px-2 py-0.5 rounded text-blue-200">"chat":{'{'}{"id"}:123456789{'}'}</code> in the response</li>
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
                    <ul className="mt-1 ml-4 space-y-1 text-blue-300">
                      <li>• Paste your Bot Token in "Bot Token" field</li>
                      <li>• Paste your Chat ID in "Chat ID" field</li>
                      <li>• Enable notifications</li>
                      <li>• Click "Save Settings"</li>
                    </ul>
                  </div>
                </li>
              </ol>
              <div className="mt-4 pt-4 border-t border-blue-500/30">
                <a
                  href="https://core.telegram.org/bots"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 flex items-center gap-2 text-sm font-medium"
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
                  ? 'bg-green-900/20 border border-green-500/30 text-green-300'
                  : 'bg-red-900/20 border border-red-500/30 text-red-300'
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
            <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
              <div>
                <h3 className="font-medium text-white flex items-center gap-2">
                  Enable Telegram Notifications
                  {telegramSettings.enabled && (
                    <span className="px-2 py-0.5 bg-green-900/40 text-green-300 text-xs font-semibold rounded-full">
                      ACTIVE
                    </span>
                  )}
                </h3>
                <p className="text-sm text-slate-400 mt-1">
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

            {/* Bot Token */}
            {(
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Bot Token
                <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <input
                  type={showBotToken ? "text" : "password"}
                  name="bot_token"
                  value={telegramSettings.bot_token || ''}
                  onChange={handleChange}
                  placeholder="••••••••••••••••••••••••••••••"
                  className="w-full px-4 py-3 pr-12 bg-[#091220] border border-slate-700/50 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm text-white"
                />
                <button
                  type="button"
                  onClick={() => setShowBotToken(!showBotToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none"
                >
                  {showBotToken ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Get this from @BotFather on Telegram
              </p>
            </div>
            )}

            {/* Chat ID */}
            {(
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Chat ID
                <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <input
                  type={showChatId ? "text" : "password"}
                  name="chat_id"
                  value={telegramSettings.chat_id || ''}
                  onChange={handleChange}
                  placeholder="••••••••••"
                  className="w-full px-4 py-3 pr-12 bg-[#091220] border border-slate-700/50 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm text-white"
                />
                <button
                  type="button"
                  onClick={() => setShowChatId(!showChatId)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 focus:outline-none"
                >
                  {showChatId ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Your personal Telegram chat ID (numeric)
              </p>
            </div>
            )}

            {/* Action Buttons */}
            <div className={`pt-3 flex flex-col gap-3`}>
              {/* Save Button */}
              <button
                onClick={handleSave}
                disabled={loading}
                className="group relative w-full overflow-hidden rounded-2xl p-px active:scale-[0.98] transition-transform duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
              >
                {/* Animated gradient border */}
                <span className="absolute inset-0 rounded-2xl bg-gradient-to-r from-blue-500 via-violet-500 to-cyan-400 opacity-80 group-hover:opacity-100 transition-opacity duration-300" />
                {/* Inner fill */}
                <span className="relative flex items-center justify-center gap-2.5 w-full py-3.5 px-6 rounded-2xl bg-[#0a1628] group-hover:bg-[#0c1a30] transition-colors duration-200">
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      <span className="text-sm font-semibold text-blue-200 tracking-wide">Saving changes…</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 text-blue-300 group-hover:text-white transition-colors duration-200" />
                      <span className="text-sm font-semibold bg-gradient-to-r from-blue-300 via-violet-300 to-cyan-300 bg-clip-text text-transparent group-hover:from-white group-hover:via-white group-hover:to-white transition-all duration-200">
                        Apply Changes
                      </span>
                    </>
                  )}
                </span>
              </button>

              {/* Test Notification Button */}
              {telegramSettings.enabled && (
                <button
                  onClick={handleTestNotification}
                  disabled={testing || loading}
                  className="group relative w-full overflow-hidden rounded-2xl p-px active:scale-[0.98] transition-transform duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
                >
                  {/* Gradient border */}
                  <span className="absolute inset-0 rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-400 to-green-400 opacity-60 group-hover:opacity-90 transition-opacity duration-300" />
                  {/* Inner fill */}
                  <span className="relative flex items-center justify-center gap-2.5 w-full py-3 px-6 rounded-2xl bg-[#0a1628] group-hover:bg-[#091f18] transition-colors duration-200">
                    {testing ? (
                      <>
                        <div className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                        <span className="text-sm font-semibold text-emerald-300 tracking-wide">Firing off message…</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4 text-emerald-400 group-hover:text-white transition-colors duration-200" />
                        <span className="text-sm font-semibold bg-gradient-to-r from-emerald-300 to-teal-300 bg-clip-text text-transparent group-hover:from-white group-hover:to-white transition-all duration-200">
                          Ping My Telegram
                        </span>
                      </>
                    )}
                  </span>
                </button>
              )}
            </div>
          </div>
        </motion.div>

        {/* AI Assistant Settings Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-900/30 rounded-lg">
              <SettingsIcon className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">AI Assistant</h2>
            </div>
          </div>

          {/* Assistant Save Status */}
          {assistantSaveStatus && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`mt-4 mb-4 px-4 py-3 rounded-lg flex items-center gap-2 ${
                assistantSaveStatus.type === 'success'
                  ? 'bg-green-900/20 border border-green-500/30 text-green-300'
                  : 'bg-red-900/20 border border-red-500/30 text-red-300'
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
            <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
              <div>
                <h3 className="font-medium text-white flex items-center gap-2">
                  Enable AI Assistant
                  {assistantSettings.enabled && (
                    <span className="px-2 py-0.5 bg-green-900/40 text-green-300 text-xs font-semibold rounded-full">
                      ACTIVE
                    </span>
                  )}
                </h3>
                <p className="text-sm text-slate-400 mt-1">
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

            <p className="text-sm text-slate-300">
              Wake phrase: <span className="font-semibold text-white">Hey Jarvis</span>
            </p>

            {/* Web Control Toggle */}
            <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg border border-purple-500/20">
              <div>
                <h3 className="font-medium text-white flex items-center gap-2">
                  Web Control Mode
                  {assistantSettings.web_control_enabled && (
                    <span className="px-2 py-0.5 bg-purple-900/40 text-purple-300 text-xs font-semibold rounded-full">
                      ACTIVE
                    </span>
                  )}
                </h3>
                <p className="text-sm text-slate-400 mt-1">
                  {assistantSettings.web_control_enabled
                    ? '✅ Jarvis can navigate pages, start Live CCTV, and control the UI with your voice'
                    : 'Enable to let Jarvis navigate pages and control features via voice commands'
                  }
                </p>
                <p className="text-xs text-slate-500 mt-1">
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
            {/* Voice Lock */}
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg border border-purple-500/20">
                <div>
                  <h3 className="font-medium text-white flex items-center gap-2">
                    🔒 Voice Lock
                    {assistantSettings.voice_lock_enabled && (
                      <span className="px-2 py-0.5 bg-purple-900/40 text-purple-300 text-xs font-semibold rounded-full">ON</span>
                    )}
                  </h3>
                  <p className="text-sm text-slate-400 mt-1">
                    {assistantSettings.voice_lock_enabled
                      ? 'Jarvis will only respond to your registered voice'
                      : 'When ON, Jarvis verifies your voice before responding'}
                  </p>
                  {!voiceEnrolled && assistantSettings.voice_lock_enabled && (
                    <p className="text-xs text-amber-400 mt-1">⚠️ No voice enrolled — register first</p>
                  )}
                </div>
                <label className="relative inline-flex items-center cursor-pointer ml-4 flex-shrink-0">
                  <input
                    type="checkbox"
                    name="voice_lock_enabled"
                    checked={assistantSettings.voice_lock_enabled}
                    onChange={handleAssistantChange}
                    className="sr-only peer"
                  />
                  <div className="relative w-14 h-8 bg-gray-300 peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[4px] after:start-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-purple-600"></div>
                </label>
              </div>

              {/* Owner voice enrollment status */}
              <div className="p-4 bg-slate-800/20 rounded-lg border border-slate-700/40">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-300">Owner Voice</p>
                    {voiceEnrolled
                      ? <p className="text-xs text-green-400 mt-0.5">✅ Voice registered</p>
                      : <p className="text-xs text-slate-500 mt-0.5">⚠️ No voice registered yet</p>
                    }
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { window.location.href = '/voice-setup' }}
                      className="px-3 py-1.5 text-xs rounded-lg bg-purple-600/20 text-purple-300 hover:bg-purple-600/30 border border-purple-500/30 transition-all"
                    >
                      {voiceEnrolled ? 'Re-enroll' : '+ Register Voice'}
                    </button>
                    {voiceEnrolled && (
                      <button
                        onClick={handleRemoveVoice}
                        className="px-3 py-1.5 text-xs rounded-lg bg-red-600/20 text-red-300 hover:bg-red-600/30 border border-red-500/30 transition-all"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
                {enrollStatus && (
                  <p className={`text-xs mt-2 ${enrollStatus.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                    {enrollStatus.message}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={handleAssistantSave}
              disabled={assistantLoading}
              className="group relative w-full overflow-hidden rounded-2xl p-px mt-2 active:scale-[0.98] transition-transform duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
            >
              <span className="absolute inset-0 rounded-2xl bg-gradient-to-r from-purple-500 via-pink-500 to-fuchsia-400 opacity-80 group-hover:opacity-100 transition-opacity duration-300" />
              <span className="relative flex items-center justify-center gap-2.5 w-full py-3.5 px-6 rounded-2xl bg-[#0a1628] group-hover:bg-[#150d1e] transition-colors duration-200">
                {assistantLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                    <span className="text-sm font-semibold text-purple-200 tracking-wide">Saving changes…</span>
                  </>
                ) : (
                  <span className="text-sm font-semibold bg-gradient-to-r from-purple-300 via-pink-300 to-fuchsia-300 bg-clip-text text-transparent group-hover:from-white group-hover:via-white group-hover:to-white transition-all duration-200">
                    Apply Assistant Settings
                  </span>
                )}
              </span>
            </button>
          </div>
        </motion.div>

        {/* Video Analysis Settings */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-[#060c18] rounded-2xl border border-slate-800/60 p-6"
        >
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <div className="p-2 bg-yellow-500/20 rounded-lg">
              <AlertCircle className="w-5 h-5 text-yellow-400" />
            </div>
            Loitering Detection Settings
          </h2>
          <p className="text-slate-400 text-sm mb-6">
            Customize how loitering is detected in video analysis. These settings determine what counts as suspicious loitering behavior.
          </p>
          
          <div className="space-y-4">
            {/* Min Duration Setting */}
            <div className="p-4 bg-slate-800/30 rounded-lg border border-slate-700/50">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <label className="block font-medium text-white text-sm">⏱️ Minimum Loitering Duration</label>
                  <p className="text-xs text-slate-400 mt-1">How long (in seconds) someone must stay in one place to be flagged as loitering</p>
                </div>
                <span className="px-3 py-1 bg-yellow-500/20 text-yellow-300 rounded-full text-sm font-mono">
                  {loiteringSettings.min_duration}s
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="30"
                step="0.5"
                value={loiteringSettings.min_duration}
                onChange={(e) => handleLoiteringChange('min_duration', parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-yellow-500"
              />
              <div className="flex justify-between text-xs text-slate-500 mt-2">
                <span>1s (Very Sensitive)</span>
                <span>30s (Very Lenient)</span>
              </div>
            </div>

            {/* Position Threshold Setting */}
            <div className="p-4 bg-slate-800/30 rounded-lg border border-slate-700/50">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <label className="block font-medium text-white text-sm">📍 Position Threshold</label>
                  <p className="text-xs text-slate-400 mt-1">Maximum distance (in pixels) someone can move and still be considered in the same location</p>
                </div>
                <span className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm font-mono">
                  {loiteringSettings.position_threshold}px
                </span>
              </div>
              <input
                type="range"
                min="10"
                max="200"
                step="5"
                value={loiteringSettings.position_threshold}
                onChange={(e) => handleLoiteringChange('position_threshold', parseInt(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
              />
              <div className="flex justify-between text-xs text-slate-500 mt-2">
                <span>10px (Strict)</span>
                <span>200px (Loose)</span>
              </div>
            </div>

            {/* Info Box */}
            <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
              <p className="text-xs text-blue-300 flex gap-2">
                <span>ℹ️</span>
                <span>
                  <strong>Lower duration</strong> = more sensitive (flags loitering sooner) | 
                  <strong> Smaller threshold</strong> = stricter (requires staying in exact same spot)
                </span>
              </p>
            </div>

            {/* Save Button */}
            <button
              onClick={saveVideoAnalysisSettings}
              disabled={loading}
              className="group relative w-full overflow-hidden rounded-lg p-px active:scale-[0.98] transition-transform duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
            >
              <span className="absolute inset-0 rounded-lg bg-gradient-to-r from-yellow-500 to-orange-500 opacity-80 group-hover:opacity-100 transition-opacity duration-300" />
              <span className="relative flex items-center justify-center gap-2.5 w-full py-2.5 px-4 rounded-lg bg-[#0a1628] group-hover:bg-[#150d1e] transition-colors duration-200">
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
                    <span className="text-sm font-semibold text-yellow-200">Saving...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    <span className="text-sm font-semibold bg-gradient-to-r from-yellow-300 to-orange-300 bg-clip-text text-transparent">
                      Save Video Analysis Settings
                    </span>
                  </>
                )}
              </span>
            </button>

            {/* Save Status */}
            {saveStatus && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-3 rounded-lg ${
                  saveStatus.type === 'success'
                    ? 'bg-green-900/40 border border-green-500/50 text-green-300'
                    : 'bg-red-900/40 border border-red-500/50 text-red-300'
                }`}
              >
                {saveStatus.message}
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );

}
export default Settings;

