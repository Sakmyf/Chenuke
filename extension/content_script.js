// content_script.js — Chenuke v15.23
// Extrae texto útil de páginas, landings, formularios y artículos.
// NO modifica el DOM ni inyecta UI propia.

'use strict';

(function () {
  // Guard: evitar múltiples inyecciones
  if (window.__chenuke_injected) return;
  window.__chenuke_injected = true;

  const MAX_CHARS = 30000;
  const MIN_USEFUL_LEN = 150;

  const MAIN_SELECTORS = [
    'article',
    'main',
    'section',
    'p',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'li',
    'td',
    'th',
    'blockquote',
    'figcaption'
  ].join(',');

  const ACTION_SELECTORS = [
    'button',
    '[role="button"]',
    'a',
    'label',
    'input',
    'textarea',
    'select',
    'option'
  ].join(',');

  const META_SELECTORS = [
    'meta[name="description"]',
    'meta[property="og:title"]',
    'meta[property="og:description"]',
    'meta[name="twitter:title"]',
    'meta[name="twitter:description"]'
  ].join(',');

  function cleanText(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .replace(/\u00a0/g, ' ')
      .trim();
  }

  function pushUnique(parts, seen, value, minLen = 2) {
    const text = cleanText(value);

    if (!text || text.length < minLen) return;

    const key = text.toLowerCase();

    if (seen.has(key)) return;

    seen.add(key);
    parts.push(text);
  }

  function extractMetaText(parts, seen) {
    pushUnique(parts, seen, document.title || '', 3);

    document.querySelectorAll(META_SELECTORS).forEach((el) => {
      pushUnique(parts, seen, el.getAttribute('content'), 3);
    });
  }

  function extractMainText(parts, seen) {
    document.querySelectorAll(MAIN_SELECTORS).forEach((el) => {
      const text = el.innerText || el.textContent || '';
      pushUnique(parts, seen, text, 20);
    });
  }

  function extractActionAndFormText(parts, seen) {
    document.querySelectorAll(ACTION_SELECTORS).forEach((el) => {
      pushUnique(parts, seen, el.innerText || el.textContent || '', 2);

      pushUnique(parts, seen, el.getAttribute('placeholder'), 2);
      pushUnique(parts, seen, el.getAttribute('aria-label'), 2);
      pushUnique(parts, seen, el.getAttribute('title'), 2);
      pushUnique(parts, seen, el.getAttribute('alt'), 2);

      const type = (el.getAttribute('type') || '').toLowerCase();

      if (type === 'submit' || type === 'button') {
        pushUnique(parts, seen, el.getAttribute('value'), 2);
      }

      if (el.name) pushUnique(parts, seen, el.name, 2);
      if (el.id) pushUnique(parts, seen, el.id, 2);
    });
  }

  function extractText() {
    try {
      const parts = [];
      const seen = new Set();

      extractMetaText(parts, seen);
      extractMainText(parts, seen);
      extractActionAndFormText(parts, seen);

      let text = parts.join('\n').replace(/\n{3,}/g, '\n\n').trim();

      // Fallback a body completo si el resultado estructural es corto.
      if (text.length < MIN_USEFUL_LEN && document.body) {
        text = cleanText(document.body.innerText || document.body.textContent || '');
      }

      return text.slice(0, MAX_CHARS);
    } catch (e) {
      try {
        return cleanText(document.body.innerText || document.body.textContent || '').slice(0, MAX_CHARS);
      } catch (_) {
        return '';
      }
    }
  }

  function detectEcommerce(text, url) {
    const t = (text || '').toLowerCase();
    const u = (url || '').toLowerCase();

    const urlSignals = [
      'shop',
      'store',
      'tienda',
      'compra',
      'cart',
      'checkout',
      'product',
      'oferta',
      'catalogo',
      'catálogo'
    ];

    const textSignals = [
      'comprar',
      'carrito',
      'precio',
      'descuento',
      'envío',
      'checkout',
      'agregar al carrito',
      'buy now',
      'add to cart'
    ];

    const financialSignals = [
      'trading',
      'forex',
      'acciones',
      'invertir',
      'invierta',
      'inversión',
      'ganar dinero',
      'dinero extra',
      'segundo ingreso',
      'ingresos ilimitados',
      'solicitar información',
      'registrate ahora',
      'regístrate ahora',
      'aprende y gana',
      'aprendé y ganá'
    ];

    return (
      urlSignals.some((w) => u.includes(w)) ||
      textSignals.some((w) => t.includes(w)) ||
      financialSignals.some((w) => t.includes(w) || u.includes(w))
    );
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.type === 'ping') {
      sendResponse({ injected: true });
      return true;
    }

    if (msg && msg.action === 'extractText') {
      try {
        const text = extractText();
        const url = window.location.href;
        const title = document.title || '';
        const is_ecommerce = detectEcommerce(text, url);

        if (!text || text.trim().length < 30) {
          sendResponse({
            ok: false,
            error: 'Texto insuficiente en la página'
          });
        } else {
          sendResponse({
            ok: true,
            text,
            url,
            title,
            is_ecommerce
          });
        }
      } catch (e) {
        sendResponse({
          ok: false,
          error: String(e)
        });
      }

      return true;
    }
  });
})();