const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const messages = document.getElementById('messages');

function agentClass(name) {
    return 'agent-' + name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

function addMessage(text, cls, name) {
    const div = document.createElement('div');
    div.className = 'message ' + cls;
    if (name) {
        const avatar = document.createElement('span');
        avatar.className = 'avatar';
        avatar.textContent = name[0];
        div.appendChild(avatar);

        const nameSpan = document.createElement('span');
        nameSpan.className = 'name';
        nameSpan.textContent = name;
        div.appendChild(nameSpan);

        div.appendChild(document.createTextNode(': ' + text));
    } else {
        div.textContent = text;
    }
    messages.appendChild(div);
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
    addMessage(text, 'user');
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
