/**
 * Authentication Service
 * Handles user registration, login, token management, and logout
 */

import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token storage keys
const ACCESS_TOKEN_KEY = 'visionguard_access_token';
const REFRESH_TOKEN_KEY = 'visionguard_refresh_token';
const USER_KEY = 'visionguard_user';

// Dedicated client for authenticated calls — no baseURL so requests route
// through the Vite proxy as relative paths (avoids port mismatch issues).
const authAxios = axios.create();

// Raw client with no interceptors (used for refresh to avoid loops)
const rawAxios = axios.create();

class AuthService {
  /**
   * Register a new user
   */
  async register(email, password, fullName) {
    try {
      const response = await axios.post(`${API_URL}/auth/register`, {
        email,
        password,
        full_name: fullName
      });
      
      // Store tokens and user info
      if (response.data.access_token) {
        this.setTokens(response.data.access_token, response.data.refresh_token);
        
        // Fetch and store user info
        await this.fetchCurrentUser();
      }
      
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed'
      };
    }
  }

  /**
   * Login user
   */
  async login(email, password) {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, {
        email,
        password
      });
      
      // Store tokens
      if (response.data.access_token) {
        this.setTokens(response.data.access_token, response.data.refresh_token);
        
        // Fetch and store user info
        await this.fetchCurrentUser();
      }
      
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  }

  /**
   * Logout user
   */
  logout() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = '/login';
  }

  /**
   * Get current user info
   */
  async fetchCurrentUser() {
    try {
      const token = this.getAccessToken();
      if (!token) return null;

      const response = await axios.get(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      localStorage.setItem(USER_KEY, JSON.stringify(response.data));
      return response.data;
    } catch (error) {
      console.error('Failed to fetch user:', error);
      return null;
    }
  }

  /**
   * Refresh access token
   */
  async refreshToken() {
    try {
      const refreshToken = this.getRefreshToken();
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await axios.post(`${API_URL}/auth/refresh`, {
        refresh_token: refreshToken
      });
      
      this.setTokens(response.data.access_token, response.data.refresh_token);
      return response.data.access_token;
    } catch (error) {
      // Refresh failed, logout user
      this.logout();
      throw error;
    }
  }

  /**
   * Store tokens in localStorage
   */
  setTokens(accessToken, refreshToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }

  /**
   * Get access token
   */
  getAccessToken() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  /**
   * Get refresh token
   */
  getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  /**
   * Get current user from localStorage
   */
  getCurrentUser() {
    const userStr = localStorage.getItem(USER_KEY);
    if (userStr) {
      try {
        return JSON.parse(userStr);
      } catch {
        return null;
      }
    }
    return null;
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!this.getAccessToken();
  }

  /**
   * Get axios instance with auth header
   */
  getAuthAxios() {
    return authAxios;
  }
}

// Create singleton instance
const authService = new AuthService();

// Attach interceptors to the authenticated client.
authAxios.interceptors.request.use((config) => {
  const token = authService.getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

authAxios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = authService.getRefreshToken();
        if (!refreshToken) {
          authService.logout();
          return Promise.reject(error);
        }

        const refreshRes = await rawAxios.post('/auth/refresh', {
          refresh_token: refreshToken,
        });

        authService.setTokens(refreshRes.data.access_token, refreshRes.data.refresh_token);

        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${refreshRes.data.access_token}`;
        return authAxios(originalRequest);
      } catch (refreshError) {
        const status = refreshError.response?.status;
        // Only hard-logout on definitive auth failures (4xx), not transient server/network errors
        if (status && status >= 400 && status < 500) {
          authService.logout();
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default authService;
