"""diagnostico — Diagnóstico de Episodios (Frente 2, sin remediación).

Congela evidencia real de un episodio — de contenedor (en vivo o de
`restart_history`), de disco (feature 009, en vivo o de un momento
pasado concreto), de Home Assistant (feature 010: un check de entidad,
de recorder corrupto, o de disponibilidad de la API, en vivo o de un
momento pasado concreto), de backup (feature 011: el log de una
ejecución de `backup_diario_nvme.sh`, en vivo o de un momento pasado
dentro de la ventana de retención), de relay `socat` (feature 012: en
vivo con detalle real por relay, o en diferido con evidencia agregada
— nunca cuál relay concreto, esa información no existe), del propio
inventario de cobertura (feature 013: una brecha real de un
componente, en vivo en la ejecución más reciente o en diferido en una
ejecución pasada concreta — nunca de tipo `condicion_incumplida`, que
duplicaría el origen `ha`), de un host físico externo vigilado por
Beszel (feature 014: Uptime Kuma o AdGuard Home, en vivo con el estado
ya calculado, o en diferido con la densidad de muestras de rendimiento
que reportó al hub — nunca presentando la mera ausencia como una caída
confirmada), del propio hub de Beszel (feature 015: en vivo si todos
sus sistemas registrados dejaron de reportar a la vez, o en diferido
con la densidad de muestras de cada sistema en una ventana — nunca
presentando una ausencia parcial como si el hub entero estuviera
caído), o de un LaunchAgent (feature 016: si tiene un proceso activo, y
su último código de salida — **solo en vivo**, sin ningún modo
diferido: no existe ninguna fuente de evidencia histórica real para
LaunchAgents) —, pide a DeepSeek varias hipótesis de causa probable ya
contrastadas contra esa evidencia, y registra cada hipótesis y la
conclusión final. No ejecuta ni propone ninguna acción correctiva
sobre el homelab — eso es explícitamente fuera de alcance (spec.md
FR-012, FR-013a de 007; FR-008 de 009, 010, 011, 012, 013, 014, 015 y
016).

Con el feature 016 se cierran los **nueve** orígenes de la Central de
Alarmas (feature 006-central-alarmas) que este proyecto se propuso
generalizar — no queda ningún origen restante. Ver
specs/007-diagnostico-episodios/, specs/009-diagnostico-discos/,
specs/010-diagnostico-ha/, specs/011-diagnostico-backups/,
specs/012-diagnostico-relays/, specs/013-diagnostico-inventario/,
specs/014-diagnostico-hosts-externos/,
specs/015-diagnostico-hub-beszel/ y specs/016-diagnostico-agentes/
para spec, plan y contratos de cada uno.
"""
