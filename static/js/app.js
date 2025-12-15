// Глобальные переменные
let currentUserId = null;
let currentMessageId = null;
let chatsData = [];

// Загрузка статистики
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        document.getElementById('total-messages').textContent = stats.total_messages;
        document.getElementById('unanswered-messages').textContent = stats.unanswered_messages;
        document.getElementById('unique-users').textContent = stats.unique_users;
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

// Загрузка списка чатов
async function loadChats() {
    try {
        const response = await fetch('/api/chats');
        chatsData = await response.json();
        
        const chatsList = document.getElementById('chats-list');
        
        if (chatsData.length === 0) {
            chatsList.innerHTML = '<div class="loading">Нет сообщений</div>';
            return;
        }
        
        chatsList.innerHTML = '';
        
        chatsData.forEach(chat => {
            const chatItem = document.createElement('div');
            chatItem.className = 'chat-item';
            if (currentUserId === chat.user_id) {
                chatItem.classList.add('active');
            }
            
            const userName = chat.user_info.full_name !== 'N/A'
                ? chat.user_info.full_name
                : `User ${chat.user_id}`;

            const lastMessage = chat.messages && chat.messages.length > 0 ? chat.messages[chat.messages.length - 1] : null;
            const messagePreview = lastMessage ? lastMessage.text.substring(0, 50) : '👋 Нажал /start';

            // Определяем время для отображения
            const displayTime = chat.last_message_time || chat.last_seen;

            chatItem.innerHTML = `
                <div class="chat-item-header">
                    <span class="chat-user-name">${userName}</span>
                    ${chat.unread_count > 0 ? `<span class="chat-badge">${chat.unread_count}</span>` : ''}
                </div>
                <div class="chat-preview">${messagePreview}${lastMessage && lastMessage.text.length > 50 ? '...' : ''}</div>
                <div class="chat-time">${formatTime(displayTime)}</div>
            `;
            
            chatItem.onclick = function() { openChat(chat.user_id, this); };
            chatsList.appendChild(chatItem);
        });
        
        loadStats();
    } catch (error) {
        console.error('Ошибка загрузки чатов:', error);
    }
}

// Открыть чат с пользователем
async function openChat(userId, clickedElement) {
    currentUserId = userId;

    // Обновляем активный чат в списке
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    if (clickedElement) {
        clickedElement.classList.add('active');
    }

    // Скрываем приветственный экран
    document.getElementById('welcome-screen').style.display = 'none';
    document.getElementById('chat-container').style.display = 'flex';

    // Загружаем сообщения
    await loadMessages(userId);
}

