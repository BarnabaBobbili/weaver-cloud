import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || '';

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// Request interceptor — attach access token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    const requestUrl = originalRequest?.url || '';
    const shouldSkipRefresh =
      requestUrl.includes('/api/auth/login') ||
      requestUrl.includes('/api/auth/login/mfa') ||
      requestUrl.includes('/api/auth/register') ||
      requestUrl.includes('/api/auth/refresh');

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !shouldSkipRefresh) {
      originalRequest._retry = true;
      try {
        const res = await client.post<{ access_token: string }>('/api/auth/refresh');
        const { access_token } = res.data;
        localStorage.setItem('access_token', access_token);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return client(originalRequest);
      } catch {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default client;
