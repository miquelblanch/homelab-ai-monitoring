# Specification Quality Checklist: Diagnóstico de Episodios (Frente 2, sin remediación)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`.
- Sin marcadores [NEEDS CLARIFICATION]: la decisión más importante
  (motor de hipótesis — DeepSeek, con cortacircuitos de gasto diario en
  vez de RAG) ya se resolvió con Miquel en conversación previa a este
  comando, y quedó registrada en `BRIEFING.md` ("Feature 007 — material
  de partida") antes de escribir este spec.
- FR-008 nombra "DeepSeek" y FR-009 "tokens" — son excepciones
  deliberadas a "sin tecnología en el spec": la elección del proveedor
  de LLM es en sí misma una decisión de producto ya tomada explícitamente
  con Miquel (coste, datos saliendo de la máquina, Principio X), no un
  detalle de implementación que debería vivir solo en el plan.
- `/speckit-clarify` (2026-08-10) resolvió 3 ambigüedades reales no
  marcadas en el spec original, detectadas en el escaneo de cobertura:
  alcance del episodio (solo contenedores, no las otras 9 alarmas de
  la Central de Alarmas — nuevo FR-001 acotado), disparo del
  diagnóstico (bajo demanda, nunca automático — nuevo FR-015), e
  identidad del episodio para la reproducibilidad de FR-002 (snapshot
  de evidencia congelado al elegir diagnosticar, no el estado en vivo).
  Todos los ítems de la checklist siguen en verde; sin regresiones.
- Pendiente de `/speckit-plan`: qué evidencia exacta se reúne por
  episodio de contenedor, cómo se garantiza que el LLM no rompa la
  reproducibilidad de FR-002 pese a su no-determinicidad típica (Edge
  Cases), el formato de persistencia del snapshot (FR-002) y del
  acumulado de gasto diario (FR-009).
- 2026-08-10 (post-clarify): Miquel planteó quitar la distinción
  crítico/no-crítico y dar remediación automática al 100% a todos los
  contenedores, incluidos los de `docker_monitor.py`/`SOUL.md` de
  Bautista — se descartó por chocar con el Principio V (NO NEGOCIABLE)
  de la constitución y con la propia lista de aprobación explícita ya
  vigente. Se mantiene la lista crítica sin cambios. Lo que sí se
  reforzó en el spec: FR-013 pasó de "puede diagnosticar" (permisivo) a
  "DEBE diagnosticar" (obligatorio) para episodios de contenedores
  críticos, con FR-013a separando explícitamente la prohibición de
  actuar sobre ellos, y un nuevo escenario de aceptación (US1,
  escenario 4) que lo hace comprobable.
