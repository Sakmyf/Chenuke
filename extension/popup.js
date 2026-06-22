// popup.js
document.addEventListener('DOMContentLoaded', () => {
    const contentDiv = document.getElementById('content');
    const refreshBtn = document.getElementById('refreshBtn');

    // Inyectar estilos directamente para garantizar el diseño oscuro
    const style = document.createElement('style');
    style.textContent = `
        body {
            width: 320px;
            margin: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #14141e;
            color: #ffffff;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 18px;
            background: rgba(255,255,255,0.03);
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .brand { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 15px; }
        .logo {
            width: 24px; height: 24px;
            background: linear-gradient(135deg, #00c6ff, #0072ff);
            border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            font-weight: bold; font-size: 12px;
        }
        .refresh-btn {
            background: none; border: none; color: #888;
            font-size: 20px; cursor: pointer; transition: color 0.2s;
        }
        .refresh-btn:hover { color: #fff; }
        .content { padding: 18px; }
        
        .loading { display: flex; align-items: center; gap: 12px; color: #aaa; font-size: 14px; }
        .spinner {
            width: 18px; height: 18px;
            border: 2px solid rgba(255,255,255,0.1);
            border-top-color: #00c6ff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .score-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .risk-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
        .risk-value { font-size: 24px; font-weight: 700; }
        .risk-bajo { color: #4ade80; }
        .risk-medio { color: #facc15; }
        .risk-alto { color: #f87171; }

        .score-circle {
            width: 50px; height: 50px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 18px; border: 3px solid;
            background: rgba(0,0,0,0.2);
        }
        .signals { margin-top: 12px; }
        .signal-title { font-size: 13px; color: #888; margin-bottom: 8px; font-weight: 500; }
        .signal-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
        .signal-item {
            background: rgba(255,255,255,0.03);
            padding: 10px 12px; border-radius: 8px;
            font-size: 13px; color: #ddd;
            border-left: 3px solid #0072ff;
        }
        .error { color: #f87171; font-size: 14px; text-align: center; padding: 20px 0; line-height: 1.5; }
    `;
    document.head.appendChild(style);

    function renderLoading() {
        contentDiv.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                Analizando contenido...
            </div>
        `;
    }

    function renderError(msg) {
        contentDiv.innerHTML = `
            <div class="error">${msg}</div>
        `;
    }

    function renderResults(data) {
        const riskText = (data.risk || 'Bajo').toString();
        const riskClass = `risk-${riskText.toLowerCase()}`;
        const score = data.score !== undefined ? data.score : 0;

        let signalsHtml = '';
        if (data.signals && data.signals.length > 0) {
            const items = data.signals.map(s => `<li class="signal-item">${s}</li>`).join('');
            signalsHtml = `
                <div class="signals">
                    <div class="signal-title">Señales estructurales detectadas:</div>
                    <ul class="signal-list">${items}</ul>
                </div>
            `;
        } else {
            signalsHtml = `
                <div class="signals">
                    <div class="signal-title" style="color: #4ade80;">Sin señales de manipulación detectadas.</div>
                </div>
            `;
        }

        contentDiv.innerHTML = `
            <div class="score-container">
                <div>
                    <div class="risk-label">Nivel de Riesgo</div>
                    <div class="risk-value ${riskClass}">${riskText}</div>
                </div>
                <div class="score-circle ${riskClass}">${score}</div>
            </div>
            ${signalsHtml}
        `;
    }

    function analyze() {
        renderLoading();
        
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (chrome.runtime.lastError || tabs.length === 0 || !tabs[0].url) {
                renderError("No se puede analizar esta pestaña.");
                return;
            }

            // Evitar analizar páginas internas de Chrome
            if (tabs[0].url.startsWith("chrome://") || tabs[0].url.startsWith("chrome-extension://")) {
                renderError("No se puede analizar una página interna de Chrome.<br>Ve a un sitio web real.");
                return;
            }

            // Pedir al background que analice la pestaña actual
            chrome.runtime.sendMessage({ type: 'ANALYZE_TAB', tabId: tabs[0].id }, (response) => {
                if (chrome.runtime.lastError) {
                    renderError("Error de conexión con el servidor.");
                    return;
                }
                if (response && response.success && response.data) {
                    renderResults(response.data);
                } else {
                    renderError("No se pudo inicializar en esta página.<br>Intenta recargar la web.");
                }
            });
        });
    }

    refreshBtn.addEventListener('click', analyze);
    analyze();
});