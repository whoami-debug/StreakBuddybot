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

// Применяем themeParams как CSS переменные для локальной отладки, если не в Telegram
if (!isTelegramEnv && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.themeParams) {
    const themeParams = window.Telegram.WebApp.themeParams;
    for (const key in themeParams) {
        if (Object.prototype.hasOwnProperty.call(themeParams, key)) {
            document.documentElement.style.setProperty(`--tg-theme-${key.replace(/_/g, '-')}`, themeParams[key]);
            // Для обратной совместимости, если где-то используются старые имена переменных (хотя лучше перейти на новые)
            document.documentElement.style.setProperty(`--${key.replace(/_/g, '-')}`, themeParams[key]); 
        }
    }
    console.log('script.js: Applied emulated themeParams as CSS variables.');
}
// --- Конец кода для эмуляции/дополнения Telegram WebApp ---

console.log('script.js: Script loaded. Environment:', isTelegramEnv ? 'Telegram' : 'Browser/Emulated');
const tg = window.Telegram.WebApp;
tg.expand(); // Expand the Web App to full height

const criticalErrorDiv = document.getElementById('error');
const feedbackDiv = document.getElementById('feedback');
const streakListDiv = document.getElementById('streakList');
const userBalanceSpan = document.getElementById('userBalance'); // Новый элемент для баланса
let currentUserId = null;
let currentUserBalance = 0; // Храним баланс локально

const FREEZE_COST_PER_DAY = 1; // Стоимость заморозки (должна совпадать с серверной)

// Определяем базовый URL для API
const IS_LOCALHOST_DEBUG = window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1' || 
                           window.location.protocol === 'file:';

const API_BASE_URL = IS_LOCALHOST_DEBUG 
    ? 'http://localhost:8080' 
    : 'https://a10c-80-110-47-123.ngrok-free.app'; // Используем новый ngrok URL для удаленного доступа

console.log('script.js: Variables initialized. IS_LOCALHOST_DEBUG:', IS_LOCALHOST_DEBUG, 'API_BASE_URL:', API_BASE_URL);

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
        const response = await fetch(apiUrl, {
            headers: {
                'ngrok-skip-browser-warning': 'true'
            }
        });
        console.log('script.js: Fetch response received:', response);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Не удалось получить детали ошибки от сервера (json parsing failed)" }));
            console.error('script.js: Fetch error - Response not OK. Status:', response.status, 'Error data:', errorData);
            throw new Error(errorData.error || 'Ошибка ' + response.status + ' при загрузке стриков');
        }
        const data = await response.json();
        console.log('script.js: Streaks data from server:', data);
        currentUserBalance = data.balance !== undefined ? data.balance : 0;
        if (userBalanceSpan) {
            userBalanceSpan.textContent = currentUserBalance;
        }
        updateStreaksUI(data.streaks);
    } catch (err) {
        console.error('script.js: Error in fetchStreaks catch block:', err);
        showCriticalError('Не удалось загрузить стрики: ' + err.message);
    }
}

