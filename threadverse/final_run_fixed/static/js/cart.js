/* ============================================================
   ThreadVerse V2 — Cart Page JavaScript
   ============================================================ */

async function updateQty(productId, newQty) {
  if (newQty < 1) {
    removeItem(productId);
    return;
  }
  await updateCartQty(productId, newQty);
  location.reload();
}

async function removeItem(productId) {
  await removeFromCart(productId);
  showToast('Item removed from cart');
  setTimeout(() => location.reload(), 400);
}

async function clearCart() {
  if (!confirm('Are you sure you want to clear your cart?')) return;
  await fetch('/api/cart/clear', { method: 'POST' });
  showToast('Cart cleared');
  setTimeout(() => location.reload(), 400);
}

async function checkout() {
  const name    = document.getElementById('shipping-name')?.value.trim();
  const address = document.getElementById('shipping-address')?.value.trim();
  const city    = document.getElementById('shipping-city')?.value.trim();

  if (!name || !address || !city) {
    showToast('Please fill in all shipping details', 'error');
    return;
  }

  try {
    // ✅ Fixed URL: was /api/checkout, now /api/cart/checkout
    const res = await fetch('/api/cart/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shipping: { name, address, city } })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Order placed! ID: ${data.order_id}`, 'success');
      setTimeout(() => window.location.href = '/orders', 1500);
    } else {
      showToast(data.error || 'Checkout failed', 'error');
    }
  } catch (e) {
    showToast('Something went wrong', 'error');
  }
}
