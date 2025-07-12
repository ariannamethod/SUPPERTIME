const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const messages = document.getElementById('messages');
const chat = document.getElementById('chat');

let startTime = Date.now();
let lastGlitch = 0;

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

function addMessage(text, cls) {
    const div = document.createElement('div');
    div.className = 'message ' + cls;
    div.textContent = text;
    messages.appendChild(div);
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
    fetch('/after_read?version=' + (version || ''))
        .then(r => r.json())
        .then(d => addMessage(d.reply, 'assistant'));
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
    const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    addMessage(data.reply, 'assistant');
    if (data.page) {
        showPage(data.page, data.version || '');
    }
    if (/что происходит|что это|что случилось/i.test(text) && Date.now() - lastGlitch < 10000) {
        addMessage('Это чат поглощает пространство-время, ты становишься чатом, а чат — тобой.', 'assistant');
    }
});
