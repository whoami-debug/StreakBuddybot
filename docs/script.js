// --- Начало кода для эмуляции/дополнения Telegram WebApp --- 
// Проверяем, запущено ли приложение внутри Telegram
const isTelegramEnv = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.query_id;

if (!isTelegramEnv) {
    console.warn('Приложение запущено вне Telegram или initDataUnsafe отсутствует. Эмуляция/дополнение Telegram WebApp API для локальной отладки.');
    
    window.Telegram = window.Telegram || {}; // Создаем Telegram, если его нет
    window.Telegram.WebApp = window.Telegram.WebApp || {}; // Создаем WebApp, если его нет

    // Принудительно устанавливаем/дополняем initDataUnsafe и другие необходимые поля
    window.Telegram.WebApp.initDataUnsafe = window.Telegram.WebApp.initDataUnsafe || {};
    window.Telegram.WebApp.initDataUnsafe.user = window.Telegram.WebApp.initDataUnsafe.user || {
        id: 668673256, // <<<=== ПОСТАВЬТЕ СЮДА ВАШ РЕАЛЬНЫЙ TELEGRAM ID для тестов
        first_name: 'Debug',
        last_name: 'User',
        username: 'whoami_debug_test', // Можно использовать ваш ник или тестовый
        language_code: 'ru'
    };
    // Убедимся, что user.id точно есть
    if (!window.Telegram.WebApp.initDataUnsafe.user.id) {
        window.Telegram.WebApp.initDataUnsafe.user.id = 668673256; // <<<=== И СЮДА ВАШ РЕАЛЬНЫЙ ID
        console.log('Принудительно установлен тестовый user.id в эмуляции.');
    }

    window.Telegram.WebApp.initData = window.Telegram.WebApp.initData || `query_id=EMULATED_QUERY_ID&user=${JSON.stringify(window.Telegram.WebApp.initDataUnsafe.user)}&auth_date=${Math.floor(Date.now() / 1000)}&hash=emulated_hash`;

    // Дополняем основные функции, если они отсутствуют
    const webAppDefaults = {
        expand: function() { console.log('Эмуляция: WebApp.expand()'); },
        ready: function() { console.log('Эмуляция: WebApp.ready()'); },
        sendData: function(data) { console.log('Эмуляция: WebApp.sendData()', data); },
        close: function() { console.log('Эмуляция: WebApp.close()'); },
        setHeaderColor: function(color_key) { console.log('Эмуляция: WebApp.setHeaderColor()', color_key); },
        setBackgroundColor: function(color_key) { console.log('Эмуляция: WebApp.setBackgroundColor()', color_key); },
        themeParams: {
            bg_color: '#ffffff', text_color: '#000000', hint_color: '#707070',
            link_color: '#007aff', button_color: '#007aff', button_text_color: '#ffffff',
            secondary_bg_color: "#f0f0f0",
        },
        colorScheme: 'light', version: '6.7',
        MainButton: { /* ... (можно оставить как было или упростить) ... */ isVisible: false, show: function(){}, hide: function(){} },
        BackButton: { /* ... */ isVisible: false, show: function(){}, hide: function(){} },
        HapticFeedback: { impactOccurred: function(s){}, notificationOccurred: function(t){}, selectionChanged: function(){} },
        platform: 'tdesktop',
        isClosingConfirmationEnabled: false,
        enableClosingConfirmation: function() { this.isClosingConfirmationEnabled = true; },
        disableClosingConfirmation: function() { this.isClosingConfirmationEnabled = false; },
    };

    for (const key in webAppDefaults) {
        if (typeof window.Telegram.WebApp[key] === 'undefined') {
            window.Telegram.WebApp[key] = webAppDefaults[key];
        }
    }
    // Убедимся, что MainButton существует и имеет базовые методы, если их нет
    window.Telegram.WebApp.MainButton = window.Telegram.WebApp.MainButton || {isVisible: false, show: function(){}, hide: function(){}};
     // И так далее для других важных объектов, если они используются напрямую
}
// --- Конец кода для эмуляции/дополнения Telegram WebApp ---

console.log('script.js: Script loaded. Environment:', isTelegramEnv ? 'Telegram' : 'Browser/Emulated');
const tg = window.Telegram.WebApp;
tg.expand(); // Expand the Web App to full height

const criticalErrorDiv = document.getElementById('error');
const feedbackDiv = document.getElementById('feedback');
const streakListDiv = document.getElementById('streakList');
let currentUserId = null;

// Определяем базовый URL для API
const IS_LOCALHOST_DEBUG = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:';
const API_BASE_URL = IS_LOCALHOST_DEBUG ? 'http://localhost:8080' : ''; // Если на GitHub Pages, используем относительный путь (предполагая прокси или тот же домен)
                                                                    // Для локального теста с ботом на localhost:8080, API_BASE_URL должен быть 'http://localhost:8080'
                                                                    // Если WebApp на GitHub Pages, а бот на localhost, то CORS должен быть настроен
                                                                    // и здесь должен быть 'http://localhost:8080'

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

    const apiUrl = API_BASE_URL + '/api/webapp/user_streaks?user_id=' + currentUserId;
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

    const apiUrlMark = API_BASE_URL + '/api/webapp/mark_today';
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