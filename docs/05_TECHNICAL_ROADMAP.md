\# Roadmap seguridad → app pública

Sprint 1 (Beta privada):

\- \[ ] Implementar /v1/auth/token (JWT 15 min, RS256, KID actual)

\- \[ ] Middleware verify\_jwt en /v1/verify

\- \[ ] /.well-known/jwks.json con claves públicas

\- \[ ] Rate-limit simple en memoria

\- \[ ] Extensión: flujo de “pedir token” y usar Authorization: Bearer



Sprint 2 (Público):

\- \[ ] Rollover de claves (KID y OLD\_KID, 24 h)

\- \[ ] CORS restringido y WAF/Cloudflare

\- \[ ] Logs/alertas 401/429

\- \[ ] Lista de revocación de API\_KEY



