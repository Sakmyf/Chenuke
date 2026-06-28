// content_script.js — Chenukek v15.x
// Escucha mensajes del popup y extrae texto de la página.
// NO modifica el DOM ni inyecta UI propia.
'use strict';

(function () {
  // Guard: evitar múltiples inyecciones
  if (window.__signalcheck_injected) return;
  window.__signalcheck_injected = true;

  /**
   * Extrae texto limpio de la página.
   * Estrategia:
   *   1. Intenta párrafos/encabezados/listas — cubre la mayoría de sitios.
   *   2. Si el resultado es muy corto, cae a body.innerText (sitios legacy, .asp, tablas).
   *   Máximo 20.000 chars para no saturar el backend.
   */
  function extractText() {
    const SELECTORS = "p, article, main, section, h1, h2, h3, h4, h5, li, td, th, blockquote, figcaption";
    const MIN_USEFUL_LEN = 150;
    const MAX_CHARS = 20000;

    try {
      const parts = [];
      const nodes = document.querySelectorAll(SELECTORS);
      nodes.forEach(el => {
        const t = (el.innerText || el.textContent || "").trim();
        if (t.length > 20) parts.push(t);
      });

      let text = parts.join("\n").replace(/\n{3,}/g, "\n\n").trim();

      // Fallback a body completo si el resultado estructural es demasiado corto
      if (text.length < MIN_USEFUL_LEN) {
        text = (document.body.innerText || "").trim();
      }

      return text.slice(0, MAX_CHARS);
    } catch (e) {
      // Último recurso
      try { return (document.body.innerText || "").slice(0, MAX_CHARS); }
      catch (_) { return ""; }
    }
  }

  /**
   * Detecta señales básicas de e-commerce en URL y texto visible.
   */
  function detectEcommerce(text, url) {
    const t = (text || "").toLowerCase();
    const u = (url || "").toLowerCase();
    const urlSignals = ["shop", "store", "tienda", "compra", "cart", "checkout", "product", "oferta", "catalogo"];
    const textSignals = ["comprar", "carrito", "precio", "descuento", "envío", "checkout", "agregar al carrito", "buy now", "add to cart"];
    return urlSignals.some(w => u.includes(w)) || textSignals.some(w => t.includes(w));
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    // Ping de verificación — el popup pregunta si el script está activo
    if (msg && msg.type === "ping") {
      sendResponse({ injected: true });
      return true;
    }

    // Solicitud de extracción de texto
    if (msg && msg.action === "extractText") {
      try {
        const text  = extractText();
        const url   = window.location.href;
        const title = document.title || "";
        const is_ecommerce = detectEcommerce(text, url);

        if (!text || text.trim().length < 30) {
          sendResponse({ ok: false, error: "Texto insuficiente en la página" });
        } else {
          sendResponse({ ok: true, text, url, title, is_ecommerce });
        }
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
      return true; // indica respuesta asíncrona
    }
  });

})();