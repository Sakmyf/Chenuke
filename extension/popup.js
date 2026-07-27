<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Chenuke — Informe de análisis</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg:#0a0f1a;--panel:#111827;--border:#1e293b;--accent:#3b82f6;--accent-glow:#60a5fa;--text:#e2e8f0;--muted:#94a3b8;
      --success:#10b981;--warning:#f59e0b;--danger:#ef4444;
    }
    *{box-sizing:border-box;margin:0;padding:0;}
    body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;line-height:1.7;-webkit-font-smoothing:antialiased;padding:2rem 1rem;min-height:100vh;display:flex;justify-content:center;align-items:flex-start;}
    .container{max-width:820px;width:100%;}
    .report-card{background:var(--panel);border:1px solid var(--border);border-radius:20px;padding:2.5rem;box-shadow:0 30px 60px -15px rgba(0,0,0,.8);}
    .report-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;border-bottom:1px solid var(--border);padding-bottom:1.5rem;flex-wrap:wrap;gap:1rem;}
    .report-header h1{font-size:1.8rem;font-weight:700;color:white;}
    .badge{background:rgba(59,130,246,.15);color:var(--accent-glow);padding:6px 16px;border-radius:20px;font-size:.85rem;font-weight:500;border:1px solid rgba(59,130,246,.2);}
    .score-display{text-align:center;padding:2rem 0;margin-bottom:1.5rem;border-bottom:1px solid var(--border);}
    .score-number{font-size:4rem;font-weight:900;font-family:'JetBrains Mono',monospace;color:white;line-height:1;}
    .score-number .level-badge{font-size:1.2rem;margin-left:0.5rem;}
    .score-label{font-size:1rem;color:var(--muted);margin-top:0.5rem;}
    .details-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1.5rem 0;}
    .detail-item{background:rgba(0,0,0,.2);border-radius:12px;padding:1rem;text-align:center;border:1px solid var(--border);}
    .detail-item .label{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}
    .detail-item .value{font-size:1.4rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:white;}
    .insight-box{background:rgba(59,130,246,.05);border-left:3px solid var(--accent);padding:1rem 1.5rem;border-radius:0 8px 8px 0;margin:1.5rem 0;font-size:1rem;color:var(--muted);line-height:1.6;}
    .back-btn{display:inline-block;margin-top:2rem;padding:12px 28px;background:var(--accent);color:white;border-radius:10px;text-decoration:none;font-weight:600;transition:background .2s,transform .2s;border:none;cursor:pointer;}
    .back-btn:hover{background:var(--accent-glow);transform:translateY(-2px);}
    .error-message{text-align:center;padding:3rem 1rem;color:var(--muted);}
    .error-message h2{color:white;font-size:2rem;margin-bottom:1rem;}
    .error-message .sub{color:var(--muted);margin-bottom:1.5rem;}
    .btn-group{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;}
    @media(max-width:600px){.report-card{padding:1.5rem;}.details-grid{grid-template-columns:1fr;}}
  </style>
