console.log('script.js: Script loaded');
const tg = window.Telegram.WebApp;
tg.expand(); // Expand the Web App to full height

const criticalErrorDiv = document.getElementById('error');
const feedbackDiv = document.getElementById('feedback');
const streakListDiv = document.getElementById('streakList');
let currentUserId = null;

console.log('script.js: Variables initialized');

function showFeedback(message, isError = false) {
    console.log('script.js: showFeedback called with:', message, 'isError:', isError);
    feedbackDiv.textContent = message;
    feedbackDiv.className = 'feedback-message'; // Reset classes
    if (isError) {
        feedbackDiv.classList.add('feedback-error');
    } else {
        feedbackDiv.classList.add('feedback-success');
    }
    feedbackDiv.style.display = 'block';
    setTimeout(() => {
        feedbackDiv.style.display = 'none';
    }, 5000);
}

function showCriticalError(message) {
    console.error('script.js: showCriticalError called with:', message);
    criticalErrorDiv.textContent = message;
    criticalErrorDiv.style.display = 'block';
    streakListDiv.innerHTML = '';
}

async function fetchStreaks() {
    console.log('script.js: fetchStreaks called. currentUserId:', currentUserId);
    if (!currentUserId) {
        showCriticalError("Ошибка: ID пользователя Telegram не определен.");
        return;
    }
    streakListDiv.innerHTML = '<div class="loading">Загрузка стриков...</div>';
    criticalErrorDiv.style.display = 'none';

    const apiUrl = '/api/webapp/user_streaks?user_id=' + currentUserId;
    console.log('script.js: Attempting to fetch from:', apiUrl);

    try {
        const response = await fetch(apiUrl);
        console.log('script.js: Fetch response received:', response);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Не удалось получить детали ошибки от сервера (json parsing failed)" }));
            console.error('script.js: Fetch error - Response not OK. Status:', response.status, 'Error data:', errorData);
            throw new Error(errorData.error || 'Ошибка ' + response.status + ' при загрузке стриков');
        }
        const data = await response.json();
        console.log('script.js: Streaks data from server:', data);
        updateStreaksUI(data.streaks);
    } catch (err) {
        console.error('script.js: Error in fetchStreaks catch block:', err);
        showCriticalError('Не удалось загрузить стрики: ' + err.message);
    }
}

function createStreakCardHTML(streak) {
    const safePartnerUsername = streak.partner_username.replace(/'/g, "\\'").replace(/"/g, "&quot;");
    return (
        '<div class="streak-card">' +
            '<div class="streak-info">' +
                '<div class="user-pair">Вы и @' + streak.partner_username + '</div>' +
                '<div class="streak-count">' + streak.streak_count + '🔥</div>' +
            '</div>' +
            '<button onclick="markToday(' + streak.partner_id + ', \'' + safePartnerUsername + '\')">Продлить стрик сегодня</button>' +
        '</div>'
    );
}

function updateStreaksUI(streaks) {
    console.log('script.js: updateStreaksUI called with streaks:', streaks);
    if (streaks && streaks.length > 0) {
        streakListDiv.innerHTML = streaks.map(createStreakCardHTML).join('');
    } else {
        streakListDiv.innerHTML = (
            '<div class="empty-state">' +
                '<h2>У вас пока нет стриков</h2>' +
                '<p>Чтобы начать стрик, начните общаться с кем-нибудь в Telegram, где добавлен бот, или попросите друга добавить вас через команду /chat в личном чате с ботом.</p>' +
            '</div>'
        );
    }
}

async function markToday(partnerId, partnerUsername) {
    console.log('script.js: markToday called for partnerId:', partnerId, 'partnerUsername:', partnerUsername, 'currentUserId:', currentUserId);
    if (!currentUserId) {
        showFeedback("Ошибка: ID пользователя Telegram не определен.", true);
        return;
    }
    showFeedback('Отмечаем стрик с @' + partnerUsername + '...', false); // Initial feedback

    const apiUrlMark = '/api/webapp/mark_today';
    console.log('script.js: Attempting to POST to:', apiUrlMark, 'with data:', { user_id: currentUserId, partner_id: partnerId });

    try {
        const response = await fetch(apiUrlMark, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUserId, partner_id: partnerId }),
        });
        console.log('script.js: Mark today response received:', response);
        const result = await response.json();
        console.log('script.js: Mark today result from server:', result);

        if (!response.ok) {
            console.error('script.js: Mark today error - Response not OK. Status:', response.status, 'Result data:', result);
            throw new Error(result.error || 'Ошибка ' + response.status + ' от сервера');
        }
        
        showFeedback(result.message || "Действие выполнено.", !result.streak_updated && !result.message.toLowerCase().includes("уже") && !result.message.toLowerCase().includes("сохранена"));

        const positiveMessages = ["стрик обновлен", "уже подтверждено", "уже было учтено", "ваша отметка сохранена"];
        if (result.streak_updated || positiveMessages.some(pm => result.message.toLowerCase().includes(pm))) {
            setTimeout(fetchStreaks, 1000);
        }

    } catch (err) {
        console.error('script.js: Error in markToday catch block:', err);
         showFeedback('Ошибка с @' + partnerUsername + ': ' + err.message, true);
    }
}

console.log('script.js: Functions defined. Initializing Web App...');
// Initialize the Web App
if (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) {
    currentUserId = tg.initDataUnsafe.user.id;
    console.log('script.js: Telegram user data found. currentUserId:', currentUserId, 'Calling fetchStreaks().');
    fetchStreaks();
} else {
    console.error('script.js: Telegram user data NOT found or incomplete. tg.initDataUnsafe:', tg.initDataUnsafe);
    showCriticalError("Ошибка: Не удалось получить данные пользователя Telegram. Пожалуйста, убедитесь, что веб-приложение открыто через Telegram бота.");
}

console.log('script.js: Script execution finished.');

// Optional: Set theme parameters based on Telegram theme
// tg.setHeaderColor('secondary_bg_color'); // Example
// tg.setBackgroundColor('bg_color'); // Example 