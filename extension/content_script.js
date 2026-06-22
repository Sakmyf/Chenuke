// content_script.js
(function() {
    'use strict';

    let host;
    let shadow;

    // Función para escapar HTML y evitar inyecciones (XSS)
    function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function init() {
        // Prevenir inyecciones múltiples
        if (document.getElementById('signalcheck-host')) return;

        host = document.createElement('div');
        host.id = 'signalcheck-host';
        host.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 2147483647; all: initial;';
        
        shadow = host.attachShadow({ mode: 'open' });
        
        const style = document.createElement('style');
        style.textContent = `
            .sc-card {
                width: 320px;
                background: rgba(20, 20, 30, 0.95);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 16px;
                color: #ffffff;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                overflow: hidden;
                animation: sc-slide-in 0.3s ease-out;
            }
            @keyframes sc-slide-in {
                from { transform: translateY(20px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            .sc-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 14px 18px;
                background: rgba(255,255,255,0.03);
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            .sc-brand {
                display: flex;
                align-items: center;
                gap: 10px;
                font-weight: 600;
                font-size: 15px;
                color: #f0f0f0;
            }
            .sc-logo {
                width: 24px;
                height: 24px;
                background: linear-gradient(135deg, #00c6ff, #0072ff);
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            .sc-close {
                cursor: pointer;
                color: #888;
                font-size: 22px;
                line-height: 1;
                background: none;
                border: none;
                padding: 0;
                transition: color 0.2s;
            }
            .sc-close:hover { color: #fff; }

            .sc-body { padding: 18px; }
            
            .sc-status-loading {
                display: flex;
                align-items: center;
                gap: 12px;
                color: #aaa;
                font-size: 14px;
            }
            .sc-spinner {
                width: 18px;
                height: 18px;
                border: 2px solid rgba(255,255,255,0.1);
                border-top-color: #00c6ff;
                border-radius: 50%;
                animation: sc-spin 0.8s linear infinite;
            }
            @keyframes sc-spin { to { transform: rotate(360deg); } }

            .sc-score-container {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            }
            .sc-risk-info { display: flex; flex-direction: column; }
            .sc-risk-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
            .sc-risk-value { font-size: 24px; font-weight: 700; }
            
            .sc-risk-bajo { color: #4ade80; }
            .sc-risk-medio { color: #facc15; }
            .sc-risk-alto { color: #f87171; }

            .sc-score-circle {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 18px;
                border: 3px solid;
                background: rgba(0,0,0,0.2);
            }
            
            .sc-signals { margin-top: 12px; }
            .sc-signal-title { font-size: 13px; color: #888; margin-bottom: 8px; font-weight: 500; }
            .sc-signal-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
            .sc-signal-item {
                background: rgba(255,255,255,0.03);
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 13px;
                color: #ddd;
                border-left: 3px solid #0072ff;
            }
            
            .sc-error { color: #f87171; font-size: 14px; text-align: center; padding: 10px 0; line-height: 1.5; }
            .sc-retry-btn {
                margin-top: 12px;
                width: 100%;
                padding: 8px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                color: white;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                transition: background 0.2s;
            }
            .sc-retry-btn:hover { background: rgba(255,255,255,0.1); }
        `;
        shadow.appendChild(style);

        const card = document.createElement('div');
        card.className = 'sc-card';
        shadow.appendChild(card);

        renderLoading(card);

        document.body.appendChild(host);

        // Iniciar análisis
        setTimeout(() => analyzeText(card), 100);
    }

    function renderLoading(card) {
        card.innerHTML = `
            <div class="sc-header">
                <div class="sc-brand">
                    <div class="sc-logo">SC</div>
                    SignalCheck
                </div>
                <button class="sc-close">×</button>
            </div>
            <div class="sc-body">
                <div class="sc-status-loading">
                    <div class="sc-spinner"></div>
                    Analizando contenido...
                </div>
            </div>
        `;
        shadow.querySelector('.sc-close').addEventListener('click', () => host.remove());
    }

    function renderError(card, errorMsg) {
        card.innerHTML = `
            <div class="sc-header">
                <div class="sc-brand">
                    <div class="sc-logo">SC</div>
                    SignalCheck
                </div>
                <button class="sc-close">×</button>
            </div>
            <div class="sc-body">
                <div class="sc-error">No se pudo analizar en esta página.<br><small style="color:#666">${escapeHtml(errorMsg)}</small></div>
                <button class="sc-retry-btn">Reintentar análisis</button>
            </div>
        `;
        shadow.querySelector('.sc-close').addEventListener('click', () => host.remove());
        shadow.querySelector('.sc-retry-btn').addEventListener('click', () => {
            renderLoading(card);
            setTimeout(() => analyzeText(card), 100);
        });
    }

    function renderResults(card, data) {
        const riskText = (data.risk || 'Bajo').toString();
        const riskClass = `sc-risk-${riskText.toLowerCase()}`;
        const score = data.score !== undefined ? data.score : 0;

        let signalsHtml = '';
        if (data.signals && Array.isArray(data.signals) && data.signals.length > 0) {
            const signalsList = data.signals.map(s => `<li class="sc-signal-item">${escapeHtml(s)}</li>`).join('');
            signalsHtml = `
                <div class="sc-signals">
                    <div class="sc-signal-title">Señales estructurales detectadas:</div>
                    <ul class="sc-signal-list">${signalsList}</ul>
                </div>
            `;
        } else {
            signalsHtml = `
                <div class="sc-signals">
                    <div class="sc-signal-title" style="color: #4ade80;">Sin señales de manipulación detectadas.</div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="sc-header">
                <div class="sc-brand">
                    <div class="sc-logo">SC</div>
                    SignalCheck
                </div>
                <button class="sc-close">×</button>
            </div>
            <div class="sc-body">
                <div class="sc-score-container">
                    <div class="sc-risk-info">
                        <span class="sc-risk-label">Nivel de Riesgo</span>
                        <span class="sc-risk-value ${riskClass}">${escapeHtml(riskText)}</span>
                    </div>
                    <div class="sc-score-circle ${riskClass}">${score}</div>
                </div>
                ${signalsHtml}
            </div>
        `;
        shadow.querySelector('.sc-close').addEventListener('click', () => host.remove());
    }

    function analyzeText(card) {
        try {
            const pageText = document.body.innerText.slice(0, 5000);
            if (!pageText || pageText.trim().length < 50) {
                renderError(card, 'No hay suficiente texto en la página para analizar.');
                return;
            }

            chrome.runtime.sendMessage(
                { type: 'ANALYZE_TEXT', text: pageText },
                (response) => {
                    if (chrome.runtime.lastError) {
                        renderError(card, 'Error de conexión con el backend.');
                        return;
                    }
                    if (response && response.success && response.data) {
                        renderResults(card, response.data);
                    } else {
                        renderError(card, 'El backend no devolvió datos válidos.');
                    }
                }
            );
        } catch (e) {
            renderError(card, 'Error inesperado al leer la página.');
            console.error('SignalCheck Error:', e);
        }
    }

    // Ejecutar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();