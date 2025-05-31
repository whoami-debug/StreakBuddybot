const tg = window.Telegram.WebApp;
tg.expand(); // Expand the Web App to full height

const criticalErrorDiv = document.getElementById('error');
const feedbackDiv = document.getElementById('feedback');
const streakListDiv = document.getElementById('streakList');
let currentUserId = null;

function showFeedback(message, isError = false) {
    feedbackDiv.textContent = message;
    feedbackDiv.className = 'feedback-message'; // Reset classes
    if (isError) {
        feedbackDiv.classList.add('feedback-error');
    } else {
        feedbackDiv.classList.add('feedback-success');
    }
    feedbackDiv.style.display = 'block';
    // Automatically hide after 5 seconds
    setTimeout(() => {
        feedbackDiv.style.display = 'none';
    }, 5000);
}

function showCriticalError(message) {
    criticalErrorDiv.textContent = message;
    criticalErrorDiv.style.display = 'block';
    streakListDiv.innerHTML = ''; // Clear loading/list
}

async function fetchStreaks() {
    if (!currentUserId) {
        showCriticalError("Ошибка: ID пользователя Telegram не определен.");
        return;
    }
    streakListDiv.innerHTML = '<div class="loading">Загрузка стриков...</div>';
    criticalErrorDiv.style.display = 'none'; // Hide critical error if shown before

    try {
        const response = await fetch('/api/webapp/user_streaks?user_id=' + currentUserId);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Не удалось получить детали ошибки от сервера" }));
            throw new Error(errorData.error || 'Ошибка ' + response.status + ' при загрузке стриков');
        }
        const data = await response.json();
        updateStreaksUI(data.streaks);
    } catch (err) {
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
    if (!currentUserId) {
        showFeedback("Ошибка: ID пользователя Telegram не определен.", true);
        return;
    }
    showFeedback('Отмечаем стрик с @' + partnerUsername + '...', false); // Initial feedback

    try {
        const response = await fetch('/api/webapp/mark_today', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUserId, partner_id: partnerId }),
        });
        
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Ошибка ' + response.status + ' от сервера');
        }
        
        showFeedback(result.message || "Действие выполнено.", !result.streak_updated && !result.message.toLowerCase().includes("уже") && !result.message.toLowerCase().includes("сохранена"));

        const positiveMessages = ["стрик обновлен", "уже подтверждено", "уже было учтено", "ваша отметка сохранена"];
        if (result.streak_updated || positiveMessages.some(pm => result.message.toLowerCase().includes(pm))) {
            setTimeout(fetchStreaks, 1000); // Refresh streaks after a short delay to let user read message
        }

    } catch (err) {
         showFeedback('Ошибка с @' + partnerUsername + ': ' + err.message, true);
    }
}

// Initialize the Web App
if (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) {
    currentUserId = tg.initDataUnsafe.user.id;
    fetchStreaks();
} else {
    showCriticalError("Ошибка: Не удалось получить данные пользователя Telegram. Пожалуйста, убедитесь, что веб-приложение открыто через Telegram бота.");
}

// Optional: Set theme parameters based on Telegram theme
// tg.setHeaderColor('secondary_bg_color'); // Example
// tg.setBackgroundColor('bg_color'); // Example 