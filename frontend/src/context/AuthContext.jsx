import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

// Browser notification helper
const requestNotificationPermission = async () => {
  if (!('Notification' in window)) return 'unsupported';
  if (Notification.permission === 'granted') return 'granted';
  if (Notification.permission === 'denied') return 'denied';
  const perm = await Notification.requestPermission();
  return perm;
};

const showBrowserNotification = (title, body, tag) => {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  try {
    const notif = new Notification(title, {
      body,
      icon: '/favicon.ico',
      tag: tag || 'stockbud-alert',
      requireInteraction: false,
    });
    notif.onclick = () => { window.focus(); notif.close(); };
    setTimeout(() => notif.close(), 8000);
  } catch (e) { /* Service worker may be needed in some contexts */ }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(sessionStorage.getItem('token'));
  const lastNotifCountRef = useRef(0);

  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
  const API = `${BACKEND_URL}/api`;

  // Poll for new notifications and trigger browser notifications
  const pollNotifications = useCallback(async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${API}/notifications/categorized`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const totalUnread = res.data.total_unread || 0;
      
      // If new unread notifications appeared, show browser notification
      // Only for categories the user has enabled
      if (totalUnread > lastNotifCountRef.current && lastNotifCountRef.current >= 0) {
        let prefs;
        try {
          const saved = localStorage.getItem('stockbud_browser_notif_prefs');
          prefs = saved ? JSON.parse(saved) : { stock: true, order: true, stamp: true, polythene: false, general: false };
        } catch { prefs = { stock: true, order: true, stamp: true, polythene: false, general: false }; }

        const notifications = res.data.notifications || {};
        // Collect only unread from enabled categories
        const enabledUnread = [];
        for (const [cat, notifs] of Object.entries(notifications)) {
          if (prefs[cat]) {
            enabledUnread.push(...(notifs || []).filter(n => !n.read));
          }
        }
        
        if (enabledUnread.length > 0) {
          const sorted = enabledUnread.sort((a, b) =>
            new Date(b.created_at || b.timestamp || 0) - new Date(a.created_at || a.timestamp || 0)
          );
          const latest = sorted[0];
          showBrowserNotification(
            `StockBud: New alert`,
            latest.message || 'New notification',
            `stockbud-${Date.now()}`
          );
        }
      }
      lastNotifCountRef.current = totalUnread;
    } catch (e) { /* ignore polling errors */ }
  }, [token, API]);

  useEffect(() => {
    if (token) {
      // Set default auth header
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      
      // Verify token and get user info
      axios.get(`${API}/auth/me`)
        .then(response => {
          setUser(response.data);
          // Request browser notification permission after login
          requestNotificationPermission();
          // Start polling for notifications
          lastNotifCountRef.current = -1; // skip first notification burst
          setTimeout(() => {
            lastNotifCountRef.current = 0;
            pollNotifications();
          }, 5000);
        })
        .catch(() => {
          logout();
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [token, API]);

  // Set up notification polling interval
  useEffect(() => {
    if (!user || !token) return;
    const interval = setInterval(pollNotifications, 60000);
    return () => clearInterval(interval);
  }, [user, token, pollNotifications]);

  const login = async (username, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, {
        username,
        password
      });

      const { access_token, user: userData } = response.data;
      
      sessionStorage.setItem('token', access_token);
      setToken(access_token);
      setUser(userData);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Request browser notification permission on login
      requestNotificationPermission();
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Login failed' 
      };
    }
  };

  const logout = () => {
    sessionStorage.removeItem('token');
    setToken(null);
    setUser(null);
    delete axios.defaults.headers.common['Authorization'];
  };

  const value = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin',
    isManager: user?.role === 'manager',
    isExecutive: user?.role === 'executive',
    showBrowserNotification,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
