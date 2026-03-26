import type { User } from '../types';

type DemoUserRecord = {
  email: string;
  password: string;
  user: User;
};

const DEMO_TIMESTAMP = '2026-01-01T00:00:00.000Z';
const DEMO_ACCESS_TOKEN_PREFIX = 'demo-token:';
const DEMO_REFRESH_TOKEN_PREFIX = 'demo-refresh:';

export const DEMO_AUTH_ENABLED = import.meta.env.VITE_ENABLE_DUMMY_AUTH !== 'false';

const DEMO_USERS: DemoUserRecord[] = [
  {
    email: 'admin@weaver.local',
    password: 'Admin@123',
    user: {
      id: 'demo-admin',
      email: 'admin@weaver.local',
      full_name: 'Demo Admin',
      role: 'admin',
      is_active: true,
      mfa_enabled: false,
      failed_login_attempts: 0,
      created_at: DEMO_TIMESTAMP,
      updated_at: DEMO_TIMESTAMP,
      last_login: 'Demo Session',
    },
  },
  {
    email: 'analyst@weaver.local',
    password: 'Analyst@123',
    user: {
      id: 'demo-analyst',
      email: 'analyst@weaver.local',
      full_name: 'Demo Analyst',
      role: 'analyst',
      is_active: true,
      mfa_enabled: false,
      failed_login_attempts: 0,
      created_at: DEMO_TIMESTAMP,
      updated_at: DEMO_TIMESTAMP,
      last_login: 'Demo Session',
    },
  },
  {
    email: 'viewer@weaver.local',
    password: 'Viewer@123',
    user: {
      id: 'demo-viewer',
      email: 'viewer@weaver.local',
      full_name: 'Demo Viewer',
      role: 'viewer',
      is_active: true,
      mfa_enabled: false,
      failed_login_attempts: 0,
      created_at: DEMO_TIMESTAMP,
      updated_at: DEMO_TIMESTAMP,
      last_login: 'Demo Session',
    },
  },
];

const normalizeEmail = (email: string) => email.trim().toLowerCase();

const cloneUser = (user: User): User => ({ ...user });

export const demoCredentials = DEMO_USERS.map(({ email, password, user }) => ({
  role: user.role,
  email,
  password,
}));

export function getDemoUserByCredentials(email: string, password: string): User | null {
  const match = DEMO_USERS.find(
    (entry) => normalizeEmail(entry.email) === normalizeEmail(email) && entry.password === password,
  );

  return match ? cloneUser(match.user) : null;
}

export function createDemoTokens(email: string): { access_token: string; refresh_token: string } {
  const normalized = normalizeEmail(email);
  return {
    access_token: `${DEMO_ACCESS_TOKEN_PREFIX}${normalized}`,
    refresh_token: `${DEMO_REFRESH_TOKEN_PREFIX}${normalized}`,
  };
}

export function isDemoAccessToken(token: string | null): boolean {
  return Boolean(token && token.startsWith(DEMO_ACCESS_TOKEN_PREFIX));
}

export function getDemoUserByToken(token: string): User | null {
  if (!token.startsWith(DEMO_ACCESS_TOKEN_PREFIX)) return null;
  const email = token.slice(DEMO_ACCESS_TOKEN_PREFIX.length);
  const match = DEMO_USERS.find((entry) => normalizeEmail(entry.email) === normalizeEmail(email));
  return match ? cloneUser(match.user) : null;
}
