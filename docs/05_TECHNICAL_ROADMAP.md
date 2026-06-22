Roadmap seguridad → app pública
NOTA: Este documento describe el roadmap de seguridad planificado para la versión pública (v8.0). El estado actual (v15.1) utiliza autenticación simple mediante Headers (x-extension-id y x-pro-token).

Sprint 1 (Beta privada):

 Implementar /v1/auth/token (JWT 15 min, RS256, KID actual)
 Middleware verify_jwt en /v3/verify
 /.well-known/jwks.json con claves públicas
 Rate-limit simple en memoria
 Extensión: flujo de “pedir token” y usar Authorization: Bearer
Sprint 2 (Público):

 Rollover de claves (KID y OLD_KID, 24 h)
 CORS restringido y WAF/Cloudflare
 Logs/alertas 401/429
 Lista de revocación de API_KEY