function createStreakCardHTML(streak) {
    console.log('Streak data for card:', streak);
    const safePartnerUsername = streak.partner_username ? streak.partner_username.replace(/'/g, "\\'").replace(/"/g, "&quot;") : '';
    const partnerMention = streak.partner_username ? `@${streak.partner_username}` : `ID: ${streak.partner_id}`;
    const chatLink = streak.partner_username 
        ? `tg://resolve?domain=${streak.partner_username}` 
        : `tg://user?id=${streak.partner_id}`;
    
    let freezeInfoHTML = '';
    if (streak.freeze_end_date) {
        try {
            const freezeEndDate = new Date(streak.freeze_end_date);
            // Проверяем, что дата валидна и что она еще не прошла (или сегодня)
            // Сравниваем только даты, без времени
            const today = new Date(); // Сегодняшняя дата (локальное время клиента)
            today.setHours(0, 0, 0, 0); // Обнуляем время для корректного сравнения с датой из БД (которая тоже без времени)
            
            if (!isNaN(freezeEndDate.getTime()) && freezeEndDate >= today) {
                 freezeInfoHTML = `<div class="freeze-info">❄️ Заморожен до: ${freezeEndDate.toLocaleDateString('ru-RU')}</div>`;
            } else if (!isNaN(freezeEndDate.getTime()) && freezeEndDate < today) {
                // Можно добавить логику, если заморозка истекла, но все еще приходит от сервера
                // Например, если get_active_freeze на сервере не удаляет старые записи сразу
                console.log('script.js: Streak with', streak.partner_username, 'had an expired freeze until', streak.freeze_end_date);
            }
        } catch (e) {
            console.error("Error parsing freeze_end_date:", streak.freeze_end_date, e);
        }
    }

    return (
        '<div class="streak-card" id="streak-card-' + streak.partner_id + '">' +
            '<div class="streak-info">' +
                '<div class="user-pair">Вы и ' + partnerMention + '</div>' +
                '<div class="streak-count">' + streak.streak_count + '🔥</div>' +
            '</div>' +
            freezeInfoHTML +
            '<div class="streak-actions">' +
                // '<button onclick="markToday(' + streak.partner_id + ', \'' + safePartnerUsername + '\')">Продлить стрик</button>' + // Кнопка удалена
                '<a href="' + chatLink + '" class="chat-link-button" target="_blank" rel="noopener noreferrer">Написать</a>' +
                '<button class="freeze-button" onclick="promptFreezeStreak(' + streak.partner_id + ', \'' + safePartnerUsername + '\')">Заморозить (❄️)</button>' + // Новая кнопка
            '</div>' +
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

// async function markToday(partnerId, partnerUsername) { // Функцию пока оставляем, но она не будет вызываться с UI
//     console.log('script.js: markToday called for partnerId:', partnerId, 'partnerUsername:', partnerUsername, 'currentUserId:', currentUserId);
//     if (!currentUserId) {
//         showFeedback("Ошибка: ID пользователя Telegram не определен.", true);
//         return;
//     }
//     showFeedback('Отмечаем стрик с @' + partnerUsername + '...', false); // Initial feedback

//     const apiUrlMark = API_BASE_URL + '/api/webapp/mark_today';
//     console.log('script.js: Attempting to POST to:', apiUrlMark, 'with data:', { user_id: currentUserId, partner_id: partnerId });

//     try {
//         const response = await fetch(apiUrlMark, {
//             method: 'POST',
//             headers: {
//                 'Content-Type': 'application/json',
//                 'ngrok-skip-browser-warning': 'true' // Добавляем заголовок для ngrok
//             },
//             body: JSON.stringify({ user_id: currentUserId, partner_id: partnerId }),
//         });
//         console.log('script.js: Mark today response received:', response);
//         const result = await response.json();
//         console.log('script.js: Mark today result from server:', result);

//         if (!response.ok) {
//             console.error('script.js: Mark today error - Response not OK. Status:', response.status, 'Result data:', result);
//             throw new Error(result.error || 'Ошибка ' + response.status + ' от сервера');
//         }
        
//         showFeedback(result.message || "Действие выполнено.", !result.streak_updated && !result.message.toLowerCase().includes("уже") && !result.message.toLowerCase().includes("сохранена"));

//         const positiveMessages = ["стрик обновлен", "уже подтверждено", "уже было учтено", "ваша отметка сохранена"];
//         if (result.streak_updated || positiveMessages.some(pm => result.message.toLowerCase().includes(pm))) {
//             setTimeout(fetchStreaks, 1000);
//         }

//     } catch (err) {
//         console.error('script.js: Error in markToday catch block:', err);
//          showFeedback('Ошибка с @' + partnerUsername + ': ' + err.message, true);
//     }
// }

async function promptFreezeStreak(partnerId, partnerUsernameSafe) {
    const partnerUsernameDisplay = partnerUsernameSafe.replace(/&quot;/g, '"').replace(/\\'/g, "'");
    console.log('script.js: promptFreezeStreak called for partnerId:', partnerId, 'partnerUsername:', partnerUsernameDisplay);

    const daysToFreezeStr = prompt(`На сколько дней вы хотите заморозить стрик с @${partnerUsernameDisplay}?\nСтоимость: ${FREEZE_COST_PER_DAY} балл(а) за день.\nМаксимум: 30 дней.`);

    if (daysToFreezeStr === null) { // Пользователь нажал "Отмена"
        showFeedback('Заморозка отменена.', false);
        return;
    }

    const daysToFreeze = parseInt(daysToFreezeStr, 10);

    if (isNaN(daysToFreeze) || daysToFreeze <= 0) {
        showFeedback('Неверное количество дней. Пожалуйста, введите положительное число.', true);
        return;
    }
    if (daysToFreeze > 30) {
        showFeedback('Максимальное количество дней для заморозки: 30.', true);
        return;
    }

    const cost = daysToFreeze * FREEZE_COST_PER_DAY;
    if (currentUserBalance < cost) {
        showFeedback(`Недостаточно баллов для заморозки на ${daysToFreeze} дней (нужно ${cost}, у вас ${currentUserBalance}).`, true);
        return;
    }
    
    showFeedback(`Замораживаем стрик с @${partnerUsernameDisplay} на ${daysToFreeze} дней...`, false);

    const apiUrlFreeze = API_BASE_URL + '/api/webapp/freeze_streak';
    console.log('script.js: Attempting to POST to:', apiUrlFreeze, 'with data:', { user_id: currentUserId, partner_id: partnerId, days: daysToFreeze });

    try {
        const response = await fetch(apiUrlFreeze, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({ user_id: currentUserId, partner_id: partnerId, days: daysToFreeze }),
        });
        console.log('script.js: Freeze streak response received:', response);
        const result = await response.json();
        console.log('script.js: Freeze streak result from server:', result);

        if (!response.ok) {
            console.error('script.js: Freeze streak error - Response not OK. Status:', response.status, 'Result data:', result);
            throw new Error(result.error || 'Ошибка ' + response.status + ' от сервера при заморозке');
        }
        
        showFeedback(result.message || "Действие по заморозке выполнено.", !result.success);

        if (result.success) {
            currentUserBalance = result.new_balance !== undefined ? result.new_balance : currentUserBalance - cost; 
             if (userBalanceSpan) {
                userBalanceSpan.textContent = currentUserBalance;
            }
            // Обновляем информацию о заморозке на конкретной карточке или перезагружаем все
            if (result.new_freeze_end_date) {
                updateFreezeInfoOnCard(partnerId, result.new_freeze_end_date);
            } else {
                // Если дата не пришла, или для простоты, можно просто перезапросить все стрики
                setTimeout(fetchStreaks, 1000); 
            }
        }

    } catch (err) {
        console.error('script.js: Error in freezeStreak catch block:', err);
         showFeedback('Ошибка при заморозке с @' + partnerUsernameDisplay + ': ' + err.message, true);
    }
}

// Новая функция для обновления информации о заморозке на карточке
function updateFreezeInfoOnCard(partnerId, freezeDateISO) {
    const cardElement = document.getElementById('streak-card-' + partnerId);
    if (!cardElement) return;

    let freezeInfoDiv = cardElement.querySelector('.freeze-info');
    if (!freezeInfoDiv) { // Если элемента нет, создаем его и вставляем перед .streak-actions
        freezeInfoDiv = document.createElement('div');
        freezeInfoDiv.className = 'freeze-info';
        const actionsDiv = cardElement.querySelector('.streak-actions');
        if (actionsDiv) {
            cardElement.insertBefore(freezeInfoDiv, actionsDiv);
        } else { // На всякий случай, если нет .streak-actions, добавляем в конец
            cardElement.appendChild(freezeInfoDiv);
        }
    }

    if (freezeDateISO) {
        try {
            const freezeEndDate = new Date(freezeDateISO);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            if (!isNaN(freezeEndDate.getTime()) && freezeEndDate >= today) {
                freezeInfoDiv.innerHTML = `❄️ Заморожен до: ${freezeEndDate.toLocaleDateString('ru-RU')}`;
                freezeInfoDiv.style.display = 'block'; // Показываем, если был скрыт
            } else {
                freezeInfoDiv.innerHTML = ''; // Стираем, если дата некорректна или прошла
                freezeInfoDiv.style.display = 'none';
            }
        } catch (e) {
            console.error("Error parsing freeze_end_date for card update:", freezeDateISO, e);
            freezeInfoDiv.innerHTML = '';
            freezeInfoDiv.style.display = 'none';
        }
    } else { // Если пришел null/undefined, значит заморозки нет
        freezeInfoDiv.innerHTML = '';
        freezeInfoDiv.style.display = 'none';
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