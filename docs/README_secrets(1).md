# Manejo de Secretos – App Pública (SignalCheck)

## 1. Principios generales

- La extensión cliente NO contiene secretos.
- Solo utiliza un `API_KEY` identificador público.
- Toda firma criptográfica ocurre exclusivamente en el backend.

---

## 2. Autenticación

### Modelo

- Tokens: JWT firmados con RS256.
- Duración: 15 minutos.
- Firma: Clave privada del backend.
- Verificación: Clave pública expuesta vía `/.well-known/jwks.json`.

### Flujo

1. La extensión solicita token.
2. Backend valida API_KEY.
3. Backend emite JWT firmado (RS256).
4. Extensión usa `Authorization: Bearer <token>` para `/v1/verify`.

---

## 3. Rotación de claves (Key Rotation)

### Política

- Mantener siempre 2 claves activas:
  - `KID_CURRENT`
  - `KID_OLD`

- Ventana de rollover: 24 horas.

### Comportamiento

- Tokens nuevos → firmados con `KID_CURRENT`.
- Tokens emitidos antes del cambio → válidos hasta su expiración (15 min).
- Luego del rollover → se elimina `KID_OLD`.

---

## 4. Custodia de claves

- Clave privada:
  - Nunca se expone.
  - Guardada en:
    - KMS (ideal), o
    - variables de entorno (`.env`) en entorno seguro.
- Clave pública:
  - Expuesta únicamente vía:
    - `/.well-known/jwks.json`

- No se versionan claves privadas en Git.
- `.env` debe estar en `.gitignore`.

---

## 5. Revocación

Para invalidar nuevos tokens:

1. Generar nuevo par RSA.
2. Cambiar `KID_CURRENT`.
3. Mover anterior a `KID_OLD`.
4. Reiniciar backend.

Los tokens previos expiran automáticamente en 15 minutos.

---

## 6. Procedimiento de generación de clave

### Generar par RSA (4096 recomendado)

```bash
openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:4096
openssl rsa -pubout -in private.pem -out public.pem