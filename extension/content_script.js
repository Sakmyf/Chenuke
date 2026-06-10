// ======================================================
// SIGNALCHECK CONTENT SCRIPT – CLEAN FIXED VERSION
// ======================================================

// 🔒 Evitar doble inyección
if (!window.__SignalCheckInjected__) {
  window.__SignalCheckInjected__ = true;

  console.log("🚀 SIGNALCHECK CONTENT SCRIPT ACTIVO");

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
  // SANITIZAR TEXTO
  // ------------------------------------------------------
  function sanitizeText(text) {
    if (!text) return "";

    let clean = text.replace(
      /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
      "[EMAIL]"
    );

    return clean;
  }

  // ------------------------------------------------------
  // DETECTAR CONTENEDOR PRINCIPAL
  // ------------------------------------------------------
  function detectMainContainer() {
    const selectors = [
      "article",
      "[role='main']",
      "main",
      ".content",
      "#content",
      ".post",
      ".article",
      "#app",
      "#root",
      "[data-testid='primaryColumn']"
    ];

    let bestElement = null;
    let bestLength = 0;

    for (const selector of selectors) {
      const elements = document.querySelectorAll(selector);

      for (const el of elements) {
        const textLength = (el.innerText || "").length;

        if (textLength > bestLength && textLength > 200) {
          bestLength = textLength;
          bestElement = el;
        }
      }
    }

    if (!bestElement) {
      const largeDivs = document.querySelectorAll("div");

      for (const div of largeDivs) {
        const textLength = (div.innerText || "").length;

        if (textLength > bestLength && textLength > 500) {
          if (div !== document.body && div.children.length > 2) {
            bestLength = textLength;
            bestElement = div;
          }
        }
      }
    }

    return bestElement || document.body;
  }

  // ------------------------------------------------------
  // EXTRACCIÓN INTELIGENTE DEL BODY
  // ------------------------------------------------------
  function extractSmartBodyText() {
    const candidates = [];

    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_ELEMENT,
      null,
      false
    );

    let node;

    while ((node = walker.nextNode())) {
      const tag = node.tagName.toLowerCase();

      if (
        ["script", "style", "nav", "header", "footer", "aside", "form"].includes(tag)
      ) {
        continue;
      }

      const text = node.innerText || "";
      const children = node.children.length;

      if (text.length > 100 && children < 50) {
        candidates.push({
          element: node,
          textLength: text.length,
          density: text.length / Math.max(children, 1)
        });
      }
    }

    candidates.sort((a, b) => b.density - a.density);

    let combinedText = "";
    const used = new Set();

    for (const candidate of candidates.slice(0, 5)) {
      let parent = candidate.element.parentElement;
      let isDuplicate = false;

      while (parent) {
        if (used.has(parent)) {
          isDuplicate = true;
          break;
        }

        parent = parent.parentElement;
      }

      if (!isDuplicate) {
        used.add(candidate.element);
        combinedText += " " + (candidate.element.innerText || "");
      }
    }

    return combinedText;
  }

  // ------------------------------------------------------
  // LIMPIAR ELEMENTOS IRRELEVANTES
  // ------------------------------------------------------
  function cleanDOM(container) {
    if (container === document.body) {
      return {
        type: "smart_body",
        text: extractSmartBodyText()
      };
    }

    const cloned = container.cloneNode(true);

    const selectorsToRemove = [
      "script",
      "style",
      "noscript",
      "svg",
      "img",
      "video",
      "canvas",
      "iframe",
      "header",
      "footer",
      "nav",
      "aside",
      "form",
      "button",
      ".advertisement",
      ".ads",
      ".banner",
      ".popup",
      ".cookie-banner",
      "[role='banner']",
      "[role='complementary']",
      "[role='navigation']"
    ];

    const elements = cloned.querySelectorAll(selectorsToRemove.join(","));
    elements.forEach((el) => el.remove());

    return cloned;
  }

  // ------------------------------------------------------
  // DETECTAR ECOMMERCE
  // ------------------------------------------------------
  function detectEcommerceContext() {
    const ecomSelectors = [
      'button[name="add-to-cart"]',
      ".add-to-cart",
      'a[href*="checkout"]',
      ".cart-icon",
      '[data-testid="checkout-button"]',
      'a[href*="pay.hotmart.com"]',
      'a[href*="pay.stripe.com"]',
      'a[href*="paypal.com"]',
      ".price-tag",
      ".product-price",
      '[class*="price"]'
    ];

    const hasCommerceElements = ecomSelectors.some(
      (selector) => document.querySelector(selector) !== null
    );

    const buttons = Array.from(
      document.querySelectorAll('button, a, [role="button"]')
    );

    const hasBuyText = buttons.some((btn) => {
      const text = (btn.textContent || "").toLowerCase();

      return (
        text.includes("comprar ahora") ||
        text.includes("añadir al carrito") ||
        text.includes("agregar al carrito") ||
        text.includes("inscribirme") ||
        text.includes("comprar") ||
        text.includes("buy now") ||
        text.includes("add to cart") ||
        text.includes("get instant access") ||
        text.includes("order now")
      );
    });

    const bodyText = document.body?.innerText || "";
    const hasPricePattern = /\$\s?\d+[\d,.]*/.test(bodyText);

    return hasCommerceElements || hasBuyText || hasPricePattern;
  }

  // ------------------------------------------------------
  // EXTRAER TEXTO LIMPIO
  // ------------------------------------------------------
  function extractCleanText() {
    if (!document.body) return "";

    try {
      const container = detectMainContainer();
      const cleaned = cleanDOM(container);

      let text = "";

      if (cleaned) {
        if (cleaned.type === "smart_body") {
          text = normalizeText(cleaned.text || "");
        } else {
          text = normalizeText(cleaned.textContent || cleaned.innerText || "");
        }
      }

      if (!text || text.length < 200) {
        text = normalizeText(document.body.innerText || "");
      }

      text = sanitizeText(text);

      return text.substring(0, 20000);
    } catch (err) {
      console.warn("⚠ fallback extracción:", err);

      return sanitizeText(
        normalizeText(document.body.innerText || "")
      ).substring(0, 20000);
    }
  }

  // ------------------------------------------------------
  // LISTENER EXTENSIÓN
  // ------------------------------------------------------
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (
      !request ||
      (
        request.action !== "extractText" &&
        request.type !== "GET_PAGE_CONTENT" &&
        request.type !== "ping"
      )
    ) {
      return;
    }

    if (request.type === "ping") {
      sendResponse({
        ok: true,
        injected: true
      });

      return true;
    }

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

    return true;
  });
}