</head>
<body>
  <div class="container">
    <div class="report-card" id="reportCard">
      <div class="report-header">
        <h1>📋 Informe de análisis</h1>
        <span class="badge">Chenuke</span>
      </div>
      <div id="content">
        <!-- El contenido se renderiza con JS -->
      </div>
    </div>
  </div>
  <script>
    (function() {
      const content = document.getElementById('content');
      let score = null;
      let level = 'bajo';
      let conf = '';

      // 1. Intentar obtener parámetros de la URL
      const params = new URLSearchParams(window.location.search);
      const urlScore = params.get('score');
      const urlLevel = params.get('level');
      const urlConf = params.get('conf');

      if (urlScore !== null && urlScore !== '' && !isNaN(parseInt(urlScore, 10))) {
        score = parseInt(urlScore, 10);
        level = urlLevel || 'bajo';
        conf = urlConf || '';
      } else {
        // 2. Fallback: intentar recuperar de localStorage (guardado por el popup)
        try {
          const stored = localStorage.getItem('chenuke_last_analysis');
          if (stored) {
            const data = JSON.parse(stored);
            if (data && data.score !== undefined && data.score !== null && !isNaN(data.score)) {
              score = parseInt(data.score, 10);
              level = data.level || 'bajo';
              conf = data.confidence || '';
              // Limpiar localStorage para no reusar datos viejos
              localStorage.removeItem('chenuke_last_analysis');
            }
          }
        } catch (e) { /* ignore */ }
      }

      // 3. Si no hay datos, mostrar error y redirigir
      if (score === null || score === undefined || isNaN(score)) {
        setTimeout(() => {
          window.location.href = 'https://chenuke.com';
        }, 3000);
        content.innerHTML = `
          <div class="error-message">
            <h2>🔍 Análisis no disponible</h2>
            <p class="sub">El informe que buscas no existe o expiró.</p>
            <p class="sub">Serás redirigido al inicio en 3 segundos...</p>
            <div class="btn-group">
              <a href="https://chenuke.com" class="back-btn">← Volver al inicio</a>
              <a href="https://chrome.google.com/webstore/detail/chenuke/hncmocmnljageejnifcmllhfophghnme" target="_blank" class="back-btn" style="background:transparent;border:1px solid var(--border);color:var(--muted);">📥 Instalar extensión</a>
            </div>
          </div>
        `;
        return;
      }

      // Asegurar score en rango 0-100
      score = Math.min(Math.max(score, 0), 100);
      level = level.toLowerCase();
      const levelColors = {
        'bajo': '#4ade80',
        'green': '#4ade80',
        'medio': '#facc15',
        'yellow': '#facc15',
        'alto': '#f87171',
        'red': '#f87171'
      };
      const levelLabels = {
        'bajo': '🟢 Bajo riesgo',
        'green': '🟢 Bajo riesgo',
        'medio': '🟡 Riesgo moderado',
        'yellow': '🟡 Riesgo moderado',
        'alto': '🔴 Alto riesgo',
        'red': '🔴 Alto riesgo'
      };
      const color = levelColors[level] || '#94a3b8';
      const label = levelLabels[level] || '—';
      const confNum = conf ? parseInt(conf, 10) : '—';

      let insightText = '';
      if (score >= 60) insightText = 'El contenido presenta señales significativas de manipulación estructural. Te recomendamos leer con cautela y verificar las fuentes.';
      else if (score >= 20) insightText = 'Se detectaron señales mixtas. El contenido tiene algunos indicadores de manipulación, pero no es concluyente.';
      else insightText = 'El contenido no presenta señales relevantes de manipulación o riesgo estructural.';

      content.innerHTML = `
        <div class="score-display">
          <div class="score-number" style="color:${color}">
            ${score}
            <span class="level-badge" style="font-size:1.2rem;font-weight:600;">${label}</span>
          </div>
          <div class="score-label">Índice de influencia estructural</div>
        </div>

        <div class="details-grid">
          <div class="detail-item">
            <div class="label">Confianza</div>
            <div class="value">${confNum}%</div>
          </div>
          <div class="detail-item">
            <div class="label">Nivel de riesgo</div>
            <div class="value" style="color:${color}">${level}</div>
          </div>
        </div>

        <div class="insight-box">
          <strong style="color:var(--text);">💡 Insight:</strong> ${insightText}
        </div>

        <div style="margin-top:1.5rem;padding:1rem;background:rgba(245,158,11,.05);border-radius:8px;border:1px dashed rgba(245,158,11,.2);">
          <p style="font-size:.9rem;color:var(--muted);">
            <strong style="color:var(--warning);">ℹ️ Nota:</strong> Este es un análisis estructural, no un fact-checker. 
            Chenuke evalúa la <strong>organización narrativa</strong> y las técnicas de influencia, no la veracidad factual.
            <br><br>
            <span style="font-size:.8rem;opacity:.7;">Usá este informe como guía, no como veredicto definitivo.</span>
          </p>
        </div>

        <div style="text-align:center;margin-top:2rem;">
          <a href="https://chenuke.com" class="back-btn">← Volver al inicio</a>
          <a href="#" onclick="window.print();return false;" class="back-btn" style="background:transparent;border:1px solid var(--border);color:var(--muted);margin-left:0.5rem;">🖨️ Imprimir / PDF</a>
        </div>
      `;
    })();
  </script>
</body>
</html>