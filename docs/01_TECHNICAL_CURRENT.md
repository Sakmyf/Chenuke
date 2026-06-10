\# GE SIGNALCHECK – ESTADO TÉCNICO ACTUAL



---



\## 1. Arquitectura General



\### Frontend

\- Extensión Chrome (Manifest V3)

\- popup\_v2.js

\- content\_script.js

\- Inyección automática + fallback manual (chrome.scripting.executeScript)

\- Comunicación vía chrome.tabs.sendMessage

\- Header seguro: x-extension-id



---



\### Backend

\- FastAPI

\- Uvicorn

\- Deployment en Railway

\- Endpoint principal: /v3/verify

\- Healthcheck: /health

\- Control de acceso por ALLOWED\_EXTENSIONS

\- CORS habilitado para extensión



---



\## 2. Flujo de Ejecución



1\. Usuario hace click en la extensión

2\. Se obtiene la pestaña activa

3\. Se envía mensaje al content script

4\. Si falla → inyección manual

5\. Se extrae texto limpio (máx 15.000 caracteres)

6\. Se envía al backend:



{

&nbsp; "url": "...",

&nbsp; "text": "..."

}



7\. Backend procesa y devuelve:



\- trust\_score

\- rhetorical\_score

\- narrative\_score

\- absence\_of\_source\_score

\- risk\_index

\- context\_warning

\- details (signals)



---



\## 3. Motor de Análisis (Heurístico)



\### Structural Engine

\- Clasificación de dominio:

&nbsp; - institutional

&nbsp; - traditional\_media

&nbsp; - satire

&nbsp; - social

&nbsp; - shortener

&nbsp; - unknown

\- Trust base: 0.45

\- Ajuste HTTPS: +0.05

\- Penalización texto corto: −0.05

\- Normalización dominio (remueve www)

\- Lookup eficiente mediante sets



---



\### Rhetorical Engine

\- Detección de alarmismo explícito

\- Carga emocional fuerte

\- Ratio upper/letters

\- Penalización contextual:

&nbsp; - No afecta institutional ni traditional\_media

\- Umbrales:

&nbsp; - 0.40 → 0.15

&nbsp; - 0.30 → 0.08



---



\### Narrative Engine

\- Detecta narrativa no verificable

\- Detecta dramatización

\- Detecta declaraciones sin fuente visible

\- Si satire → score 0



---



\### Absence of Source Engine

Detecta presencia de:

\- http(s)

\- www

\- “según”

\- “de acuerdo con”

\- “fuente”



Si no hay referencias → +0.25



---



\## 4. Fórmula de Riesgo



risk\_index =

&nbsp; (0.30 \* rhetorical)

\+ (0.25 \* narrative)

\+ (0.20 \* absence)

\+ (0.25 \* (1 - trust))



Ajustes:

\- traditional\_media → factor 0.85

\- social → mínimo 0.35

\- Clamp final 0–1



---



\## 5. Estado de Madurez



Arquitectura:

\- Modular

\- Determinística

\- Escalable

\- Separación clara de responsabilidades



No es:

\- Fact-checker

\- Sistema ML

\- Detector automático de “verdad”

\- Sistema de certificación científica



Es:

\- Motor heurístico de análisis estructural del discurso digital.



