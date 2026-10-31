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
4. `BARRIDO-xxxx-xx-xx.md` — los barridos previos en busca de problemas, errores 
   o elementos no monitorizados.


## El problema, en una frase

El objetivo **no** es resolver un misterio concreto ni una lista fija de casos
conocidos. Es un sistema de monitorización que cubra **sistemáticamente** todo
el homelab — Principio XIII de la constitución — y que, para cada problema real
que detecte, o lo corrija solo (si ya está diagnosticado y la acción es segura y
reversible) o avise a Miquel con contexto suficiente y con posibles soluciones
para que lo resuelva él.

Cuatro casos motivaron el proyecto, encontrados por casualidad en momentos
distintos — no son la lista de tareas, son la prueba de que el problema es
sistémico (ver `BRIEFING.md` para el detalle de cada uno):

1. Un contenedor (`beszel`) acumuló 49 reinicios automáticos sin causa raíz
   conocida. El **criterio de muerte** ya se comprobó (5 episodios reales de
   `restart_history`) y **no lo pasa**: 3 de 5 no tienen ningún dato más allá
   de la marca de tiempo. No se persigue esta causa raíz como objetivo — se usa
   como evidencia de que hace falta mejor cobertura, no como algo a resolver.
2. El barrido del 01-08-2026: 11 problemas reales, 0 visibles en el dashboard.
   Causas conocidas y escritas en `BARRIDO-2026-08-01.md`.
3. Beszel —la propia herramienta de monitorización— no vigila bien 2 de los 3
   sistemas que tiene a su cargo. Investigado en `BARRIDO-2026-08-07.md`: el
   síntoma original ya no se reproducía, pero quedaba un hueco real (si el
   hub deja de reportar para los tres a la vez, nada lo distingue de "los
   tres están bien"). Cerrado por `specs/003-latidos-beszel-calendario/`
   (User Story 2): latido propio derivado de la antigüedad de `updated` de
   los tres sistemas, no solo su `status`.
4. Los recordatorios de Tareas/Calendario de Nextcloud no llegan por Telegram.
   Investigado en `BARRIDO-2026-08-07.md`: encontrado y arreglado un fallo
   silencioso real en `recordatorios_hoy()` (un `""` que significaba dos
   cosas distintas). Cerrado por `specs/003-latidos-beszel-calendario/`
   (User Story 1): latido propio de `fermin-calendar.sh` (entonces
   `bautista-calendar.sh`: el agente Hermes se llama Fermín desde el
   2026-10-29).

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

- **Cobertura sistemática, no lista de casos.** No se trata de arreglar los
  cuatro casos conocidos uno por uno — se trata de recorrer todo lo que compone
  el homelab y comprobar, de cada pieza, si tiene estado esperado declarado, si
  se vigila, y si un fallo llegaría al dashboard (Principio XIII).
- **No reemplaza `docker_monitor.py`.** Sigue vigilando contenedores y es el
  mecanismo independiente de reserva. Desde el feature 021, la decisión de
  reiniciar un contenedor la toma la remediación de este repo (con evidencia y
  verificación); el modelo es OpenAI con DeepSeek de reserva desde el 2026-10-01.
- **Contenedores críticos:** desde la constitución 3.0.0 (2026-10-11) admiten modo
  automático como los demás. NEVER_RESTART está vacío desde el 2026-10-31 (su
  último miembro, `frigate`, va siempre en marcha).
- **Repo público, saneado.** Se nombra el software, no la topología: nada de
  nombres de entidades ligadas a dispositivos de seguridad física, IPs,
  credenciales. Ver la decisión "Repositorio público" en `BRIEFING.md`.
- **Reparto de trabajo:** ver `METODO.md`. Por defecto, Claude prepara material y
  revisa; Miquel ejecuta los comandos `speckit-*`.
