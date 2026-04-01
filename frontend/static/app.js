async function fetchCart(ownerId) {
  const resp = await fetch(`/api/cart?ownerId=${ownerId}`);
  if (!resp.ok) throw new Error("Failed to fetch cart");
  return await resp.json();
}

async function addToCart(productId, explicitQty) {
  const ownerEl = document.getElementById("ownerId");
  const ownerId = ownerEl ? ownerEl.value : (localStorage.getItem("ownerId") || "guest_default");
  
  let qty = 1;
  const qtyInput = document.getElementById(`qty-${productId}`);
  if (explicitQty !== undefined) {
    qty = explicitQty;
  } else if (qtyInput) {
    qty = parseInt(qtyInput.value) || 1;
  }

  try {
    const resp = await fetch(`/cart/items?ownerId=${ownerId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productId, quantity: qty })
    });
    const result = await resp.json();
    if (!resp.ok) {
        alert("Error: " + (result.detail || "Unknown error"));
        return;
    }
    alert(`Added ${qty} of ${productId} to cart!`);
    loadCart(); // Refresh if on the same page
  } catch (err) {
    console.error(err);
    alert("System error adding to cart");
  }
}

async function updateQuantity(productId, qty) {
  const ownerId = document.getElementById("ownerId").value;
  try {
    const resp = await fetch(`/cart/items/${productId}?ownerId=${ownerId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity: qty })
    });
    if (!resp.ok) {
        const result = await resp.json();
        alert("Error: " + (result.detail || "Unknown error"));
    }
    loadCart();
  } catch (err) {
    console.error(err);
    alert("System error updating quantity");
  }
}

async function removeFromCart(productId) {
  const ownerId = document.getElementById("ownerId").value;
  try {
    const resp = await fetch(`/cart/items/${productId}?ownerId=${ownerId}`, {
      method: "DELETE"
    });
    if (!resp.ok) {
        const result = await resp.json();
        alert("Error: " + (result.detail || "Unknown error"));
    }
    loadCart();
  } catch (err) {
    console.error(err);
    alert("System error removing from cart");
  }
}

