// ============================================================
// Anonymous Bot — Панель управления
// ============================================================

// Глобальное состояние
const state = {
    currentUserId: null,
    currentMessageId: null,
    chats: [],
    searchQuery: '',
    isLoadingChats: false,
};

// ============================================================
// Утилиты
// ============================================================

function $(id) {
    return document.getElementById(id);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML.replace(/\n/g, '<br>');
}

function formatTime(timestamp) {
    if (!timestamp) return '';

    // SQLite TIMESTAMP DEFAULT CURRENT_TIMESTAMP возвращает UTC-время без TZ.
    // Добавим 'Z', чтобы JS интерпретировал его как UTC, а не как локальное.
    let ts = timestamp;
    if (typeof ts === 'string' && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(ts)) {
        ts = ts.replace(' ', 'T') + 'Z';
    }
    const date = new Date(ts);
    if (isNaN(date.getTime())) return '';

    const now = new Date();
    const diff = now - date;
    const isToday =
        date.getFullYear() === now.getFullYear() &&
        date.getMonth() === now.getMonth() &&
        date.getDate() === now.getDate();

    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const isYesterday =
        date.getFullYear() === yesterday.getFullYear() &&
        date.getMonth() === yesterday.getMonth() &&
        date.getDate() === yesterday.getDate();

    const time = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

    if (isToday) return time;
    if (isYesterday) return `Вчера, ${time}`;
    if (diff < 7 * 86400000) {
        const day = date.toLocaleDateString('ru-RU', { weekday: 'short' });
        return `${day}, ${time}`;
    }
    return date.toLocaleDateString('ru-RU') + ', ' + time;
}

function getInitials(name) {
    if (!name || name === 'N/A') return '?';
    const parts = String(name).trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
}

function colorFromId(id) {
    // Стабильный цвет аватара по ID
    const palette = [
        '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
        '#f97316', '#eab308', '#22c55e', '#10b981',
        '#06b6d4', '#0ea5e9', '#3b82f6', '#a855f7',
    ];
    const hash = Math.abs(Number(id) || 0);
    return palette[hash % palette.length];
}

function getDisplayName(userInfo, fallbackId) {
    if (!userInfo) return `User ${fallbackId}`;
    if (userInfo.full_name && userInfo.full_name !== 'N/A') return userInfo.full_name;
    if (userInfo.first_name && userInfo.first_name !== 'N/A') return userInfo.first_name;
    if (userInfo.username && userInfo.username !== 'N/A') return '@' + userInfo.username;
    return `User ${fallbackId}`;
}

const MEDIA_LABELS = {
    photo: { icon: '🖼', name: 'Фото' },
    video: { icon: '🎥', name: 'Видео' },
    animation: { icon: '🎞', name: 'GIF' },
    document: { icon: '📄', name: 'Документ' },
    audio: { icon: '🎵', name: 'Аудио' },
    voice: { icon: '🎤', name: 'Голосовое' },
    video_note: { icon: '🎬', name: 'Кружок' },
    sticker: { icon: '😀', name: 'Стикер' },
};

function mediaPreviewText(type) {
    const m = MEDIA_LABELS[type];
    return m ? `${m.icon} ${m.name}` : '📎 Медиа';
}

function renderMediaBlock(mediaType, url, options = {}) {
    if (!mediaType) return '';
    const safeUrl = encodeURI(url);
    const m = MEDIA_LABELS[mediaType] || { icon: '📎', name: 'Медиа' };

    switch (mediaType) {
        case 'photo':
        case 'sticker':
            return `<div class="media media-image">
                <img src="${safeUrl}" loading="lazy" alt="${m.name}">
            </div>`;
        case 'animation':
            return `<div class="media media-image">
                <img src="${safeUrl}" loading="lazy" alt="GIF">
            </div>`;
        case 'video':
        case 'video_note':
            return `<div class="media media-video ${mediaType === 'video_note' ? 'is-round' : ''}">
                <video src="${safeUrl}" controls preload="metadata"></video>
            </div>`;
        case 'voice':
        case 'audio':
            return `<div class="media media-audio">
                <span class="media-icon">${m.icon}</span>
                <audio src="${safeUrl}" controls preload="metadata"></audio>
            </div>`;
        case 'document':
        default:
            return `<a class="media media-file" href="${safeUrl}" target="_blank" rel="noopener">
                <span class="media-file-icon">${m.icon}</span>
                <span class="media-file-meta">
                    <span class="media-file-name">${m.name}</span>
                    <span class="media-file-action">Открыть / скачать</span>
                </span>
            </a>`;
    }
}

