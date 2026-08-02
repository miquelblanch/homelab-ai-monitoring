# Homelab Diagnostic Agent — Briefing para Claude Code

> Proyecto de aprendizaje de Spec-Driven Development (SDD) con Spec Kit. Construye un
> agente de diagnóstico (LangGraph) para el homelab de Miquel: detecta errores,
> intenta corregirlos dentro de una lista cerrada de acciones reversibles, y si no
> puede, reporta a Miquel.

## Antes de nada

Este repo **no** contiene el `CLAUDE.md` general del homelab (vive un nivel por
encima, fuera de este repo, y es privado). Lo que hay aquí es autocontenido y público.

Lee, en este orden:

1. `.specify/memory/constitution.md` — los no negociables del proyecto. Fuente de
   autoridad: una divergencia entre lo que dice y lo que hace el código es un
   defecto del código, no de la constitución.
2. `BRIEFING.md` — el problema, la premisa, qué está en alcance y qué no. No es la
   especificación; es lo que se sabe antes de escribirla.
3. `METODO.md` — el reparto de trabajo: **Miquel ejecuta** todas las skills y
   comandos de Spec Kit; **Claude revisa** y aporta material y criterios antes de
   cada paso. No ejecutes tú las skills `speckit-*` salvo que se te pida
   explícitamente lo contrario.
4. `BARRIDO-2026-08-01.md` — el barrido que originó la segunda premisa del
   proyecto (cobertura del dashboard).
5. `PRINCIPIOS.md` — material de entrada histórico de la constitución. Ya
   incorporado; queda como registro, no como fuente viva.

## El problema, en una frase

Dos premisas distintas, con reglas distintas (ver `BRIEFING.md` para el detalle):

- **Primera** (sin diagnosticar): un contenedor acumuló 49 reinicios automáticos sin
  causa raíz conocida. Necesita pasar el **criterio de muerte** (5 episodios,
  ¿basta la evidencia para distinguirlos?) antes de escribir código de agente.
- **Segunda** (ya diagnosticada): el dashboard (`http://homelab.amsterdam9.home/`)
  no refleja 11 problemas reales encontrados en el barrido — por deduplicación mal
  hecha y ausencia de estado esperado, no por falta de señal. No necesita el
  criterio de muerte: la causa ya se conoce.

## Datos disponibles para el agente

**Base de datos:** `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/homelab.db`
(fuera de este repo, en la máquina del homelab — no versionada aquí)

| Tabla | Contenido | Utilidad |
| --- | --- | --- |
| `restart_history` | 83 eventos reales, mar–may 2026, con `result` | Conjunto de evaluación para el criterio de muerte |
| `container_metrics` | Detalle a 5 min: CPU, memoria, estado, salud. Retención 30 días | Contexto inmediato de un episodio |
| `container_metrics_hourly` | Medias horarias, permanentes, desde 2026-04-17 | Contexto histórico y detección de anomalías |
| `disk_metrics` / `disk_metrics_daily` | Igual, para los tres discos | Correlación con eventos de disco |
| `migrations` | Migraciones aplicadas | Idempotencia |

**Fuentes adicionales:** logs de LaunchAgents en `~/Library/Logs/`, `docker inspect`,
`docker logs`, estado de relays y tareas programadas.

**Por qué importa poder leer esto en diferido:** el agente debe poder ejecutarse
contra un episodio histórico, no solo en vivo — si no, no hay forma de comparar dos
versiones del grafo sobre el mismo caso ni de medir sin esperar a que algo se
rompa. Es el Principio XI de la constitución (Reproducibilidad Diferida).

## Reglas operativas rápidas

- **No reemplaza `docker_monitor.py`.** Sigue siendo quien reinicia contenedores.
  El agente añade diagnóstico y, para causas ya diagnosticadas, remediación
  reversible — nunca sustituye la remediación existente.
- **Ninguna acción sobre contenedores críticos** sin aprobación humana explícita
  (lista del monitor, ver constitución).
- **Repo público, saneado.** Se nombra el software, no la topología: nada de
  nombres de entidades ligadas a dispositivos de seguridad física, IPs,
  credenciales. Ver la decisión "Repositorio público" en `BRIEFING.md`.
- **Reparto de trabajo:** ver `METODO.md`. Por defecto, Claude prepara material y
  revisa; Miquel ejecuta los comandos `speckit-*`.
