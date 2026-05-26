/* ============================================================
   ThreadVerse V2 — Shop Page JavaScript
   ============================================================ */

let allProducts = [];
let filters = { category: '', gender: '', max_price: '', sort: 'default', search: '' };

// ── FETCH & RENDER PRODUCTS ──
async function fetchProducts() {
  const params = new URLSearchParams();
  if (filters.category)  params.set('category',  filters.category);
  if (filters.gender)    params.set('gender',     filters.gender);
  if (filters.max_price) params.set('max_price',  filters.max_price);
  if (filters.sort && filters.sort !== 'default') params.set('sort', filters.sort);
  if (filters.search)    params.set('search',     filters.search);

  try {
    const res = await fetch(`/api/products?${params}`);
    allProducts = await res.json();
  } catch(e) {
    allProducts = [];
  }

  renderProducts(allProducts);

  const countEl = document.getElementById('product-count');
  if (countEl) countEl.textContent = `${allProducts.length} item${allProducts.length !== 1 ? 's' : ''}`;
}

function getProductImage(p) {
  if (p.image) return p.image;
  return 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=400&auto=format&fit=crop&q=60';
}

function renderProducts(products) {
  const grid = document.getElementById('product-grid');
  if (!grid) return;

  if (!products.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;text-align:center;padding:80px 20px">
        <div style="font-size:3rem;margin-bottom:16px">🔍</div>
        <h3 style="margin-bottom:8px">No products found</h3>
        <p style="color:var(--muted);margin-bottom:24px">Try adjusting your filters or search term</p>
        <button class="btn btn-primary" onclick="clearFilters()">Clear Filters</button>
      </div>`;
    return;
  }

  grid.innerHTML = products.map((p, i) => `
    <div class="product-card fade-in" style="animation-delay:${Math.min(i * 0.05, 0.4)}s">
      <div class="product-card-img">
        <img src="${getProductImage(p)}" alt="${p.name}" loading="lazy"
             onerror="this.src='https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=400&auto=format&fit=crop&q=60'"/>
        <div class="product-card-actions">
          <button class="icon-btn" title="Wishlist" onclick="toggleWishlist(${p.id}, this)">♡</button>
          <a href="/product/${p.id}" class="icon-btn" title="View">👁</a>
        </div>
      </div>
      <div class="product-card-body">
        <div class="product-card-cat">${p.category} · ${p.gender}</div>
        <div class="product-card-name"><a href="/product/${p.id}">${p.name}</a></div>
        <div class="product-card-meta">
          <div class="product-card-price">₹${p.price.toFixed(0)}</div>
          <div class="product-card-rating"><span class="star">★</span> ${p.rating} (${p.reviews})</div>
        </div>
        <button class="product-card-add" onclick="addToCart(${p.id})">+ Add to Cart</button>
      </div>
    </div>
  `).join('');
}

// ── FILTER CONTROLS ──
function setCategory(cat, el) {
  if (filters.category === cat) {
    filters.category = '';
    if (el) el.classList.remove('active');
  } else {
    filters.category = cat;
    document.querySelectorAll('.cat-filter').forEach(b => b.classList.remove('active'));
    if (el) el.classList.add('active');
  }
  fetchProducts();
}

function setGender(g, el) {
  filters.gender = g;
  document.querySelectorAll('.gender-btn').forEach(b => b.classList.remove('active'));
  if (el) el.classList.add('active');
  fetchProducts();
}

function setSort(val) {
  filters.sort = val;
  fetchProducts();
}

function setMaxPrice(val) {
  filters.max_price = val;
  const display = document.getElementById('price-display');
  if (display) {
    if (!val) {
      display.textContent = 'Any price';
    } else {
      const v = parseInt(val);
      if (v <= 1999)       display.textContent = 'Under ₹1,999';
      else if (v <= 3999)  display.textContent = 'Under ₹3,999';
      else if (v <= 5999)  display.textContent = 'Under ₹5,999';
      else if (v <= 7999)  display.textContent = 'Under ₹7,999';
      else if (v <= 9999)  display.textContent = 'Under ₹9,999';
      else if (v <= 11999) display.textContent = 'Under ₹11,999';
      else                 display.textContent = `Under ₹${v.toLocaleString('en-IN')}`;
    }
  }
  fetchProducts();
}

function setSearch(val) {
  filters.search = val;
  fetchProducts();
}

function clearFilters() {
  filters = { category: '', gender: '', max_price: '', sort: 'default', search: '' };
  document.querySelectorAll('.cat-filter, .gender-btn').forEach(b => b.classList.remove('active'));
  const allGenderBtn = document.querySelector('.gender-btn[data-gender=""]');
  if (allGenderBtn) allGenderBtn.classList.add('active');
  const searchEl = document.getElementById('search-input');
  if (searchEl) searchEl.value = '';
  const sortEl = document.getElementById('sort-select');
  if (sortEl) sortEl.value = 'default';
  const priceEl = document.getElementById('price-range');
  if (priceEl) priceEl.value = priceEl.max; // 14999
  const priceDisplay = document.getElementById('price-display');
  if (priceDisplay) priceDisplay.textContent = 'Any price';
  fetchProducts();
}

// ── READ URL PARAMS ──
function readURLParams() {
  const params = new URLSearchParams(window.location.search);
  const cat = params.get('cat') || params.get('category');
  if (cat) {
    filters.category = cat;
    setTimeout(() => {
      const btn = [...document.querySelectorAll('.cat-filter')]
        .find(b => b.textContent.trim().toLowerCase() === cat.toLowerCase());
      if (btn) btn.classList.add('active');
    }, 50);
  }
  const gender = params.get('gender');
  if (gender) filters.gender = gender;
}

// ── INIT ──
document.addEventListener('DOMContentLoaded', () => {
  readURLParams();
  fetchProducts();

  const allGenderBtn = document.querySelector('.gender-btn[data-gender=""]');
  if (allGenderBtn) allGenderBtn.classList.add('active');

  let searchTimer;
  const searchEl = document.getElementById('search-input');
  if (searchEl) {
    searchEl.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => setSearch(searchEl.value.trim()), 300);
    });
  }
});
