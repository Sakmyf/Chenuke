// content_script.js — Chenuke v15.29
// Extrae texto útil de páginas, landings, formularios y artículos.
// NO modifica el DOM ni inyecta UI propia.
//
// v15.28: se dejan de extraer atributos técnicos del DOM (name, id, value,
// placeholder) y elementos de formulario ("email", "pass", "lgnjs").
// v15.29: se filtra CÓDIGO CRUDO. textContent de <section>/<li> incluía
// scripts inline embebidos (ej: 'var ba147url="...botmaker...init.js"'),
// que entraban al análisis como "narrativa" y ensuciaban el informe de
// sitios oficiales. Ahora: se saltan nodos dentro de script/style/etc.,
// se prefiere innerText, y pushUnique descarta fragmentos con firma de
// JS/CSS/markup.

'use strict';

(function () {
  if (window.__chenuke_injected) return;
  window.__chenuke_injected = true;

  const MAX_CHARS = 30000;
  const MIN_USEFUL_LEN = 150;

  const MAIN_SELECTORS = [
    'article', 'main', 'section', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'li', 'td', 'th', 'blockquote', 'figcaption'
  ].join(',');

  // Solo elementos con texto visible para el usuario. NO se incluyen
  // input/textarea/select/option: sus atributos técnicos (name, id, value)
  // son markup de la interfaz, no discurso, y contaminan el análisis.
  const ACTION_SELECTORS = [
    'button', '[role="button"]', 'a', 'label'
  ].join(',');

  const META_SELECTORS = [
    'meta[name="description"]',
    'meta[property="og:title"]',
    'meta[property="og:description"]',
    'meta[name="twitter:title"]',
    'meta[name="twitter:description"]'
  ].join(',');

  // Nodos cuyo texto NUNCA es discurso: código, estilos, plantillas.
  // textContent los incluiría (a diferencia de innerText), metiendo JS
  // crudo como "var ba147url=..." en el análisis. Se descartan a nivel
  // de elemento y de ancestro.
  const NOISE_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'CODE', 'PRE']);

  function inNoiseNode(el) {
    let n = el;
    while (n && n !== document.body) {
      if (NOISE_TAGS.has(n.tagName)) return true;
      n = n.parentElement;
    }
    return false;
  }

  // Heurística anti-código: fragmentos con firma de JS/CSS/markup no son
  // texto que el usuario lee. Evita que un <script> sin envolver o un
  // bloque de config se cuele como "narrativa".
  function looksLikeCode(text) {
    if (!text) return false;
    if (/\b(?:var|let|const|function)\s+[\w$]+\s*=/.test(text)) return true;
    if (/https?:\/\/\S+\.(?:js|css)(?:["';)\s]|$)/.test(text)) return true;
    if (/[{};]\s*$/.test(text) && /[:=(]/.test(text)) return true;
    if (/<\/?[a-z][\w-]*[^>]*>/i.test(text)) return true;
    return false;
  }

  function cleanText(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .replace(/\u00a0/g, ' ')
      .trim();
  }

  function pushUnique(parts, seen, value, minLen = 2) {
    const text = cleanText(value);
    if (!text || text.length < minLen) return;
    if (looksLikeCode(text)) return;   // no dejar pasar JS/CSS/markup crudo
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
      if (inNoiseNode(el)) return;              // dentro de <script>/<style>/etc.
      // innerText respeta lo renderizado (ignora scripts); textContent NO,
      // por eso solo se cae a textContent si innerText viene realmente vacío
      // Y el resultado no parece código (lo filtra pushUnique igual).
      const text = el.innerText || el.textContent || '';
      pushUnique(parts, seen, text, 20);
    });
  }

  function extractActionAndFormText(parts, seen) {
    document.querySelectorAll(ACTION_SELECTORS).forEach((el) => {
      // Solo lo que el usuario efectivamente lee en pantalla (o escucha vía
      // lector de pantalla). Se excluyen a propósito:
      //   - el.name / el.id  → nombres técnicos del DOM ("email", "pass",
      //     "lgnjs"). No son discurso: inflan el largo del texto, disparan
      //     falsos positivos y mandan estructura de formularios de sesión
      //     al backend y a la IA. Fueron la causa de que un análisis de
      //     Facebook incluyera campos de login.
      //   - el.getAttribute('value') → idem para botones.
      pushUnique(parts, seen, el.innerText || el.textContent || '', 2);
      pushUnique(parts, seen, el.getAttribute('aria-label'), 2);
      pushUnique(parts, seen, el.getAttribute('title'), 2);
      pushUnique(parts, seen, el.getAttribute('alt'), 2);
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

    const urlSignals = ['shop', 'store', 'tienda', 'compra', 'cart', 'checkout', 'product', 'oferta', 'catalogo', 'catálogo'];
    const textSignals = ['comprar', 'carrito', 'precio', 'descuento', 'envío', 'checkout', 'agregar al carrito', 'buy now', 'add to cart'];
    const financialSignals = ['trading', 'forex', 'acciones', 'invertir', 'invierta', 'inversión', 'ganar dinero', 'dinero extra', 'segundo ingreso', 'ingresos ilimitados', 'solicitar información', 'registrate ahora', 'regístrate ahora', 'aprende y gana', 'aprendé y ganá'];

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
          sendResponse({ ok: false, error: 'Texto insuficiente en la página' });
        } else {
          sendResponse({ ok: true, text, url, title, is_ecommerce });
        }
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
      return true;
    }
  });
})();