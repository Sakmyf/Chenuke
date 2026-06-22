SignalCheck Engine v15.1
Versión limpia y optimizada del MVP. Motor de análisis estructural heurístico (no fact-checker).

Decisiones aplicadas
positivo = riesgo en todos los módulos de análisis.
Estados únicos de salida: bajo, medio, alto.
Clase base única: RuleResult.
Endpoint vigente: /v3/verify.
Módulos de Analysis interconectados con weight_engine y classify_context.
Estructura del Proyecto
backend/  __init__.py  app.py              # API FastAPI (Entry point del backend)  engine.py  weight_engine.py  source_analyzer.py  context_classifier.py  content_filter.py  confidence_score.py  database.py  models.py  Analysis/            # 15 módulos de reglas heurísticas    __init__.py    rules_types.py    urgency.py    ... (otros módulos)extension/             # Extensión de Chrome (Manifest V3)  manifest.json  popup.html  popup.css  popup.js  content_script.js  service_worker.js  icons/
🚀 Comandos y Deploy
1. Backend (Local)
bash

# Instalar dependencias
pip install -r requirements.txt

# Arrancar servidor local
uvicorn backend.app:app --reload --port 8000
2. Extensión (Local)
Abrir chrome://extensions/ en el navegador.
Activar "Modo desarrollador" (esquina superior derecha).
Click en "Cargar descomprimida".
Seleccionar la carpeta extension/.
3. Deploy en Railway / PaaS
El proyecto incluye un railway.json y Procfile configurados.
El comando de arranque en producción estándar es:

bash

uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4
(Asegúrate de que la variable de entorno PORT esté disponible en tu plataforma de deploy).