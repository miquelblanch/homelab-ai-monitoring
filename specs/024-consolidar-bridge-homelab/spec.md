# Feature Specification: Puente Único hacia los Scripts del Homelab

**Feature Branch**: `024-consolidar-bridge-homelab`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Consolidar lo que de verdad se duplica entre los tres puentes hacia scripts privados del homelab (diagnostico/_homelab_bridge.py, inventory/_homelab_bridge.py, remediacion/_homelab_bridge.py), y documentar explícitamente las dependencias entre paquetes que hoy existen pero no están todas registradas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cambiar algo compartido en un solo lugar (Priority: P1)

Quien mantiene el sistema de diagnóstico necesita cambiar cómo se
resuelve una credencial, un latido, o la lista de contenedores que
nunca se reinician, y que ese cambio se aplique a los tres paquetes
(diagnóstico, inventario, remediación) sin tener que recordar tocar
tres ficheros distintos ni arriesgarse a que uno se quede desactualizado.

**Why this priority**: Es el problema central — cinco piezas hoy
copiadas en dos o tres ficheros a la vez es exactamente el tipo de
duplicación donde un cambio real se aplica en un sitio y se olvida en
otro, sin que nada avise.

**Independent Test**: Se puede probar cambiando el comportamiento de
una de las piezas verificadas como compartidas (por ejemplo, cómo se
resuelve la ruta de los scripts del homelab) en un único lugar, y
comprobando que los tres paquetes ven el cambio sin tocar más ficheros.

**Acceptance Scenarios**:

1. **Given** una de las piezas compartidas (credenciales, latidos,
   lista de contenedores que nunca se reinician, credenciales de
   Telegram, o la resolución de la ruta de scripts), **When** se
   modifica su comportamiento, **Then** los paquetes que la usan ven
   el mismo cambio sin necesidad de tocar más de un lugar.
2. **Given** el mecanismo de prueba que permite forzar un contenedor
   como crítico solo durante pruebas de la remediación de
   contenedores, **When** se consolida la función de contenedores
   críticos, **Then** ese mecanismo sigue existiendo únicamente para
   remediación — nunca se activa desde diagnóstico ni desde inventario.

---

### User Story 2 - Saber qué paquete depende de cuál, sin sorpresas (Priority: P2)

Quien mantiene el sistema necesita poder confiar en que la
documentación de dependencias entre paquetes (diagnóstico, inventario,
remediación) refleja la realidad del código — no una afirmación de
"independencia total" que ya dejó de ser cierta sin que nadie lo
anotara.

**Why this priority**: Una dependencia real no documentada es peor que
una duplicación: alguien puede romper el paquete del que depende sin
saber que hay otro paquete que lo necesita.

**Independent Test**: Se puede probar comparando, para cada paquete,
la documentación de sus dependencias contra los `import` reales de su
código — deben coincidir exactamente, sin ninguna dependencia real sin
anotar.

**Acceptance Scenarios**:

1. **Given** la dependencia real y ya existente de diagnóstico hacia
   inventario, **When** se completa esta feature, **Then** existe una
   anotación explícita de esa dependencia, con el mismo nivel de
   detalle que ya tiene la dependencia de remediación hacia
   diagnóstico.
2. **Given** cualquier paquete de los tres, **When** alguien revisa su
   documentación de dependencias, **Then** no encuentra ninguna
   afirmación de independencia que el código ya haya dejado de cumplir.

---

### Edge Cases

- ¿Qué pasa con la función que decide qué contenedores son críticos,
  que en remediación de contenedores tiene lógica añadida (el
  mecanismo de prueba) que los otros dos paquetes no tienen? Debe
  quedar una única versión base compartida más la extensión de
  remediación por encima — nunca la extensión filtrándose a los otros
  paquetes, ni una segunda copia de la base solo por la extensión.
- ¿Qué pasa con las piezas que hoy solo usa un paquete (los checks de
  Home Assistant en diagnóstico; las comprobaciones propias de
  cobertura en inventario; el reinicio de contenedores y la
  declaración de correcciones en remediación)? No se mueven a ningún
  sitio compartido — moverlas sería alcance añadido, no consolidación
  de duplicados reales.
