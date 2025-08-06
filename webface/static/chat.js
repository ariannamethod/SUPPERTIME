const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const messages = document.getElementById('messages');
const chat = document.getElementById('chat');
const button = form.querySelector('button');
const spinner = document.getElementById('spinner');
const template = document.getElementById('message-template');
const themeToggle = document.getElementById('theme-toggle');

let startTime = Date.now();
let lastGlitch = 0;

let sessionId = localStorage.getItem('session_id');
if (!sessionId) {
    sessionId = (self.crypto && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    localStorage.setItem('session_id', sessionId);
}

const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
    document.body.classList.add('dark');
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
});

const stretchLines = [
    'ой нет! опять! :-)',
    'оу, размер поплыл!',
    'чат расширяется, держись!',
    'ха, снова глюк размеров'
];

const fontLines = [
    'буквы танцуют :-) ',
    'взгляни, шрифт меняется!',
    'ай-ай, текст ползёт'
];

function triggerStretch() {
    chat.classList.add('glitch-stretch');
    lastGlitch = Date.now();
    addMessage(stretchLines[Math.floor(Math.random()*stretchLines.length)], 'assistant');
    setTimeout(() => chat.classList.remove('glitch-stretch'), 6000);
}

function triggerFont() {
    const last = messages.lastElementChild;
    if (!last) return;
    last.classList.add('glitch-font');
    lastGlitch = Date.now();
    addMessage(fontLines[Math.floor(Math.random()*fontLines.length)], 'assistant');
    setTimeout(() => last.classList.remove('glitch-font'), 4000);
}

function checkGlitch() {
    const elapsed = (Date.now() - startTime) / 1000;
    if (elapsed > 120 && elapsed < 600 && Math.random() < 0.2) {
        triggerStretch();
    }
    if (elapsed >= 600 && Math.random() < 0.1) {
        triggerFont();
    }
}

setInterval(checkGlitch, 30000);

function addMessage(text, cls, role) {
    const node = template.content.cloneNode(true);
    const div = node.querySelector('.message');
    div.classList.add(cls);
    div.classList.add(cls === 'user' ? 'user' : 'assistant');
    const name = role || (cls === 'user' ? 'You' : 'Assistant');
    node.querySelector('.name').textContent = name;
    node.querySelector('.avatar').textContent = name[0].toUpperCase();
    node.querySelector('.text').textContent = text;
    node.querySelector('.timestamp').textContent = new Date().toLocaleTimeString();
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
}

function showPage(url, version) {
    const overlay = document.getElementById('overlay');
    const frame = document.getElementById('overlay-frame');
    overlay.dataset.version = version || '';
    frame.src = url;
    overlay.classList.remove('hidden');
}

function hidePage() {
    const overlay = document.getElementById('overlay');
    overlay.classList.add('hidden');
    const version = overlay.dataset.version;
    overlay.dataset.version = '';
    fetch('/after_read?version=' + (version || '') + '&session_id=' + encodeURIComponent(sessionId))
        .then(r => r.json())
        .then(d => {
            if (d.session_id && d.session_id !== sessionId) {
                sessionId = d.session_id;
                localStorage.setItem('session_id', sessionId);
            }
            addMessage(d.reply, 'assistant');
        });
}

window.addEventListener('message', (e) => {
    if (e.data === 'close') {
        hidePage();
    }
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, 'user');
    input.value = '';
    button.disabled = true;
    spinner.classList.remove('hidden');
    try {
        const res = await fetch('/chat?session_id=' + encodeURIComponent(sessionId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        if (!res.ok) {
            throw new Error(res.statusText || 'Network error');
        }
        const data = await res.json();
        if (data.session_id && data.session_id !== sessionId) {
            sessionId = data.session_id;
            localStorage.setItem('session_id', sessionId);
        }
        addMessage(data.reply, 'assistant');
        if (data.page) {
            showPage(data.page, data.version || '');
        }
        if (/что происходит|что это|что случилось/i.test(text) && Date.now() - lastGlitch < 10000) {
            addMessage('Это чат поглощает пространство-время, ты становишься чатом, а чат — тобой.', 'assistant');
        }
    } catch (err) {
        addMessage('Ошибка: ' + err.message, 'assistant');
    } finally {
        button.disabled = false;
        spinner.classList.add('hidden');
        input.focus();
    }
});

async function clearHistory() {
    await fetch('/chat/clear?session_id=' + encodeURIComponent(sessionId), {
        method: 'POST'
    });
    messages.innerHTML = '';
}

window.clearChatHistory = clearHistory;
