// ======================================================
// SIGNALCHECK CONTENT SCRIPT – CLEAN FIXED VERSION (v2)
// ======================================================

// 🔒 Evitar doble inyección
if (!window.__SignalCheckInjected__) {
  window.__SignalCheckInjected__ = true;

  console.log("🚀 SIGNALCHECK CONTENT SCRIPT ACTIVO");

  // ------------------------------------------------------
  // CONSTANTES GLOBALES
  // ------------------------------------------------------
  const MAX_TEXT_LENGTH = 20000;
  const MIN_BODY_LENGTH = 120;
  
  const NOISE_SELECTORS = [
    "script", "style", "noscript", "svg", "iframe", "nav", "header", "footer", 
    "aside", "form", "button", "[role='navigation']", "[role='banner']", 
    "[role='complementary']", ".nav", ".menu", ".navbar", ".sidebar", ".footer", 
    ".header", ".ads", ".advertisement", ".banner", ".popup", ".cookie-banner", 
    ".breadcrumb", ".menu-lateral"
  ].join(", ");

  const CONTENT_SELECTORS = [
    "p", "td", "th", "li", "h1", "h2", "h3", "h4", "h5", "h6", 
    "blockquote", "article", "section", "dd", "dt", "span"
  ].join(", ");

  const ECOM_SELECTORS = [
    'button[name="add-to-cart"]', ".add-to-cart", 'a[href*="checkout"]', ".cart-icon",
    '[data-testid="checkout-button"]', 'a[href*="pay.hotmart.com"]', 'a[href*="pay.stripe.com"]',
    'a[href*="paypal.com"]', ".price-tag", ".product-price", '[class*="price"]'
  ];

  const BUY_TEXTS = [
    "comprar ahora", "añadir al carrito", "agregar al carrito", "inscribirme", 
    "comprar", "buy now", "add to cart", "get instant access", "order now"
  ];

  const EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const PRICE_REGEX = /\$\s?\d+[\d,.]*/;

  // ------------------------------------------------------
  // UTILIDAD: LIMPIAR TEXTO
  // ------------------------------------------------------
  function normalizeText(text) {
    if (!text) return "";
    return String(text)
      .replace(/\s+/g, " ")
      .replace(/\n+/g, " ")
      .replace(/\t+/g, " ")
      .trim();
  }

  // ------------------------------------------------------
  // SANITIZAR TEXTO (PII)
  // ------------------------------------------------------
  function sanitizeText(text) {
    if (!text) return "";
    return text.replace(EMAIL_REGEX, "[EMAIL]");
  }

  // ------------------------------------------------------
  // EXTRACCIÓN INTELIGENTE DEL BODY (SIN CLONAR DOM)
  // ------------------------------------------------------
  function extractSmartBodyText() {
    const blocks = document.querySelectorAll(CONTENT_SELECTORS);
    const seen = new Set();
    const parts = [];

    blocks.forEach((el) => {
      // 1. Saltar si está dentro de un contenedor de ruido (nav, ads, etc)
      if (el.closest(NOISE_SELECTORS)) return;

      // 2. Saltar contenedores que envuelven a otros bloques (evita duplicar texto)
      if (el.querySelector(CONTENT_SELECTORS)) return;

      const txt = normalizeText(el.innerText || el.textContent || "");
      
      // Umbral bajo (>20) para no perder celdas/títulos cortos legítimos
      if (txt.length > 20 && !seen.has(txt)) {
        seen.add(txt);
        parts.push(txt);
      }
    });

    let combined = parts.join(" ");

    // Red de seguridad: si aún quedó poco, usar el innerText completo del body
    if (combined.length < 200) {
      combined = normalizeText(document.body.innerText || "");
    }

    return combined;
  }

  // ------------------------------------------------------
  // DETECTAR ECOMMERCE
  // ------------------------------------------------------
  function detectEcommerceContext() {
    const hasCommerceElements = ECOM_SELECTORS.some(
      (selector) => document.querySelector(selector) !== null
    );

    let hasBuyText = false;
    if (!hasCommerceElements) {
      const buttons = document.querySelectorAll('button, a, [role="button"]');
      for (const btn of buttons) {
        const text = (btn.textContent || "").toLowerCase();
        if (BUY_TEXTS.some(t => text.includes(t))) {
          hasBuyText = true;
          break;
        }
      }
    }

    const bodyText = document.body?.innerText || "";
    const hasPricePattern = PRICE_REGEX.test(bodyText);

    return hasCommerceElements || hasBuyText || hasPricePattern;
  }

  // ------------------------------------------------------
  // EXTRAER TEXTO LIMPIO (ORQUESTADOR)
  // ------------------------------------------------------
  function extractCleanText() {
    if (!document.body) return "";

    try {
      let text = extractSmartBodyText();

      // Doble verificación por si la extracción falla
      if (!text || text.length < MIN_BODY_LENGTH) {
        const fallback = normalizeText(document.body.innerText || "");
        if (fallback.length > text.length) text = fallback;
      }

      text = sanitizeText(text);
      return text.substring(0, MAX_TEXT_LENGTH);
      
    } catch (err) {
      console.warn("⚠ fallback extracción:", err);
      return sanitizeText(
        normalizeText(document.body.innerText || "")
      ).substring(0, MAX_TEXT_LENGTH);
    }
  }

  // ------------------------------------------------------
  // LISTENER EXTENSIÓN (ASÍNCRONO PARA NO BLOQUEAR UI)
  // ------------------------------------------------------
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (!request || (request.action !== "extractText" && request.type !== "GET_PAGE_CONTENT" && request.type !== "ping")) {
      return false; 
    }

    if (request.type === "ping") {
      sendResponse({ ok: true, injected: true });
      return false; 
    }

    // Usamos setTimeout(0) para ceder el hilo al navegador antes de procesar el DOM pesado.
    // Esto previene el "congelamiento" de la pestaña del usuario.
    setTimeout(() => {
      try {
        const cleanText = extractCleanText();
        const isEcommerce = detectEcommerceContext();

        sendResponse({
          ok: true,
          text: cleanText,
          url: window.location.href,
          title: document.title || "",
          is_ecommerce: isEcommerce
        });
      } catch (error) {
        console.error("❌ Error extrayendo texto:", error);
        sendResponse({
          ok: false,
          text: "",
          url: window.location.href,
          title: document.title || "",
          error: true,
          is_ecommerce: false
        });
      }
    }, 0);

    return true; // Indica a Chrome que sendResponse se llamará de forma asíncrona
  });
}