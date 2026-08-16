# Specification Quality Checklist: Reinicio de Agentes y Relays (LaunchAgents/LaunchDaemons)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-16
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

- Mismo criterio que el resto del proyecto para "sin detalles de
  implementación": los nombres de acción (`reiniciar_agente`,
  `reiniciar_contenedor`), rutas de evidencia (`evidencia/agente.py`,
  016) y mecanismos citados (`launchctl kickstart`, `sudoers`) son
  vocabulario de dominio de este sistema de remediación, no una fuga
  de stack técnico — mismo patrón que ya aceptó el checklist de 021
  citando `docker_monitor.py`/`docker restart`.
- **Decisión de alcance tomada al escribir este spec, no solo
  trasladada de la conversación previa**: de los 7 puntos pendientes
  resueltos en `CASUISTICA-026-acciones-reversibles.md`, este feature
  se queda solo con lo que comparte el mismo mecanismo real
  (`launchctl kickstart`, sobre `amsterdam9.*` y `com.homeassistant.*`)
  más el cableado de "Beszel (hub)". `hermes cron run` (jobs de
  Hermes) y el reinicio por SSH de `host_externo` son mecanismos
  distintos — se dejan fuera a propósito, como features separadas,
  siguiendo la misma disciplina de "una acción nueva por feature" que
  ya usaron 019 y 021, en vez de mezclar tres mecanismos distintos en
  un solo spec/plan/tasks. Si Miquel prefiere incluirlos aquí, es un
  ajuste directo al `spec.md` antes de `/speckit-clarify`.
- Los enchufes Tapo P115 y la duplicidad `Relay: X` no entran en el
  alcance de este feature en ningún escenario — quedan documentados en
  Assumptions solo como recordatorio, no como trabajo pendiente de
  esta feature.
- Sin ningún marcador `[NEEDS CLARIFICATION]`: las siete decisiones de
  alcance que hacían falta ya se cerraron con Miquel el 2026-08-15/16
  (`BRIEFING.md`, sección Feature 026, y `CASUISTICA-026-...md`) antes
  de invocar `/speckit-specify`.
- **Ampliación 2026-08-16, tras la primera versión del spec**: Miquel
  pidió añadir dos piezas de visibilidad en el dashboard (User Stories
  4 y 5, FR-017 a FR-022). Aclarado con él en dos vueltas porque mi
  primer planteamiento iba al revés de lo que pedía: "Remediaciones"
  NO es un log de eventos — es una vista de solo lectura, proyección
  de Inventario, con únicamente los componentes que tienen una acción
  real y cuál es. El log de eventos (todo el ciclo diagnosticar→
  decidir→actuar, incluidos pendiente/rechazado/fallido/cortacircuito)
  va en "Correcciones", que esta feature amplía más allá de su alcance
  actual (solo alarmas ya resueltas, desde 2026-08-10) — confirmado
  explícitamente que esa ampliación entra en el alcance de la 026, no
  se deja aparte.
- **`/speckit-clarify` (2026-08-16)**: 3 preguntas planteadas y
  resueltas — cortacircuito/aviso comparten el umbral ya existente de
  contenedores (3/6h, sin configuración nueva); la acción sigue siendo
  única (reiniciar o `sin_accion`, sin diseñar una segunda acción
  ahora, reforzando FR-002 para dejar explícito que el diagnóstico va
  primero); y Remediaciones debe distinguir cuando un
  `com.homeassistant.*` está bloqueado por falta del permiso `sudoers`
  en vez de mostrarlo como si ya funcionara (FR-023, Principio XII).
  Ningún ítem del checklist cambió de estado (ya estaba 16/16) — las
  tres respuestas se integraron como refuerzo de requisitos existentes
  (FR-009, FR-014, FR-002, FR-017) más un requisito nuevo (FR-023),
  no como corrección de un fallo de calidad.