async function doCheckout() {
  const ownerEl = document.getElementById("ownerId");
  const ownerId = ownerEl ? ownerEl.value : (localStorage.getItem("ownerId") || "guest_default");
  const codesInput = document.getElementById("codes");
  const codes = codesInput ? codesInput.value.split(",").map(c => c.trim()).filter(c => c) : [];
  
  const resultEl = document.getElementById("checkout-result");
  if (resultEl) resultEl.innerHTML = `<p class="badge badge-info">Processing checkout...</p>`;

  try {
    const resp = await fetch(`/api/cart/checkout?ownerId=${ownerId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ discountCodes: codes })
    });
    const result = await resp.json();
    
    if (!resp.ok) {
        if (resultEl) resultEl.innerHTML = `<div class="pricing-summary"><p class="badge badge-danger">Checkout Failed: ${result.detail || 'Unknown Error'}</p></div>`;
        return;
    }

    if (resultEl) {
        resultEl.innerHTML = `<div class="pricing-summary">
            <h4>Checkout Result: ${result.canProceedToPayment ? '<span class="badge badge-success">READY TO PAY</span>' : '<span class="badge badge-danger">ADJUSTMENT NEEDED</span>'}</h4>
            <div class="pricing-row"><span>Subtotal</span><span>$${result.pricing.subtotal.amount.toFixed(2)}</span></div>
            <div class="pricing-row"><span>Discount</span><span>-$${result.pricing.discount.amount.toFixed(2)}</span></div>
            <div class="pricing-row"><span>Tax</span><span>$${result.pricing.tax.amount.toFixed(2)}</span></div>
            <div class="pricing-row"><span>Shipping</span><span>$${result.pricing.shipping.amount.toFixed(2)}</span></div>
            <div class="pricing-row total"><span>Grand Total</span><span>$${result.pricing.grandTotal.amount.toFixed(2)}</span></div>
            ${result.itemErrors.length ? `<h5>Action Required:</h5><ul>${result.itemErrors.map(e => `<li style="color:var(--danger)">${e.productId}: ${e.message}</li>`).join("")}</ul>` : ""}
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 1rem;">Order Reference: ${result.cartId} | Version: ${result.cartVersion}</p>
            <p style="font-size: 0.8rem; color: var(--text-muted);">Priced at: ${new Date(result.pricedAt).toLocaleString()}</p>
        </div>`;
    }
  } catch (err) {
    console.error(err);
    if (resultEl) resultEl.innerHTML = `<p class="badge badge-danger">System Error: Could not connect to checkout service.</p>`;
  }
}

async function loadCart() {
  const ownerEl = document.getElementById("ownerId");
  if (ownerEl) {
    localStorage.setItem("ownerId", ownerEl.value);
  }
  const ownerId = ownerEl ? ownerEl.value : (localStorage.getItem("ownerId") || "guest_default");
  
  try {
    const cart = await fetchCart(ownerId);
    renderCart(cart);
  } catch (err) {
    console.error(err);
    const container = document.getElementById("cart-items");
    if (container) container.innerHTML = `<p class="badge badge-danger">Failed to load cart</p>`;
  }
}

// Initial setup to load ownerId from storage
window.addEventListener("DOMContentLoaded", () => {
    const ownerEl = document.getElementById("ownerId");
    if (ownerEl) {
        const stored = localStorage.getItem("ownerId");
        if (stored) ownerEl.value = stored;
    }
});

function renderCart(cart) {
  const container = document.getElementById("cart-items");
  const pricingContainer = document.getElementById("pricing");
  const aiContainer = document.getElementById("ai-block");

  if (!container) return; // Not on cart page

  if (cart.items.length === 0) {
    container.innerHTML = `<div class="card"><p>Your cart is empty.</p></div>`;
    if (pricingContainer) pricingContainer.innerHTML = "";
    if (aiContainer) aiContainer.innerHTML = "";
    return;
  }

  container.innerHTML = cart.items.map(item => {
    const upsell = cart.ai ? cart.ai.upsell.find(u => u.baseProductId === item.productId) : null;
    return `
    <div class="cart-item">
      <img src="${item.imageUrl || 'https://via.placeholder.com/64'}" alt="${item.name}">
      <div>
        <h4>${item.name}</h4>
        <p class="stock">Price: $${item.unitPrice.amount.toFixed(2)} | In Stock: ${item.inStock ? '<span class="badge badge-success">YES</span>' : '<span class="badge badge-danger">NO</span>'}</p>
        ${upsell ? `
            <div class="upsell-card" style="font-size: 0.8rem; margin-top: 0.5rem; border-color: var(--accent); padding: 0.5rem;">
                <div style="color: var(--accent);">✦ Recommended Upgrade: <strong>${upsell.suggestedProductId}</strong></div>
                <div style="font-weight: 600;">+$${upsell.priceDelta.amount.toFixed(2)} for better tier</div>
                <button class="secondary-btn" style="padding: 2px 8px; font-size: 0.75rem; margin-top: 0.3rem;" 
                    onclick="removeFromCart('${item.productId}'); addToCart('${upsell.suggestedProductId}', ${item.quantity});">
                    Swap to Premium
                </button>
            </div>` : ""}
      </div>
      <div>
        <label>Qty <input type="number" min="0" value="${item.quantity}" onchange="updateQuantity('${item.productId}', this.value)"></label>
      </div>
      <div>
        <strong>$${item.lineTotal.amount.toFixed(2)}</strong>
      </div>
      <button class="secondary-btn" onclick="removeFromCart('${item.productId}')">Remove</button>
    </div>
  `}).join("");

  if (pricingContainer) {
    pricingContainer.innerHTML = `
      <div class="pricing-summary">
        <div class="pricing-row"><span>Subtotal</span><span>$${cart.pricing.subtotal.amount.toFixed(2)}</span></div>
        <div class="pricing-row"><span>Discount</span><span>-$${cart.pricing.discount.amount.toFixed(2)}</span></div>
        <div class="pricing-row"><span>Tax</span><span>$${cart.pricing.tax.amount.toFixed(2)}</span></div>
        <div class="pricing-row"><span>Shipping</span><span>$${cart.pricing.shipping.amount.toFixed(2)}</span></div>
        <div class="pricing-row total"><span>Grand Total</span><span>$${cart.pricing.grandTotal.amount.toFixed(2)}</span></div>
        ${cart.pricing.appliedDiscountCodes.map(c => `<span class="badge badge-info">${c}</span>`).join(" ")}
      </div>
    `;
  }

  if (aiContainer && cart.ai) {
    let aiHtml = "";
    
    // Price Sensitivity
    const sens = cart.ai.priceSensitivity;
    if (sens) {
        aiHtml += `<div class="ai-section">
            <h3>Purchase Likelihood</h3>
            <p>Score: <strong>${(sens.buyProbability * 100).toFixed(1)}%</strong> | Segment: <span class="badge badge-info">${sens.segment}</span></p>
        </div>`;
    }

    // Upsell
    if (cart.ai.upsell.length > 0) {
        aiHtml += `<div class="ai-section">
            <h3>Premium Upgrades</h3>
            ${cart.ai.upsell.map(u => `
                <div class="upsell-card">
                    <div>Suggest upgrading ${u.baseProductId} to <strong>${u.suggestedProductId}</strong></div>
                    <div>+ $${u.priceDelta.amount.toFixed(2)}</div>
                    <button onclick="addToCart('${u.suggestedProductId}', 1)">Change to Premium</button>
                </div>
            `).join("")}
        </div>`;
    }

    // Recommendations
    if (cart.ai.recommendations.length > 0) {
        aiHtml += `<div class="ai-section">
            <h3>Frequently Bought Together</h3>
            <div class="recommendations-grid">
                ${cart.ai.recommendations.map(rid => `
                    <div class="card">
                        <h5>${rid}</h5>
                        <button onclick="addToCart('${rid}')">Add This Too</button>
                    </div>
                `).join("")}
            </div>
        </div>`;
    }

    aiContainer.innerHTML = aiHtml;
  }
}
