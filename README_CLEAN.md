# SignalCheck Clean v15.0

Versión limpia del MVP actual.

Decisiones aplicadas:
- `positivo = riesgo` en todos los módulos.
- Estados únicos: `bajo`, `medio`, `alto`.
- Clase base única: `RuleResult`.
- Endpoint vigente: `/v3/verify`.
- El motor sigue siendo heurístico, no fact-checker.

## Estructura

```txt
backend/
  app.py
  engine.py
  Analysis/
    rules_types.py
    urgency.py
    promises.py
    emotions.py
    polarization.py
    misinformation.py
    scientific_claims.py
    narrative_patterns.py
    hypothetical.py
    detect_uncertainty.py
    contradictions.py
    credibility.py
    authority.py
    commercial_risk.py
    structural.py
extension/
  manifest.json
  popup.html
  popup.css
  popup.js
  content_script.js
  service_worker.js
  icons/
```

## Local

```bash
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000
```

## Chrome

Cargar carpeta `extension/` en modo desarrollador.