// ============================================================
// API
// ============================================================

async function api(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
}

// ============================================================
// Загрузка данных
// ============================================================

async function loadStats() {
    try {
        const stats = await api('/api/stats');
        $('total-messages').textContent = stats.total_messages ?? 0;
        $('unanswered-messages').textContent = stats.unanswered_messages ?? 0;
        // Поддерживаем оба имени поля для обратной совместимости
        $('unique-users').textContent =
            stats.unique_users ?? stats.total_users ?? 0;
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

async function loadChats(silent = false) {
    if (state.isLoadingChats) return;
    state.isLoadingChats = true;
    try {
        state.chats = await api('/api/chats');
        renderChats();
        if (!silent) loadStats();
    } catch (error) {
        console.error('Ошибка загрузки чатов:', error);
        if (!silent) {
            $('chats-list').innerHTML =
                '<div class="empty-state"><p>⚠️ Не удалось загрузить чаты</p></div>';
        }
    } finally {
        state.isLoadingChats = false;
    }
}

function renderChats() {
    const list = $('chats-list');
    const q = state.searchQuery.trim().toLowerCase();

    let chats = state.chats;
    if (q) {
        chats = chats.filter((c) => {
            const name = getDisplayName(c.user_info, c.user_id).toLowerCase();
            const username = (c.user_info?.username || '').toLowerCase();
            const idStr = String(c.user_id);
            return name.includes(q) || username.includes(q) || idStr.includes(q);
        });
    }

    if (chats.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">💭</div>
                <p>${q ? 'Ничего не найдено' : 'Пока нет чатов'}</p>
            </div>`;
        return;
    }

    list.innerHTML = '';
    for (const chat of chats) {
        const name = getDisplayName(chat.user_info, chat.user_id);
        const lastMsg =
            chat.messages && chat.messages.length > 0
                ? chat.messages[chat.messages.length - 1]
                : null;

        let preview = '';
        if (lastMsg) {
            const prefix = lastMsg.is_from_admin ? '↩ ' : '';
            let text = (lastMsg.text || '').replace(/\s+/g, ' ').trim();
            if (lastMsg.has_media || lastMsg.media_type) {
                const mediaLabel = mediaPreviewText(lastMsg.media_type);
                text = text ? `${mediaLabel} · ${text}` : mediaLabel;
            }
            if (!text) text = '(пусто)';
            preview =
                prefix +
                (text.length > 60 ? text.slice(0, 60) + '…' : text);
        } else {
            preview = '👋 Запустил бота';
        }

        const displayTime = chat.last_message_time || chat.last_seen;
        const isActive = state.currentUserId === chat.user_id;
        const initials = getInitials(name);
        const avatarColor = colorFromId(chat.user_id);

        const item = document.createElement('div');
        item.className = 'chat-item' + (isActive ? ' active' : '');
        item.innerHTML = `
            <div class="avatar" style="background:${avatarColor}">${initials}</div>
            <div class="chat-item-body">
                <div class="chat-item-row">
                    <span class="chat-item-name">${escapeHtml(name)}</span>
                    <span class="chat-item-time">${formatTime(displayTime)}</span>
                </div>
                <div class="chat-item-row">
                    <span class="chat-item-preview">${escapeHtml(preview)}</span>
                    ${chat.unread_count > 0
                        ? `<span class="badge">${chat.unread_count}</span>`
                        : ''}
                </div>
            </div>`;
        item.addEventListener('click', () => openChat(chat.user_id));
        list.appendChild(item);
    }
}

async function openChat(userId) {
    state.currentUserId = userId;

    document.querySelectorAll('.chat-item').forEach((el) =>
        el.classList.remove('active')
    );
    // Помечаем активный
    renderChats();

    $('welcome-screen').style.display = 'none';
    $('chat-container').style.display = 'flex';

    await loadMessages(userId);
}

async function loadMessages(userId) {
    try {
        const messages = await api(`/api/messages/${userId}`);
        renderMessages(userId, messages);
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
    }
}

function renderMessages(userId, messages) {
    const container = $('messages-container');
    const chatData = state.chats.find((c) => c.user_id === userId);

    // Заголовок чата
    let userInfo = chatData?.user_info;
    if (!userInfo && messages.length > 0) userInfo = messages[0].user_info;

    const name = getDisplayName(userInfo, userId);
    const initials = getInitials(name);
    const color = colorFromId(userId);

    $('chat-user-avatar').textContent = initials;
    $('chat-user-avatar').style.background = color;
    $('chat-user-name').textContent = name;

    let subtitle = `ID: ${userId}`;
    if (userInfo?.username && userInfo.username !== 'N/A') {
        subtitle = `@${userInfo.username} · ${subtitle}`;
    }
    $('chat-user-id').textContent = subtitle;

    container.innerHTML = '';
    state.currentMessageId = null;

    if (!messages || messages.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <p>Сообщений пока нет</p>
                <p class="muted">Можно отправить первое — кнопка «Написать сообщение» выше</p>
            </div>`;
        return;
    }

    // Сохраняем ID последнего сообщения от пользователя без ответа
    let lastUnansweredId = null;

    for (const msg of messages) {
        const isFromAdmin = !!msg.is_from_admin;
        const replies = Array.isArray(msg.replies) ? msg.replies : [];

        if (!isFromAdmin && replies.length === 0) {
            lastUnansweredId = msg.message_id;
        }

        const group = document.createElement('div');
        group.className = 'message-group';

        const bubble = document.createElement('div');
        bubble.className =
            'message-bubble ' + (isFromAdmin ? 'admin-message' : 'user-message');

        const labelIcon = isFromAdmin ? '👨‍💼' : '👤';
        const labelText = isFromAdmin ? 'Администратор' : 'Пользователь';
        const status = isFromAdmin
            ? '<span class="status sent">отправлено</span>'
            : replies.length > 0
                ? '<span class="status answered">отвечено</span>'
                : '<span class="status pending">ожидает ответа</span>';

        const mediaHtml = msg.has_media
            ? renderMediaBlock(
                  msg.media_type,
                  `/api/media/message/${encodeURIComponent(msg.message_id)}`
              )
            : '';

        // Текст: для медиа — caption, для текста — основной текст
        const bodyText = (msg.caption && msg.has_media) ? msg.caption : msg.text;

        bubble.innerHTML = `
            <div class="message-header">
                <span class="message-author">${labelIcon} ${labelText}</span>
                ${status}
            </div>
            ${mediaHtml}
            ${bodyText ? `<div class="message-text">${escapeHtml(bodyText)}</div>` : ''}
            <div class="message-footer">
                <span class="message-id" title="ID сообщения">#${escapeHtml(msg.message_id)}</span>
                <span class="message-time">${formatTime(msg.timestamp)}</span>
            </div>`;
        group.appendChild(bubble);

        // Ответы администратора
        for (const reply of replies) {
            const rb = document.createElement('div');
            rb.className = 'message-bubble admin-message reply';

            const replyMediaHtml = reply.has_media && reply.reply_id != null
                ? renderMediaBlock(
                      reply.media_type,
                      `/api/media/reply/${encodeURIComponent(reply.reply_id)}`
                  )
                : '';
            const replyBody =
                (reply.caption && reply.has_media) ? reply.caption : reply.reply_text;

            rb.innerHTML = `
                <div class="message-header">
                    <span class="message-author">↩ Ответ администратора</span>
                </div>
                ${replyMediaHtml}
                ${replyBody ? `<div class="message-text">${escapeHtml(replyBody)}</div>` : ''}
                <div class="message-footer">
                    <span class="message-time">${formatTime(reply.timestamp)}</span>
                </div>`;
            group.appendChild(rb);
        }

        container.appendChild(group);
    }

    state.currentMessageId = lastUnansweredId;
    updateReplyFormHint();

    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

function updateReplyFormHint() {
    const hint = $('reply-hint');
    if (!hint) return;
    if (state.currentMessageId) {
        hint.textContent = `Ответ будет привязан к сообщению #${state.currentMessageId}`;
        hint.classList.remove('warn');
    } else {
        hint.textContent = 'Нет неотвеченных сообщений — используйте «Написать сообщение»';
        hint.classList.add('warn');
    }
}

// ============================================================
// Действия
// ============================================================

function toggleNewMessageForm() {
    const form = $('new-message-form');
    const input = $('new-message-input');
    const isHidden = form.style.display === 'none' || !form.style.display;

    if (isHidden) {
        form.style.display = 'block';
        setTimeout(() => input.focus(), 50);
    } else {
        form.style.display = 'none';
        input.value = '';
    }
}

async function sendNewMessage() {
    const input = $('new-message-input');
    const text = input.value.trim();
    const btn = $('btn-send-new');

    if (!text) {
        showNotification('Введите текст сообщения', 'error');
        return;
    }
    if (!state.currentUserId) {
        showNotification('Не выбран пользователь', 'error');
        return;
    }

    setLoading(btn, true);
    try {
        const result = await api('/api/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: state.currentUserId,
                message_text: text,
            }),
        });
        if (result.success) {
            input.value = '';
            toggleNewMessageForm();
            showNotification('Сообщение отправлено', 'success');
            await loadMessages(state.currentUserId);
            await loadChats(true);
        } else {
            showNotification('Ошибка: ' + result.error, 'error');
        }
    } catch (error) {
        console.error(error);
        showNotification('Не удалось отправить сообщение', 'error');
    } finally {
        setLoading(btn, false);
    }
}

