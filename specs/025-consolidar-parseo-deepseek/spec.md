# Feature Specification: Parseo de DeepSeek Compartido y Autocomprobación Sincera

**Feature Branch**: `025-consolidar-parseo-deepseek`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Consolidar el bloque de parseo de la respuesta de DeepSeek que hoy está duplicado entre el diagnóstico de episodios y la remediación de contenedores, y corregir el texto de ayuda de las tres CLIs que hace creer que su autocomprobación --selftest está acotada a ese paquete cuando en realidad las tres ejecutan siempre la misma suite completa compartida."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Corregir el respaldo de una respuesta de DeepSeek en un solo lugar (Priority: P1)

Quien mantiene el sistema necesita corregir cómo se extrae el
contenido y el coste de una respuesta de DeepSeek — incluido el
respaldo para cuando el modelo deja la respuesta en el campo de
razonamiento en vez del campo de contenido normal — y que esa
corrección se aplique tanto al diagnóstico de episodios como a la
remediación de contenedores sin tener que recordar tocar dos sitios.

**Why this priority**: El respaldo del campo de razonamiento ya
resolvió un problema real en producción una vez (una respuesta
completa y válida que se descartaba por estar en el campo equivocado).
Que hoy viva duplicado significa que el mismo síntoma puede reaparecer
en la remediación de contenedores sin que nadie lo note, porque quien
corrija el diagnóstico de episodios no tiene por qué acordarse del
segundo sitio.

**Independent Test**: Se puede probar cambiando el comportamiento del
respaldo (por ejemplo, qué campo se prueba primero) en un único lugar
y comprobando que tanto el diagnóstico de episodios como la
remediación de contenedores ven el cambio.

**Acceptance Scenarios**:

1. **Given** una respuesta de DeepSeek con el contenido en el campo de
   razonamiento en vez del campo de contenido normal, **When** se
   extrae con la lógica compartida, **Then** tanto el diagnóstico de
   episodios como la remediación de contenedores recuperan el mismo
   contenido, con el mismo criterio.
2. **Given** las preguntas que cada uno le hace a DeepSeek (una
   abierta sobre la causa probable, otra cerrada sobre si una acción
   de la lista cerrada resuelve el caso) y la validación que cada uno
   aplica después de extraer la respuesta, **When** se consolida la
   extracción compartida, **Then** ambas preguntas y ambas
   validaciones siguen siendo exactamente las que eran — nada de eso
   se toca.

---

### User Story 2 - Confiar en lo que dice la autocomprobación de cada CLI (Priority: P2)

Quien usa cualquiera de las tres CLIs (diagnóstico, inventario,
remediación) necesita que el texto de ayuda y la documentación interna
de su autocomprobación (`--selftest`) digan la verdad sobre qué
comprueba, para no llevarse la impresión de que valida solo la lógica
de ese paquete cuando en realidad ejecuta la misma suite completa
compartida por los tres.

**Why this priority**: Es una corrección de menor impacto que la
Historia 1 — no cambia ningún comportamiento, solo texto — pero deja
de inducir a error sobre el alcance real de la comprobación.

**Independent Test**: Se puede probar leyendo el texto de ayuda y la
documentación interna de `--selftest` en las tres CLIs y comprobando
que ninguno da a entender un alcance acotado al propio paquete.

**Acceptance Scenarios**:

1. **Given** el texto de ayuda de `--selftest` en cualquiera de las
   tres CLIs, **When** alguien lo lee, **Then** entiende que ejecuta
   la suite completa compartida de los tres paquetes, no una acotada
   al paquete de esa CLI.
2. **Given** la documentación interna de la función que ejecuta la
   autocomprobación en cualquiera de las tres CLIs, **When** alguien
   la revisa, **Then** no encuentra una lista de ficheros de test que
   dé a entender un alcance menor que el real.

---

### Edge Cases

- ¿Qué pasa con la pregunta que cada uno le hace a DeepSeek
  (construcción del prompt) y con la validación posterior de la
  respuesta ya extraída? No se tocan — son deliberadamente distintas
  entre el diagnóstico de episodios y la remediación de contenedores,
  y consolidarlas sería alcance añadido, no la duplicación real que
  motiva esta feature.
- ¿Qué pasa si en el futuro se decide que cada CLI debería ejecutar
  solo sus propios tests? Queda fuera de esta feature — sería un
  cambio de comportamiento real, no una corrección de texto engañoso.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE ofrecer un único lugar de origen para la
  lógica de extraer el contenido y los tokens de una respuesta de
  DeepSeek, incluido el respaldo para cuando el modelo devuelve la
  respuesta en el campo de razonamiento en vez del campo de contenido
  normal.
- **FR-002**: El diagnóstico de episodios y la remediación de
  contenedores DEBEN seguir obteniendo, ante la misma respuesta de
  DeepSeek, exactamente el mismo contenido y los mismos tokens que
  obtienen hoy.
- **FR-003**: La pregunta que cada uno construye para DeepSeek, y la
  validación que cada uno aplica después de extraer la respuesta, NO
  se consolidan — permanecen tal cual, específicas de cada uno.
- **FR-004**: El texto de ayuda de `--selftest` en las tres CLIs DEBE
  describir con precisión que ejecuta la suite completa compartida de
  los tres paquetes, no una acotada al paquete de esa CLI.
- **FR-005**: La documentación interna de la función que ejecuta la
  autocomprobación en las tres CLIs DEBE describir con precisión el
  mismo alcance — sin enumerar una lista de ficheros que dé a entender
  algo más acotado que la realidad.
- **FR-006**: Qué pruebas ejecuta cada CLI al invocar `--selftest` NO
  cambia — sigue siendo la misma suite completa compartida que ya
  ejecutan hoy.

### Key Entities

- **Extracción de respuesta DeepSeek**: la lógica que, dada una
  respuesta cruda de la API de DeepSeek, obtiene el contenido (con el
  respaldo del campo de razonamiento) y los tokens de entrada/salida —
  hoy duplicada, pasa a tener un único origen.
- **Pregunta a DeepSeek**: lo que cada consumidor (diagnóstico de
  episodios, remediación de contenedores) construye como prompt —
  deliberadamente distinta entre los dos, fuera de alcance.
- **Validación posterior**: lo que cada consumidor comprueba sobre la
  respuesta ya extraída antes de aceptarla — deliberadamente distinta
  entre los dos, fuera de alcance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Corregir el comportamiento del respaldo de extracción de
  una respuesta de DeepSeek requiere modificar un único lugar,
  verificable revisando cuántos ficheros cambian.
- **SC-002**: Las pruebas existentes del diagnóstico de episodios y de
  la remediación de contenedores relacionadas con el parseo de
  DeepSeek siguen pasando exactamente igual, sin alterar su intención.
- **SC-003**: El texto de ayuda y la documentación interna de
  `--selftest` en las tres CLIs no contienen ninguna afirmación sobre
  su alcance que no sea cierta.

## Assumptions

- El bloque de extracción compartido descrito en
  `REFACTOR-deepseek-selftest.md` (raíz del repo) — contenido con
  respaldo de razonamiento, tokens de entrada/salida — es la
  duplicación real completa entre los dos consumidores; no se ha
  detectado ninguna otra pieza compartida entre ambos.
- El cambio es puramente de organización interna y de precisión de
  documentación: no añade, retira, ni cambia ninguna capacidad hoy
  soportada por ninguno de los tres paquetes.
