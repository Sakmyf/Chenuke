# ORCHESTRATOR_SPEC.md — Orquestador Ético multi-IA

Este documento describe el diseño del Orquestador Ético multi-IA utilizado por el backend para analizar contenido, consultar múltiples modelos y producir una clasificación responsable.

---

## 1. Objetivo

Utilizar varias IA y fuentes de información para evaluar afirmaciones (claims) presentes en un contenido, sin delegar completamente la decisión en ningún modelo individual, y manteniendo siempre los principios definidos en `ETHICS.md`.

---

## 2. Entradas y salidas

### 2.1 Input al Orquestador

```json
{
  "url": "https://ejemplo.com/post",
  "title": "Título",
  "text": "Contenido relevante...",
  "locale": "es-AR",
  "evidence_sources": [
    {"url": "..."},
    {"url": "..."}
  ]
}
```

### 2.2 Output del Orquestador hacia el Fusor Ético

```json
[
  {
    "claim": "Texto del claim",
    "evidence_strength": "fuerte | media | debil | desconocida",
    "consensus": "amplio | parcial | dividido | marginal",
    "risk_if_wrong": "alto | medio | bajo",
    "label": "respaldado | en_debate | especulativo | contradicho",
    "sources_used": [
      {"url": "...", "type": "estudio | noticia | opinion", "weight": 0.8}
    ]
  }
]
```

El Orquestador no asigna el color final; solo estructura la evidencia.

---

## 3. Componentes internos

1. **Claim Extractor (IA1)**
   - Modelo especializado en identificar hasta N afirmaciones clave del texto.
   - Restricciones:
     - Sin inventar claims.
     - Debe citar fragmentos del texto original.

2. **Evidence Evaluator (IA2)**
   - Recibe claims + fuentes.
   - Evalúa para cada claim:
     - coherencia entre fuentes,
     - presencia de evidencia empírica,
     - concordancia o conflicto entre fuentes consultadas.
   - Devuelve `evidence_strength`, `consensus`, `label` preliminar.

3. **Risk Assessor (IA3)**
   - Estima el impacto potencial de que un claim sea falso o engañoso.
   - Clasifica `risk_if_wrong` en alto/medio/bajo.

4. **Bias & Integrity Checker (IA4)**
   - Revisa:
     - si las evaluaciones favorecen injustamente una sola línea ideológica,
     - si falta considerar fuentes relevantes,
     - si se están usando términos absolutos sin sustento.

5. **Validator Ético**
   - Componente determinista que:
     - verifica formato,
     - descarta outputs que contradigan `ETHICS.md`,
     - marca como inválidas respuestas que sugieran daño, discriminación o violación de privacidad.

---

## 4. Protocolo de consulta a múltiples IA

1. Todas las consultas a modelos externos se hacen con:
   - datos minimizados,
   - sin identificadores personales,
   - solo texto necesario para análisis.

2. Las IAs externas se consideran:
   - fuentes auxiliares,
   - no autoridades definitivas.

3. El Orquestador compara respuestas entre modelos:
   - si hay discrepancias fuertes → aumenta la probabilidad de `en_debate` o `especulativo`,
   - nunca fuerza `respaldado` cuando hay conflicto significativo entre modelos o fuentes.

4. Cualquier sugerencia de un modelo que implique:
   - violar principios éticos,
   - recomendar censura injustificada,
   - promover daño,
   se descarta y se registra internamente.

---

## 5. Integración con el Fusor Ético

El Fusor Ético toma la lista de claims evaluados y aplica reglas determinísticas, por ejemplo:

- Si predominan claims `respaldado` con `evidence_strength=fuerte` → 🟢.
- Si hay mezcla relevante de `respaldado` y `contradicho`/`en_debate` → 🟡.
- Si la mayoría es `especulativo`, con bajo riesgo → ⚪.
- Si predominan `contradicho` con `risk_if_wrong=alto` → 🔴.

Estas reglas deben estar documentadas y versionadas.

---

## 6. Manejo de incertidumbre y abstención

Si el Orquestador:

- no encuentra suficiente evidencia,
- recibe respuestas inconsistentes de las IA,
- detecta que cualquier clasificación sería engañosa,

entonces debe señalizarlo explícitamente para que el Fusor Ético pueda:

- marcar el contenido como `especulativo` o `en_debate`, o
- recomendar abstención parcial (no asignar color fuerte).

---

## 7. Logs Éticos

El Orquestador registrará únicamente:

- hashes de URL,
- timestamps,
- tipo de decisión (respaldado/en_debate/especulativo/contradicho/abstención),
- indicadores técnicos (sin datos personales).

Objetivo: auditoría y mejora continua, no rastrear usuarios.

---

Este diseño permite que el sistema utilice múltiples IA con inteligencia y prudencia, manteniendo el control humano y ético en el centro de la toma de decisiones.
