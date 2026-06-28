
---

### 3. `02_VERSION_LOG.md.md`
```markdown
# CHENUKE – VERSION LOG

## v15.1 – Hardening & Optimización (Sesión 2)
- **Backend**: Fix de 12 bugs críticos (Event loop bloqueado, timing attacks, pesos no renormalizados, conexiones zombie DB).
- **Backend**: Cableado completo de contextos (añadido `ecommerce`, `politics`, `opinion`, `news`).
- **Backend**: ~80+ regex precompilados, type hints, logger estructurado.
- **Extensión**: Migración a inyección dinámica (eliminado permiso `tabs` invasivo).
- **Extensión**: Fix de Main Thread Blocking y fuga de memoria en `content_script.js`.
- **Extensión**: Mitigación de vulnerabilidad XSS en `popup.js`.
- **Extensión**: Fix de crash por URLs Unicode en `service_worker.js`.
- **Extensión**: Implementación de caché de sesión y notificaciones inteligentes.
- **Deploy**: Estandarización de `Procfile`, `railway.json` (healthcheck) y `requirements.txt`.

## v7.1 – Refactor a /v3/verify
- Separación clara de motores (Structural, Rhetorical, Narrative, Absence).
- Penalización contextual de uppercase.
- Clasificación formal de dominio.
- Clamp final de risk_index (0–1).

## Próxima Etapa – v8.0 (Roadmap)
- Integración OpenAI como motor complementario (Arquitectura Híbrida).
- Implementación de Autenticación JWT (RS256) y JWKS.
- Análisis semántico contextual opcional.
- Modo transparente (desglose completo del score).