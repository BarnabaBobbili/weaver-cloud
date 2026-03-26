import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';

import { notificationsApi } from '../api';
import type { NotificationItem } from '../types';
import { formatRelativeTime } from '../utils/formatters';

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);

  const load = () => {
    notificationsApi.list().then((res) => {
      setItems(res.data.items);
      setUnread(res.data.unread);
    }).catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  const markRead = async (id: string) => {
    await notificationsApi.markRead(id).catch(() => {});
    load();
  };

  return (
    <div style={{ position: 'relative' }}>
      <button className="header-icon-btn" aria-label="Notifications" onClick={() => setOpen((value) => !value)}>
        <Bell size={16} />
        {unread > 0 && (
          <span style={{
            position: 'absolute',
            top: -2,
            right: -2,
            minWidth: 16,
            height: 16,
            borderRadius: 999,
            background: 'var(--accent-red)',
            color: 'white',
            fontSize: 10,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 4px',
          }}>
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div style={{
          position: 'absolute',
          right: 0,
          top: 36,
          width: 320,
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-subtle)',
          boxShadow: '0 12px 32px rgba(0,0,0,0.22)',
          zIndex: 10,
        }}>
          <div className="row-between" style={{ padding: 14, borderBottom: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>Notifications</span>
            <button className="link-blue" onClick={() => void notificationsApi.markAllRead().then(load).catch(() => {})}>Mark all read</button>
          </div>
          <div style={{ maxHeight: 320, overflowY: 'auto' }}>
            {items.length > 0 ? items.map((item) => (
              <button
                key={item.id}
                onClick={() => void markRead(item.id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: 14,
                  border: 'none',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: item.is_read ? 'transparent' : 'rgba(82,130,224,0.08)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>{item.message}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>{formatRelativeTime(item.created_at)}</div>
              </button>
            )) : (
              <div style={{ padding: 14, fontSize: 12, color: 'var(--text-muted)' }}>No notifications.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
