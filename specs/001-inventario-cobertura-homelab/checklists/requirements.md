# Specification Quality Checklist: Inventario Sistemático de Cobertura del Homelab

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-07
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

- Ninguna pregunta [NEEDS CLARIFICATION]. Seis decisiones de alto impacto se
  resolvieron con Miquel antes de cerrar el spec (2026-08-07):
  1. El inventario es repetible, y Miquel lo relanza también como
     herramienta de descubrimiento deliberado, no solo para detectar altas y
     bajas (FR-013, User Story 3 escenario 3).
  2. Dentro de Home Assistant, la granularidad baja hasta la entidad
     individual (FR-003), no se queda en el nivel de integración. Un portal
     específico de HA queda explícitamente fuera de este spec porque
     contradice la decisión ya escrita en `BRIEFING.md` de no construir un
     dashboard nuevo (FR-018, Assumptions) — se deja anotado como candidato a
     un feature futuro.
  3. El inventario no se limita a Docker en el Mac Mini: incluye los hosts
     físicos que alojan Uptime Kuma y AdGuard Home (FR-005), cerrando dentro
     del propio inventario el Caso 3 de `BRIEFING.md` ("Beszel no vigila bien
     lo que vigila"). Identificados por el software que alojan, no por IP,
     por la política de saneado del repo.
  4. Dentro de Home Assistant, el spec no enumera dispositivos,
     automatizaciones ni la antena Zigbee por nombre (FR-003, Assumptions):
     hacerlo sería la misma lista elegida a mano que el Principio XIII
     prohíbe. La redacción de FR-003 se amplió para cubrir cualquier dominio
     de entidad sin enumerarlas; el detalle concreto lo saca la primera
     ejecución del inventario, no el spec.
  5. El agente Hermes/Bautista (proceso nativo, no Docker) y el canal de
     Telegram entran como componentes propios y separados (FR-006), porque
     un fallo silencioso de Telegram invalidaría la entrega de casi todas
     las demás alertas del sistema — riesgo concentrado, marcado aparte en
     Edge Cases, no como una brecha más entre otras cuarenta.
  6. El inventario debe poder lanzarse a demanda, no solo en una ventana
     programada (FR-014); el mecanismo concreto (manual, programado, o un
     botón futuro en el dashboard que ya existe) se deja para el plan.

- **`/speckit-clarify` (2026-08-07)**: 3 preguntas formales, todas resueltas
  sin llegar al límite de 5. Ninguna reabrió un ítem del checklist (sigue
  16/16); las tres afinaron requisitos ya existentes con un criterio
  concreto y comprobable:
  1. Identidad de un componente entre ejecuciones cuando cambia de nombre
     → emparejar por identificador estable de la fuente cuando exista
     (FR-015, Edge Cases, Key Entities).
  2. Retención de ejecuciones pasadas del inventario → todas, sin límite de
     tiempo (FR-017, Key Entities).
  3. Umbral de caducidad de una declaración de estado esperado (Principio
     III) → 90 días de calendario desde la última revisión confirmada
     (FR-007, Key Entities).