- ¿Qué pasa si un paquete deja de poder importar el módulo compartido
  (por ejemplo, un repo público clonado fuera del homelab)? Debe
  comportarse exactamente igual que hoy — valores inocuos, nunca una
  excepción — el mismo contrato "a prueba de fallos" que ya tienen los
  tres ficheros por separado.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE ofrecer un único lugar de origen para
  cada pieza verificada como compartida entre dos o más paquetes hoy:
  el control de contenedores que nunca se reinician, la lectura de
  credenciales genéricas, el registro de latidos, las credenciales de
  Telegram, y la resolución de la ruta de scripts del homelab.
- **FR-002**: Los tres paquetes (diagnóstico, inventario, remediación)
  DEBEN seguir teniendo acceso a esas piezas compartidas exactamente
  con el mismo comportamiento observable que tienen hoy.
- **FR-003**: La función que decide qué contenedores son críticos DEBE
  seguir existiendo en una versión base compartida más una extensión
  exclusiva de remediación de contenedores (el mecanismo de prueba que
  permite forzar un contenedor como crítico) — esa extensión nunca
  debe quedar accesible desde diagnóstico ni desde inventario.
- **FR-004**: Las piezas exclusivas de un solo paquete (los checks de
  Home Assistant y su histórico en diagnóstico; las comprobaciones
  propias de cobertura de inventario; el reinicio de contenedores, el
  cortacircuito, y la declaración de correcciones del dashboard en
  remediación) DEBEN permanecer en su paquete — no se consolidan.
- **FR-005**: El sistema DEBE documentar explícitamente, con el mismo
  nivel de detalle que ya existe para la dependencia de remediación
  hacia diagnóstico, la dependencia real y ya existente de diagnóstico
  hacia inventario.
- **FR-006**: Si el módulo compartido no puede acceder a un script
  externo del homelab (repo clonado fuera de la máquina, por ejemplo),
  DEBE devolver un resultado inocuo — nunca lanzar una excepción —
  igual que el contrato que ya cumple cada uno de los tres ficheros
  hoy por separado.

### Key Entities

- **Pieza compartida**: una función o bloque de arranque que hoy
  existe, con comportamiento idéntico, en dos o tres de los tres
  ficheros puente. Cinco piezas verificadas: control de contenedores
  que nunca se reinician, lectura de credenciales, registro de
  latidos, credenciales de Telegram, y resolución de la ruta de
  scripts del homelab.
- **Pieza exclusiva**: una función que hoy solo existe en uno de los
  tres ficheros puente y sirve solo a su paquete — no es duplicación,
  es alcance propio de ese paquete.
- **Dependencia entre paquetes**: una relación de import real de un
  paquete (diagnóstico, inventario, remediación) hacia otro. Dos
  existen hoy: remediación hacia diagnóstico (ya documentada) y
  diagnóstico hacia inventario (sin documentar hasta esta feature).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cambiar el comportamiento de cualquiera de las cinco
  piezas compartidas requiere modificar un único lugar, verificable
  revisando cuántos ficheros cambian.
- **SC-002**: El mecanismo de prueba de contenedores críticos exclusivo
  de remediación de contenedores sigue sin ser alcanzable desde
  diagnóstico ni desde inventario — verificable por inspección directa.
- **SC-003**: Los tres paquetes obtienen, antes y después del cambio,
  resultados idénticos ante los mismos casos — ninguna prueba
  existente cambia de resultado.
- **SC-004**: La documentación de dependencias de cada paquete no
  contiene ninguna afirmación de independencia que el código ya haya
  dejado de cumplir — verificable comparando la documentación contra
  los `import` reales.

## Assumptions

- Las cinco piezas compartidas y la lista de piezas exclusivas
  descritas en `REFACTOR-homelab-bridge.md` (raíz del repo) son la
  partición correcta y completa a fecha de esta especificación.
- No se decide en esta feature si conviene que algún paquete empiece a
  importar de `inventory` para algo nuevo — solo se documenta la
  dependencia que ya existe.
- El cambio es puramente de organización interna y de documentación:
  no añade ni retira ninguna capacidad hoy soportada por los tres
  paquetes.