async function sendReply() {
    const input = $('reply-input');
    const text = input.value.trim();
    const btn = $('btn-send-reply');

    if (!text) {
        showNotification('Введите текст ответа', 'error');
        return;
    }
    if (!state.currentMessageId) {
        showNotification('Нет сообщения для ответа. Используйте «Написать сообщение».', 'error');
        return;
    }

    setLoading(btn, true);
    try {
        const result = await api('/api/send_reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message_id: state.currentMessageId,
                reply_text: text,
            }),
        });
        if (result.success) {
            input.value = '';
            showNotification('Ответ отправлен', 'success');
            await loadMessages(state.currentUserId);
            await loadChats(true);
        } else {
            showNotification('Ошибка: ' + result.error, 'error');
        }
    } catch (error) {
        console.error(error);
        showNotification('Не удалось отправить ответ', 'error');
    } finally {
        setLoading(btn, false);
    }
}

function setLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.classList.toggle('is-loading', loading);
}

// ============================================================
// Уведомления
// ============================================================

function showNotification(message, type = 'info') {
    const note = document.createElement('div');
    note.className = `notification notification-${type}`;
    note.innerHTML = `
        <span class="notification-icon">${
            type === 'success' ? '✅' : type === 'error' ? '⚠️' : 'ℹ️'
        }</span>
        <span>${escapeHtml(message)}</span>`;
    $('notifications').appendChild(note);

    setTimeout(() => {
        note.classList.add('hide');
        setTimeout(() => note.remove(), 300);
    }, 3000);
}

