import axios from 'axios';

type FastApiDetailItem = {
  msg?: string;
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }

  const data = error.response?.data as
    | { detail?: unknown; message?: unknown }
    | undefined;

  if (!data) return fallback;

  if (typeof data.detail === 'string') return data.detail;

  if (Array.isArray(data.detail)) {
    const msgs = data.detail
      .map((item) => (item as FastApiDetailItem)?.msg)
      .filter((msg): msg is string => typeof msg === 'string' && msg.length > 0);
    if (msgs.length > 0) return msgs.join(' | ');
  }

  if (data.detail && typeof data.detail === 'object') {
    const msg = (data.detail as { msg?: unknown }).msg;
    if (typeof msg === 'string' && msg.length > 0) return msg;
  }

  if (typeof data.message === 'string' && data.message.length > 0) {
    return data.message;
  }

  return fallback;
}
