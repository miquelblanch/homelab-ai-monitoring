# Research — Generalizar el Diagnóstico a los Backups

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un cuarto valor real, `'backup'`,
sin ningún `ALTER TABLE` — misma situación que ya resolvió research.md
§1 de 010: la columna es TEXT libre desde la migración de 009, sin
ninguna restricción `CHECK`.

**Rationale**: cualquier string es válido desde la migración de 009;
documentar el valor nuevo aquí y en `model.py`/`data-model.md` basta,
no hace falta ningún cambio de esquema.

## §2 — Identificador de un episodio de backup: el momento, no un nombre

**Decisión**: a diferencia de discos (`label`, 009 §2) o HA (`check_id`,
010 §2), un episodio de backup no tiene ningún nombre que elegir — solo
existe una serie (el rsync nocturno de `backup_diario_nvme.sh`). El
identificador es directamente el momento de la ejecución, tomado del
propio nombre del fichero de log
(`backup_YYYY-MM-DD_HH-MM-SS.log`) — no hace falta ningún argumento
adicional para `--backup-vivo`, y `--backup-historico` recibe
`MOMENTO_ISO` a secas, sin el prefijo `LABEL@`/`CHECK_ID@` que sí
necesitan discos y HA para desambiguar entre varias series.

**Rationale**: introducir un `LABEL@`/`CHECK_ID@` para una sola serie
sería una convención copiada sin necesidad real — el propio nombre del
fichero de log ya es el identificador natural y único.

## §3 — Evidencia del log: extracción acotada, nunca el fichero crudo

**Hallazgo de la investigación previa a planificar**: el log más
grande de los 8 reales retenidos (`backup_2026-08-07_02-00-02.log`)
tiene 9.878 líneas y pesa 955 KB. Inspeccionado en vivo: la inmensa
mayoría son líneas de `rsync --itemize-changes` (una por cada fichero
tocado esa noche — esa noche, 6.269 creados + 2.605 borrados según el
propio bloque de estadísticas), sin ningún valor diagnóstico por sí
solas. Enviar el log completo repetiría, de entrada, el mismo problema
real que ya costó 280.454 tokens en 010 (research.md §13 de 010, caso
`sal_nivel`) — aquí no hay que esperar a un hallazgo en vivo para
saberlo, ya está comprobado contra los logs reales antes de escribir
ningún código.

**Decisión**: `_parsear_log_backup()` extrae solo piezas acotadas del
texto del log, nunca el fichero completo:

| Pieza | Qué es | Tamaño |
|---|---|---|
| `dumps` | Líneas de estado de cada dump de BD (`✅ X OK` / `⚠️ X falló`) | Fija, ~9-11 líneas |
| `rsync_stats` | El bloque `--stats` de rsync (Number of files, Total file size, Total transferred, speedup...) | Fija, ~12 líneas, independiente de cuántos ficheros cambiaran |
| `resumen_final` | La línea `RESUMEN FINAL` (duración + código de rsync ya interpretado por el propio script) | 1 línea |
| `rsync_estado` | `"ok"` o `"error"`, parseado de la propia clasificación que ya hace `backup_diario_nvme.sh` (0/24=ok, 23/otros=error) | 1 valor |
| `anomalias` | Líneas que coinciden con patrones de error reales de rsync/el script (`rsync:`, `rsync error:`, `IO error`, `Permission denied`) en cualquier punto del log, **excluidas las que ya coinciden con el patrón de `dumps`** (hallazgo I1 de `/speckit-analyze`, 2026-08-12: `⚠️`/`❌` también marcan un dump fallido, y sin esta exclusión esa misma línea se contaba dos veces, gastando presupuesto de anomalías en contenido ya presente en `dumps`), acotadas a `BACKUP_ANOMALIA_MAX_LINEAS` (30) — igual que `HA_HISTORIAL_MAX_ENTRADAS` en 010, límite por diseño desde el principio, no una corrección posterior | Máximo 30 líneas |