// Загрузка сообщений пользователя
async function loadMessages(userId) {
    try {
        const response = await fetch(`/api/messages/${userId}`);
        const messages = await response.json();

        const messagesContainer = document.getElementById('messages-container');
        const chatUserName = document.getElementById('chat-user-name');
        const chatUserId = document.getElementById('chat-user-id');

        // Находим информацию о пользователе из chatsData
        const chatData = chatsData.find(chat => chat.user_id === userId);

        // Обновляем заголовок
        if (chatData) {
            const userName = chatData.user_info.full_name !== 'N/A'
                ? chatData.user_info.full_name
                : `User ${userId}`;
            chatUserName.textContent = userName;
            chatUserId.textContent = `ID: ${userId}`;
        } else if (messages.length > 0) {
            const userInfo = messages[0].user_info;
            const userName = userInfo.full_name !== 'N/A'
                ? userInfo.full_name
                : `User ${userId}`;
            chatUserName.textContent = userName;
            chatUserId.textContent = `ID: ${userId}`;
        }

        // Очищаем контейнер
        messagesContainer.innerHTML = '';

        // Если нет сообщений, показываем информацию
        if (messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="no-messages">
                    <p>📭 Пользователь еще не отправлял сообщений</p>
                    <p style="color: #888; font-size: 14px;">Вы можете отправить первое сообщение, нажав кнопку "✉️ Написать сообщение"</p>
                </div>
            `;
            return;
        }

        // Отображаем сообщения
        messages.forEach(message => {
            const messageGroup = document.createElement('div');
            messageGroup.className = 'message-group';
            
            // Сообщение пользователя
            const userBubble = document.createElement('div');
            userBubble.className = 'message-bubble user-message';
            userBubble.innerHTML = `
                <div class="message-header">
                    <span>👤 Пользователь</span>
                    <span>ID: ${message.message_id}</span>
                </div>
                <div class="message-text">${escapeHtml(message.text)}</div>
                <div class="message-time">${formatTime(message.timestamp)}</div>
            `;
            messageGroup.appendChild(userBubble);
            
            // Ответ администратора (если есть)
            if (message.admin_reply) {
                const adminBubble = document.createElement('div');
                adminBubble.className = 'message-bubble admin-message';
                adminBubble.innerHTML = `
                    <div class="message-header">
                        <span>👨‍💼 Администратор</span>
                    </div>
                    <div class="message-text">${escapeHtml(message.admin_reply)}</div>
                    <div class="message-time">${formatTime(message.admin_reply_timestamp)}</div>
                `;
                messageGroup.appendChild(adminBubble);
            } else {
                // Сохраняем ID последнего неотвеченного сообщения
                currentMessageId = message.message_id;
            }
            
            messagesContainer.appendChild(messageGroup);
        });
        
        // Прокручиваем вниз
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
    }
}

// Переключение формы нового сообщения
function toggleNewMessageForm() {
    const form = document.getElementById('new-message-form');
    const input = document.getElementById('new-message-input');

    if (form.style.display === 'none') {
        form.style.display = 'block';
        input.focus();
    } else {
        form.style.display = 'none';
        input.value = '';
    }
}

// Отправка нового сообщения пользователю
async function sendNewMessage() {
    const messageInput = document.getElementById('new-message-input');
    const messageText = messageInput.value.trim();

    if (!messageText) {
        alert('Введите текст сообщения');
        return;
    }

    if (!currentUserId) {
        alert('Не выбран пользователь');
        return;
    }

    try {
        const response = await fetch('/api/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: currentUserId,
                message_text: messageText
            })
        });

        const result = await response.json();

        if (result.success) {
            // Очищаем поле ввода и скрываем форму
            messageInput.value = '';
            toggleNewMessageForm();

            // Показываем уведомление
            showNotification('✅ Сообщение отправлено!', 'success');
        } else {
            showNotification('❌ Ошибка: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Ошибка отправки сообщения:', error);
        showNotification('❌ Ошибка отправки сообщения', 'error');
    }
}

// Отправка ответа
async function sendReply() {
    const replyInput = document.getElementById('reply-input');
    const replyText = replyInput.value.trim();

    if (!replyText) {
        alert('Введите текст ответа');
        return;
    }

    if (!currentMessageId) {
        alert('Не выбрано сообщение для ответа');
        return;
    }

    try {
        const response = await fetch('/api/send_reply', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message_id: currentMessageId,
                reply_text: replyText
            })
        });

        const result = await response.json();

        if (result.success) {
            // Очищаем поле ввода
            replyInput.value = '';

            // Перезагружаем сообщения
            await loadMessages(currentUserId);

            // Перезагружаем список чатов
            await loadChats();

            // Показываем уведомление
            showNotification('✅ Ответ отправлен!', 'success');
        } else {
            showNotification('❌ Ошибка: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Ошибка отправки ответа:', error);
        showNotification('❌ Ошибка отправки ответа', 'error');
    }
}

// Форматирование времени
function formatTime(timestamp) {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // Если сегодня
    if (diff < 86400000 && date.getDate() === now.getDate()) {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }

    // Если вчера
    if (diff < 172800000 && date.getDate() === now.getDate() - 1) {
        return 'Вчера ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }

    // Иначе полная дата
    return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Показать уведомление
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        background: ${type === 'success' ? '#4caf50' : '#f44336'};
        color: white;
        border-radius: 10px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    // Удаляем через 3 секунды
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Автообновление каждые 10 секунд
setInterval(() => {
    loadChats();
    if (currentUserId) {
        loadMessages(currentUserId);
    }
}, 10000);

// Обработка Enter в поле ввода
document.addEventListener('DOMContentLoaded', () => {
    const replyInput = document.getElementById('reply-input');

    replyInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendReply();
        }
    });

    // Загружаем данные при старте
    loadChats();
    loadStats();
});

// Добавляем CSS анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

