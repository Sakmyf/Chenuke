\# GE SIGNALCHECK – VERSION LOG



---



\## v7.0 – 16/02/2026

\- Motor heurístico estable

\- Detección de uppercase retórico contextualizada

\- Fórmula de riesgo estabilizada

\- Endpoint `/v1/verify` consolidado

\- Safe-mode sin texto (retorno green)

\- CORS habilitado para extensión Chrome

\- Deployment estable en Railway

\- Healthcheck `/health` operativo



---



\## v7.1 – 16/02/2026

\- Refactor completo a endpoint `/v3/verify`

\- Separación clara de motores:

&nbsp; - Structural Engine

&nbsp; - Rhetorical Engine

&nbsp; - Narrative Engine

&nbsp; - Absence Engine

\- Ajuste fino de ponderaciones heurísticas

\- Penalización contextual de uppercase (no afecta dominios institucionales)

\- Clasificación formal de dominio (institutional / media / social / satire / unknown)

\- Factor correctivo para traditional\_media

\- Clamp final de risk\_index (0–1)

\- Respuesta API estructurada:

&nbsp; - trust\_score

&nbsp; - rhetorical\_score

&nbsp; - narrative\_score

&nbsp; - absence\_of\_source\_score

&nbsp; - risk\_index

&nbsp; - context\_warning

&nbsp; - details



---



\## v7.2 – En desarrollo

\- Ajuste dinámico de umbrales de riesgo

\- Preparación para módulo de análisis ampliado (modo pago)

\- Estructura lista para integrar feedback anónimo

\- Preparación para arquitectura híbrida (Heurístico + LLM opcional)



---



\## Próxima Etapa – v8.0

\- Integración OpenAI como motor complementario

\- Análisis semántico contextual opcional

\- Generación de explicación ampliada automática

\- Modo transparente (desglose completo del score)

\- Arquitectura híbrida modular



---



\## Estado actual



El sistema funciona completamente en modo heurístico determinístico.

No depende de ML.

No realiza verificación factual.

Analiza patrones estructurales del discurso digital.



