import { logger } from './logger';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export async function apiRequest(path: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });

    // Capture request ID from response for correlation
    const requestId = res.headers.get('X-Request-ID');

    if (res.status === 401) {
      logger.warn('Unauthorized request, redirecting to login', {
        component: 'api',
        endpoint: path,
        requestId,
      } as any);
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
        window.location.href = '/auth/login';
      }
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: 'An error occurred' }));
      const errorMsg = errorData.detail || errorData.message || `Request failed with status ${res.status}`;

      logger.error(`API error: ${options.method || 'GET'} ${path} -> ${res.status}`, new Error(errorMsg), {
        component: 'api',
        endpoint: path,
        statusCode: res.status,
        requestId,
      } as any);

      throw new Error(errorMsg);
    }

    if (res.status === 204) return null;
    return res.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      logger.error('Network error: API unreachable', error, {
        component: 'api',
        endpoint: path,
      } as any);
    }
    throw error;
  }
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

export function setToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', token);
  }
}

export function removeToken(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token');
  }
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
