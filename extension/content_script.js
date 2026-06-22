// content_script.js
(function() {
    'use strict';

    // Evitar bloqueo del Main Thread y dar tiempo a que la página cargue
    setTimeout(() => {
        // 1. Extraer texto de la página (limitado para no saturar el backend)
        // Usamos innerText en lugar de textContent para obtener texto visible real
        const pageText = document.body.innerText.slice(0, 5000); 

        if (!pageText || pageText.trim().length < 50) {
            return; // No hay suficiente texto para analizar
        }

        // 2. Enviar mensaje al Service Worker (Background) para que haga la petición al backend
        chrome.runtime.sendMessage(
            { type: 'ANALYZE_TEXT', text: pageText },
            (response) => {
                // Fix: Mitigar error de Message Port Leaks
                if (chrome.runtime.lastError) {
                    console.error('SignalCheck Error:', chrome.runtime.lastError.message);
                    return;
                }

                if (response && response.success && response.data) {
                    renderUI(response.data);
                }
            }
        );
    }, 0);

    // 3. Función para renderizar la UI con Shadow DOM (Aislamiento total de CSS)
    function renderUI(data) {
        // data = { risk: 'Bajo', score: 0, signals: [...] }
        
        // Evitar inyección duplicada si ya existe
        if (document.getElementById('signalcheck-host')) {
            document.getElementById('signalcheck-host').remove();
        }

        // Crear Host
        const host = document.createElement('div');
        host.id = 'signalcheck-host';
        // Posición fija, z-index altísimo, y 'all: initial' para resetear herencia
        host.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 2147483647; all: initial;';

        // Adjuntar Shadow DOM
        const shadow = host.attachShadow({ mode: 'open' });

        // Estilos aislados dentro del Shadow DOM
        const style = document.createElement('style');
        style.textContent = `
            .sc-container {
                width: 280px;
                background: #ffffff;
                border-radius: 10px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                color: #1a1a1a;
                padding: 16px;
                font-size: 14px;
                line-height: 1.5;
                box-sizing: border-box;
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #e0e0e0;
            }
            .sc-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid #eee;
                padding-bottom: 8px;
                margin-bottom: 12px;
            }
            .sc-title {
                font-weight: 700;
                font-size: 16px;
                color: #333;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .sc-logo {
                width: 16px;
                height: 16px;
                background: #4285f4;
                border-radius: 50%;
                display: inline-block;
            }
            .sc-risk-badge {
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                display: inline-block;
                margin-bottom: 12px;
            }
            .sc-risk-bajo { background: #e6f4ea; color: #137333; }
            .sc-risk-medio { background: #fef7e0; color: #b06000; }
            .sc-risk-alto { background: #fce8e6; color: #c5221f; }
            
            .sc-section-title {
                font-weight: 600;
                font-size: 13px;
                color: #555;
                margin-top: 10px;
                margin-bottom: 6px;
            }
            .sc-signal-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .sc-signal-item {
                display: flex;
                align-items: flex-start;
                gap: 8px;
                margin-bottom: 6px;
                font-size: 13px;
                color: #444;
            }
            .sc-icon {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #999;
                margin-top: 7px;
                flex-shrink: 0;
            }
            .sc-close {
                cursor: pointer;
                color: #999;
                font-size: 18px;
                line-height: 1;
                font-weight: normal;
            }
            .sc-close:hover { color: #333; }
        `;

        // Contenedor interno
        const container = document.createElement('div');
        container.className = 'sc-container';

        // Mapear riesgo a clase (manejo seguro de strings)
        const riskText = (data.risk || 'Bajo').toString();
        const riskClass = `sc-risk-${riskText.toLowerCase()}`;
        const score = data.score !== undefined ? data.score : 0;

        // --- Construir UI de forma segura (Sin innerHTML para evitar XSS) ---

        // Header
        const header = document.createElement('div');
        header.className = 'sc-header';
        
        const titleDiv = document.createElement('div');
        titleDiv.className = 'sc-title';
        const logo = document.createElement('span');
        logo.className = 'sc-logo';
        titleDiv.appendChild(logo);
        titleDiv.appendChild(document.createTextNode('SignalCheck'));
        
        const closeBtn = document.createElement('span');
        closeBtn.className = 'sc-close';
        closeBtn.textContent = '×';
        closeBtn.addEventListener('click', () => host.remove());
        
        header.appendChild(titleDiv);
        header.appendChild(closeBtn);

        // Badge de Riesgo
        const riskBadge = document.createElement('div');
        riskBadge.className = `sc-risk-badge ${riskClass}`;
        riskBadge.textContent = `Riesgo: ${riskText} (${score})`;

        container.appendChild(header);
        container.appendChild(riskBadge);

        // Señales detectadas
        if (data.signals && Array.isArray(data.signals) && data.signals.length > 0) {
            const signalsTitle = document.createElement('div');
            signalsTitle.className = 'sc-section-title';
            signalsTitle.textContent = 'Señales detectadas:';
            container.appendChild(signalsTitle);

            const ul = document.createElement('ul');
            ul.className = 'sc-signal-list';
            
            data.signals.forEach(signal => {
                const li = document.createElement('li');
                li.className = 'sc-signal-item';
                const dot = document.createElement('span');
                dot.className = 'sc-icon';
                li.appendChild(dot);
                // Usar textContent previene ataques XSS si el backend devolvió código malicioso
                li.appendChild(document.createTextNode(signal)); 
                ul.appendChild(li);
            });
            container.appendChild(ul);
        } else {
            const noSignals = document.createElement('div');
            noSignals.style.marginTop = '10px';
            noSignals.style.fontSize = '13px';
            noSignals.style.color = '#666';
            noSignals.textContent = 'No se detectaron señales de manipulación estructural.';
            container.appendChild(noSignals);
        }

        // Ensamblar y adjuntar al DOM
        shadow.appendChild(style);
        shadow.appendChild(container);
        document.body.appendChild(host);
    }
})();