La lista de ficheros cambiados (`--itemize-changes`) en sí **nunca**
se incluye — ni completa ni resumida por conteo — porque no aporta
señal diagnóstica: un fichero de música renombrado y otro con un
permiso corrupto tienen la misma pinta en esa lista sin contexto
adicional, y cualquier error real de E/S por fichero ya aparece en las
líneas de anomalía capturadas aparte.

**Tamaño resultante**: para el log más grande real (955 KB), la
evidencia extraída se queda en unas pocas decenas de líneas —
comparable en orden de magnitud al prompt ya validado con éxito en 010
tras el arreglo de `sal_nivel` (~1.900 tokens), muy lejos de los
280.454 tokens del caso sin acotar.

**Alternativas consideradas**: enviar solo un resumen numérico (número
de líneas de error, sin su texto). Rechazada — pierde exactamente el
detalle que permite formular una hipótesis concreta ("Permission
denied" apunta a un problema de permisos, no solo a "hubo un error");
30 líneas de texto real siguen siendo baratas y mucho más útiles que
un conteo.

## §4 — Principio X: verificado explícitamente que no hay credenciales en el log

**Decisión**: antes de diseñar cualquier mecanismo que envíe contenido
de estos logs a DeepSeek, se comprobó contra los logs reales que
`rsync --itemize-changes` solo emite ruta + banderas de cambio, nunca
contenido de fichero. El directorio `.secrets/` del propio homelab
aparece en el log (como entrada de directorio, `.d..t.......
homelab/.secrets/`) porque rsync lo sincroniza igual que cualquier
otra carpeta — pero nunca aparece el contenido de ningún `.env`, solo
su existencia como ruta. El propio `backup_diario_nvme.sh` ya evita
deliberadamente escribir la contraseña de MariaDB en el log (comentario
del script: la resuelve el propio contenedor por variable de entorno,
nunca se interpola en el comando que se registra).

**Verificación adicional**: la extracción de §3 ni siquiera necesita
apoyarse en esta garantía de rsync — ninguna de las piezas extraídas
(`dumps`, `rsync_stats`, `resumen_final`, `anomalias`) proviene de la
lista de ficheros itemizados, así que una ruta con `.secrets/` no
tendría forma de colarse en la evidencia enviada a DeepSeek aunque
`rsync` sí expusiera contenido (no lo hace).

**Rationale**: mismo criterio ya exigido por research.md §7 de 007 —
justificar caso por caso qué sale de la máquina, no darlo por sentado.

## §5 — Encontrar el log correcto: vivo (el más reciente) y diferido (por cercanía al momento)

**Decisión**:
- **En vivo**: el fichero `backup_*.log` más reciente en
  `/Volumes/FastData/homelab/logs/`, por orden lexicográfico del
  nombre (el formato `YYYY-MM-DD_HH-MM-SS` ya ordena cronológicamente
  sin necesidad de leer `mtime`).
- **En histórico**: se parsea el `MOMENTO_ISO` embebido en cada nombre
  de fichero y se toma el log más cercano a `MOMENTO_ISO`, dentro de
  una tolerancia `VENTANA_BACKUP_HORAS = 12` — igual de amplia que la
  ventana de entidad de HA (010 §6) y por la misma razón: solo hay una
  ejecución por noche, así que basta con señalar la fecha aproximada
  sin acertar la hora exacta (`02:00`) para que resuelva al log
  correcto.

**Rationale**: reutiliza el mismo patrón de "ventana de tolerancia" que
ya usan `disk_metrics_near()` (009) y el historial de entidad de HA
(010 §6) — aplicado aquí sobre nombres de fichero en vez de filas de
una tabla, porque no hay tabla.

**Alternativas consideradas**: exigir el timestamp exacto del nombre
del fichero de log como identificador (sin tolerancia). Rechazada —
obligaría a Miquel a mirar primero el listado de `logs/` para copiar el
nombre exacto antes de poder diagnosticar nada; una ventana de
tolerancia amplia no tiene ningún coste real porque solo hay una
ejecución por noche.

## §6 — `_homelab_bridge.py` no cambia: no hace falta puentear ningún script

**Decisión**: a diferencia de contenedores (`docker_monitor.py`),
discos (`homelab.db` vía `homelab_secrets`) y HA (`ha_monitor.py`),
este feature no necesita leer ningún módulo Python externo en vivo —
toda la evidencia son ficheros de texto ya escritos en
`/Volumes/FastData/homelab/logs/`, leídos directamente con `pathlib` de
la librería estándar. `_homelab_bridge.py` queda sin cambios.

**Rationale**: el bridge existe para leer el *estado en memoria* de
scripts externos (listas `CHECKS`, `CRITICAL`, resultados ya
calculados); aquí no hay ningún estado en memoria que leer, solo
ficheros — no hay ninguna razón para introducir una dependencia nueva
donde ya basta con `pathlib`.

## §7 — Prompt de DeepSeek: generalizado una cuarta vez

**Decisión**: `_PROMPT_INSTRUCCIONES` (`deepseek.py`) cambia de nuevo
solo su frase de encuadre: añade "...o un backup nocturno fallido o
parcial (rsync, o algún dump de base de datos)" a la lista ya
existente de contenedor/disco/HA. El resto del prompt no cambia.

**Rationale**: mismo argumento que 009 §5 y 010 §8 — cambiar solo la
frase de encuadre es el cambio mínimo que generaliza sin arriesgar una
regresión sobre invariantes ya validados.

**`es_critico` para backup — siempre `False`**: igual que discos y HA
— no existe concepto de "backup crítico" (spec.md Assumptions).

## §8 — CLI: dos flags nuevos, uno de ellos sin argumento

**Decisión**:

```
python3 -m diagnostico.cli congelar --backup-vivo
python3 -m diagnostico.cli congelar --backup-historico MOMENTO_ISO
```

`--backup-vivo` es `action="store_true"` — no lleva argumento, a
diferencia de `--disco-vivo LABEL`/`--ha-vivo CHECK_ID`, porque no hay
nada que elegir entre varias series (research.md §2). `diagnosticar`,
`mostrar` y `--selftest` no cambian su firma.

**`MOMENTO_ISO` — misma convención de zona horaria que 009/010**: hora
local sin marca de zona, comparada directamente contra el timestamp
embebido en el nombre del fichero de log — sin conversión a UTC.

## §9 — Sin log encontrado: se congela el momento pedido, no el momento de congelar (corrección real, 2026-08-12)

**Hallazgo real de validación en vivo**: la primera versión de
`_congelar_backup()` usaba `datetime.now()` como `componente`/ventana
cuando no se encontraba ningún log — tanto en vivo (razonable, "ahora"
es lo que se pidió) como en diferido (**no** razonable: pedir
`--backup-historico "2020-01-01T02:00:00"` mostraba en `mostrar` la
hora a la que se ejecutó `congelar`, no 2020, engañoso de leer después
sin volver a mirar los argumentos originales).

**Decisión**: `_congelar_backup()` recibe explícitamente
`momento_solicitado` (el momento pedido: `datetime.now()` para
`--backup-vivo`, el argumento tal cual para `--backup-historico`) y lo
usa como `componente`/ventana solo cuando no hay ningún log que
encontrar — cuando sí lo hay, se sigue usando el momento real del
propio log (más preciso que el momento pedido, que puede diferir en
minutos dentro de la ventana de tolerancia).

**Validado tras el arreglo**: `congelar --backup-historico
"2020-01-01T02:00:00"` muestra ahora ese mismo momento en `mostrar`,
con evidencia vacía y `no_diagnosticable` honesto (quickstart.md
Escenario 6).