// ============================================================
// Тема
// ============================================================

const THEME_KEY = 'anonbot-theme';

function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const btn = $('theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const prefersDark =
        window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(saved || (prefersDark ? 'dark' : 'light'));
}

function toggleTheme() {
    const cur = document.documentElement.dataset.theme || 'light';
    const next = cur === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
}

// ============================================================
// Инициализация
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();

    $('theme-toggle').addEventListener('click', toggleTheme);
    $('refresh-btn').addEventListener('click', () => loadChats(false));
    $('btn-new-message').addEventListener('click', toggleNewMessageForm);
    $('btn-cancel-new').addEventListener('click', toggleNewMessageForm);
    $('btn-close-new').addEventListener('click', toggleNewMessageForm);
    $('btn-send-new').addEventListener('click', sendNewMessage);
    $('btn-send-reply').addEventListener('click', sendReply);

    const search = $('search-input');
    search.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        renderChats();
    });

    const replyInput = $('reply-input');
    replyInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendReply();
        }
    });

    const newInput = $('new-message-input');
    newInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendNewMessage();
        }
        if (e.key === 'Escape') toggleNewMessageForm();
    });

    loadChats();
    loadStats();

    // Автообновление каждые 10 секунд (тихо)
    setInterval(() => {
        loadChats(true);
        if (state.currentUserId) loadMessages(state.currentUserId);
    }, 10000);
});
