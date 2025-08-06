const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const messages = document.getElementById('messages');
const template = document.getElementById('message-template');
const themeToggle = document.getElementById('theme-toggle');

function agentClass(name) {
    return 'agent-' + name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
    document.body.classList.add('dark');
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
});

function addMessage(text, cls, role) {
    const node = template.content.cloneNode(true);
    const div = node.querySelector('.message');
    if (cls) div.classList.add(cls);
    const isUser = role === 'You' || cls === 'user';
    div.classList.add(isUser ? 'user' : 'assistant');
    const name = role || (isUser ? 'You' : 'Assistant');
    node.querySelector('.name').textContent = name;
    node.querySelector('.avatar').textContent = name[0].toUpperCase();
    node.querySelector('.text').textContent = text;
    node.querySelector('.timestamp').textContent = new Date().toLocaleTimeString();
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
}

function queueMessages(list) {
    let delay = 0;
    list.forEach(m => {
        delay += 10000 + Math.random() * 10000;
        setTimeout(() => addMessage(m.text, agentClass(m.name), m.name), delay);
    });
}

async function startForum() {
    const res = await fetch('/forum/start');
    const data = await res.json();
    queueMessages(data.messages);
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, 'user', 'You');
    input.value = '';
    const res = await fetch('/forum/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    queueMessages(data.messages);
});

window.addEventListener('DOMContentLoaded', startForum);
