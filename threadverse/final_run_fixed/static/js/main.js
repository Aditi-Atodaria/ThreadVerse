/* ============================================================
   ThreadVerse V2 — Main JavaScript
   ============================================================ */

// ── CLOUD CART NOTIFICATION ──────────────────────────────────────────────────
function showCartCloud(productName, count) {
  const existing = document.getElementById('tv-cart-cloud');
  if (existing) existing.remove();

  const cloud = document.createElement('div');
  cloud.id = 'tv-cart-cloud';
  cloud.innerHTML = `
    <div class="tv-cloud-inner">
      <span class="tv-cloud-icon">🛍️</span>
      <div class="tv-cloud-text">
        <strong>${productName || 'Item'}</strong>
        <span class="tv-cloud-sub">added · ${count} item${count !== 1 ? 's' : ''} in cart</span>
      </div>
      <a href="/checkout" class="tv-cloud-btn">View Cart</a>
    </div>`;

  if (!document.getElementById('tv-cloud-style')) {
    const s = document.createElement('style');
    s.id = 'tv-cloud-style';
    s.textContent = `
      #tv-cart-cloud {
        position: fixed; bottom: 28px; left: 50%;
        transform: translateX(-50%) translateY(80px);
        z-index: 99999; pointer-events: auto;
        filter: drop-shadow(0 8px 28px rgba(0,0,0,0.16));
        animation: tvCloudUp 0.38s cubic-bezier(0.16,1,0.3,1) forwards,
                   tvCloudOut 0.4s ease 3.6s forwards;
      }
      .tv-cloud-inner {
        display: flex; align-items: center; gap: 0.85rem;
        background: #fff; border-radius: 100px;
        padding: 0.65rem 1rem 0.65rem 0.9rem;
        border: 1.5px solid #e8e8e8;
        white-space: nowrap; max-width: 92vw;
        box-shadow: 0 2px 20px rgba(0,0,0,0.10);
      }
      .tv-cloud-icon { font-size: 1.25rem; flex-shrink: 0; }
      .tv-cloud-text {
        display: flex; flex-direction: column; flex: 1;
        font-family: 'Oswald', sans-serif;
        min-width: 0;
      }
      .tv-cloud-text strong {
        font-size: 0.83rem; font-weight: 500; color: #111;
        overflow: hidden; text-overflow: ellipsis;
        max-width: 180px; display: block;
      }
      .tv-cloud-sub { font-size: 0.7rem; color: #888; font-weight: 300; letter-spacing: 0.02em; }
      .tv-cloud-btn {
        background: #111; color: #fff; text-decoration: none;
        font-family: 'Oswald', sans-serif; font-size: 0.7rem;
        letter-spacing: 0.08em; text-transform: uppercase;
        padding: 0.42rem 0.9rem; border-radius: 100px;
        flex-shrink: 0; transition: background 0.2s;
      }
      .tv-cloud-btn:hover { background: #224292; }
      @keyframes tvCloudUp {
        from { transform: translateX(-50%) translateY(80px); opacity: 0; }
        to   { transform: translateX(-50%) translateY(0);   opacity: 1; }
      }
      @keyframes tvCloudOut {
        from { opacity: 1; transform: translateX(-50%) translateY(0); }
        to   { opacity: 0; transform: translateX(-50%) translateY(16px); }
      }
      @media (max-width: 480px) {
        .tv-cloud-inner { padding: 0.55rem 0.8rem; gap: 0.6rem; }
        .tv-cloud-text strong { max-width: 110px; }
      }`;
    document.head.appendChild(s);
  }

  document.body.appendChild(cloud);
  setTimeout(() => { if (cloud.parentNode) cloud.remove(); }, 4200);
}

// ── LEGACY TOAST ──────────────────────────────────────────────────────────────
function showToast(message, type = 'default') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { success: '✓', error: '✕', default: '💜' };
  toast.innerHTML = `<span>${icons[type] || '💜'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

// ── CART API ──────────────────────────────────────────────────────────────────
async function addToCart(productId, size, productName) {
  try {
    const res = await fetch('/api/cart/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: productId, size })
    });
    const data = await res.json();
    if (data.success) {
      updateCartBadge(data.count);
      const name = productName
        || document.querySelector(`[data-product-id="${productId}"] .product-card-name`)?.textContent
        || document.querySelector('.product-title')?.textContent
        || document.querySelector('h1')?.textContent
        || 'Item';
      showCartCloud(name.trim().slice(0, 40), data.count);
    } else {
      showToast('Failed to add to cart', 'error');
    }
    return data;
  } catch (e) {
    showToast('Failed to add to cart', 'error');
    return {};
  }
}

async function removeFromCart(productId) {
  const res = await fetch('/api/cart/remove', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: productId })
  });
  return res.json();
}

async function updateCartQty(productId, qty) {
  const res = await fetch('/api/cart/update', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: productId, qty })
  });
  return res.json();
}

function updateCartBadge(count) {
  document.querySelectorAll('.cart-badge').forEach(b => {
    b.textContent = count;
    b.style.display = count > 0 ? 'flex' : 'none';
  });
  // Also update hero-nav badge
  document.querySelectorAll('.hero-nav-cart-badge').forEach(b => {
    b.textContent = count;
    b.style.display = count > 0 ? 'flex' : 'none';
  });
}

// ── WISHLIST API ──────────────────────────────────────────────────────────────
async function toggleWishlist(productId, btn) {
  try {
    const res = await fetch('/api/wishlist/toggle', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: productId })
    });
    const data = await res.json();
    if (data.added) {
      showToast('Added to wishlist ♥', 'success');
      if (btn) { btn.classList.add('active'); btn.textContent = '♥'; }
    } else {
      showToast('Removed from wishlist');
      if (btn) { btn.classList.remove('active'); btn.textContent = '♡'; }
      if (window.location.pathname === '/wishlist') setTimeout(() => location.reload(), 600);
    }
    return data;
  } catch (e) { showToast('Something went wrong', 'error'); return {}; }
}

// ── NAV BADGE INIT ────────────────────────────────────────────────────────────
async function initNavBadges() {
  try {
    const res  = await fetch('/api/cart/count');
    const data = await res.json();
    updateCartBadge(data.count || 0);
  } catch(e) {}
}

// ── ACTIVE NAV ────────────────────────────────────────────────────────────────
function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(link => {
    link.classList.toggle('active', link.getAttribute('href') === path);
  });
}

// ── INIT ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initNavBadges();
  setActiveNav();
  document.addEventListener('click', function(e) {
    const menu = document.querySelector('.nav-user-menu');
    const dd   = document.getElementById('user-dropdown');
    if (menu && dd && !menu.contains(e.target)) dd.classList.remove('open');
  });
});
