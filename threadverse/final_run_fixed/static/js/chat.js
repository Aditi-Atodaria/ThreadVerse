/* ============================================================
   ThreadVerse V2 — Chat Page JavaScript
   ============================================================ */

const messagesArea = document.getElementById('messages-area');
const chatInput    = document.getElementById('chat-input');
let chatHistory = [];

function scrollToBottom() {
  messagesArea.scrollTop = messagesArea.scrollHeight;
}

function getProductImage(p) {
  if (p.image) return p.image;
  return 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=400&auto=format&fit=crop&q=60';
}

function renderMessage(role, text, products = [], suggestions = []) {
  const div = document.createElement('div');
  div.className = `message ${role} fade-in`;

  const avatar = role === 'bot'
    ? `<div class="msg-avatar">💜</div>`
    : `<div class="msg-avatar">👤</div>`;

  let productsHTML = '';
  if (products && products.length) {
    productsHTML = `<div class="chat-products">
      ${products.map(p => `
        <div class="chat-product-card">
          <a href="/product/${p.id}">
            <img src="${getProductImage(p)}" alt="${p.name}"
              style="width:100%;height:115px;object-fit:cover;border-radius:10px;margin-bottom:8px;display:block;"
              onerror="this.src='https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=400&auto=format&fit=crop&q=60'"/>
          </a>
          <div class="chat-product-cat">${p.category}</div>
          <div class="chat-product-name">${p.name}</div>
          <div class="chat-product-price">₹${p.price.toFixed(0)}</div>
          <button class="chat-product-btn" onclick="chatAddToCart(${p.id}, this)">+ Cart</button>
          <a href="/product/${p.id}" class="chat-product-view">View →</a>
        </div>
      `).join('')}
    </div>`;
  }

  let suggestionsHTML = '';
  if (suggestions && suggestions.length) {
    suggestionsHTML = `<div class="msg-suggestions">
      ${suggestions.map(s => `<button class="suggestion-chip" onclick="sendSuggestion('${s.replace(/'/g, "\\'")}')">${s}</button>`).join('')}
    </div>`;
  }

  div.innerHTML = `
    ${avatar}
    <div class="msg-content">
      ${text ? `<div class="msg-bubble">${text}</div>` : ''}
      ${productsHTML}
      ${suggestionsHTML}
    </div>
  `;

  messagesArea.appendChild(div);
  scrollToBottom();
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'message bot typing-indicator';
  div.id = 'typing';
  div.innerHTML = `
    <div class="msg-avatar">💜</div>
    <div class="msg-content">
      <div class="msg-bubble">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;
  messagesArea.appendChild(div);
  scrollToBottom();
}

function removeTyping() {
  const t = document.getElementById('typing');
  if (t) t.remove();
}

async function sendMessage(messageText) {
  const text = (messageText || chatInput.value).trim();
  if (!text) return;
  chatInput.value = '';

  renderMessage('user', text);
  showTyping();

  chatHistory.push({ role: 'user', content: text });

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: chatHistory.slice(-20) })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    removeTyping();

    const botText = data.message || '';
    renderMessage('bot', botText, data.products || [], data.suggestions || []);

    let assistantContent = botText;
    if (data.products && data.products.length) {
      assistantContent += ` [Showed products: ${data.products.map(p => p.name).join(', ')}]`;
    }
    chatHistory.push({ role: 'assistant', content: assistantContent });

  } catch (e) {
    removeTyping();
    renderMessage('bot', '❌ Something went wrong — please try again.', [], ['Show all products', 'Dresses', 'Under ₹2,999']);
    chatHistory.pop();
  }
}

function sendSuggestion(text) {
  sendMessage(text);
}

async function chatAddToCart(productId, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  const data = await addToCart(productId);
  if (btn) { btn.textContent = data && data.success ? '✓ Added' : '+ Cart'; btn.disabled = false; }
  if (data && data.success) {
    renderMessage('bot',
      `✅ Added to your cart! You now have ${data.count} item(s). Want to keep browsing?`,
      [],
      ['Show more', 'Under ₹2,999', 'Top rated', 'View cart']
    );
    chatHistory.push({ role: 'assistant', content: `Added product ${productId} to cart. Cart now has ${data.count} items.` });
  }
}

function sidebarSend(message) {
  sendMessage(message);
}

function clearChat() {
  messagesArea.innerHTML = '';
  chatHistory = [];
  greetUser();
}

function greetUser() {
  renderMessage('bot',
    `Hey there! 👋 I'm <strong>ThreadVerse AI</strong>, your personal style assistant.<br><br>
    Tell me what you're looking for — try <em>"floral dress under ₹3,999"</em>, <em>"men's jackets for winter"</em>, or <em>"something for a party"</em>. I understand categories, prices, colors, and occasions!`,
    [],
    ['Show all products', 'New arrivals', 'Dresses under ₹5,999', "Men's jackets", 'Gift ideas', 'Top rated']
  );
}

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.getElementById('send-btn').addEventListener('click', () => sendMessage());

document.addEventListener('DOMContentLoaded', () => {
  greetUser();
  chatInput.focus();
});
