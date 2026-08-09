# Feature Specification: Metadatos de Móvil Fuera de Alcance y Backup Propio de HA

**Feature Branch**: `005-movil-y-backup-ha`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "El inventario de cobertura marca 150 entidades de Home Assistant como brecha. De esas, 53 pertenecen a la app móvil de Home Assistant en el iPhone de Miquel, el de Cécile y el MacBook Air — localización, nivel de batería, red wifi, modo kiosco... — y no son señales de salud de nada, son metadatos personales que cambian todo el rato. Quiero que dejen de contar como brecha, igual que ya se hizo con las entidades de ajuste/diagnóstico. Además, Home Assistant tiene su propio sistema de copias de seguridad automáticas (distinto del backup diario del homelab), y hoy nadie vigila si esas copias se siguen haciendo — si dejaran de funcionar, no me enteraría hasta necesitar una copia y no encontrarla. Quiero que haya un aviso si la última copia correcta de Home Assistant tiene más de un día y medio. No incluye los climatizadores, los ESP32, el resto de sensores de los enchufes inteligentes, los scripts, ni el resto de entidades sin triar — esas quedan para un feature posterior, cuando decida qué es \"normal\" para cada una."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dejar de contar como brecha los metadatos personales del móvil (Priority: P1)

Miquel quiere que el inventario de cobertura deje de marcar como brecha
las 53 entidades que la app móvil de Home Assistant genera para su
iPhone, el de Cécile y su MacBook Air — localización, batería, red
wifi, modo kiosco, aplicación en primer plano... — porque no son
señales de salud de ningún sistema, son metadatos personales que
cambian constantemente y nunca van a tener un "estado esperado" fijo
que declarar uno a uno.

**Why this priority**: Es la pieza de mayor impacto y menor riesgo —
un único criterio ya declarado por la propia integración de Home
Assistant (de qué app procede cada entidad), sin inventar nada, que
cierra más de un tercio de las brechas restantes de golpe.

**Independent Test**: Se puede probar por completo relanzando el
inventario de cobertura y comprobando que ninguna entidad de la app
móvil de Home Assistant aparece como brecha.

**Acceptance Scenarios**:

1. **Given** una entidad generada por la app móvil de Home Assistant
   (en cualquiera de los tres dispositivos en alcance), **When** se
   relanza el inventario de cobertura, **Then** esa entidad no aparece
   como brecha.
2. **Given** una entidad que no proviene de la app móvil (por ejemplo,
   una luz o un sensor de temperatura), **When** se relanza el
   inventario, **Then** esa entidad sigue evaluándose con las reglas
   ya existentes, sin verse afectada por esta regla nueva.

---

### User Story 2 - Saber si el backup automático de Home Assistant ha dejado de funcionar (Priority: P2)

Miquel quiere que el inventario de cobertura avise si el sistema de
copias de seguridad automáticas propio de Home Assistant deja de
completar copias correctas — hoy nadie lo vigila, y si dejara de
funcionar en silencio, Miquel no se enteraría hasta el día que
necesitara restaurar una copia y no la encontrara.

**Why this priority**: Depende de declarar un estado esperado nuevo
(la antigüedad de la última copia correcta) sobre un tipo de dato que
hoy ningún mecanismo del homelab comprueba — más trabajo que la User
Story 1, y por eso va después.

**Independent Test**: Se puede probar por completo comprobando que,
mientras la última copia correcta de Home Assistant tiene menos de un
día y medio, el inventario no la marca como brecha — y que, si esa
antigüedad supera el día y medio, sí aparece como brecha real.

**Acceptance Scenarios**:

1. **Given** la última copia de seguridad automática correcta de Home
   Assistant se completó hace menos de un día y medio, **When** se
   relanza el inventario, **Then** no aparece como brecha.
2. **Given** la última copia de seguridad automática correcta de Home
   Assistant tiene más de un día y medio de antigüedad, **When** se
   relanza el inventario, **Then** aparece como brecha real — distinta
   de "nunca se declaró nada al respecto", porque sí hay un estado
   esperado declarado que hoy no se cumple.

---

### Edge Cases

- ¿Qué pasa si la entidad de la última copia correcta de Home Assistant
  no tiene ningún valor todavía (por ejemplo, en una instalación
  recién hecha que nunca completó una copia)? Cuenta como brecha —
  ausencia de dato no es lo mismo que una copia reciente, y no debe
  mostrarse como si todo estuviera bien.
- ¿Qué pasa con una entidad de la app móvil que en el futuro sí
  interese vigilar (por ejemplo, si Miquel decide que quiere un aviso
  de batería baja del móvil)? Queda fuera de este feature — la regla
  aquí es un "no aplica" general para toda la familia; una excepción
  puntual futura se añadiría como una decisión aparte, con el mismo
  criterio que ya se usó para las excepciones de seguridad de feature
  004.
- ¿Qué pasa si Miquel o Cécile añaden un dispositivo nuevo con la app
  móvil de Home Assistant en el futuro? Sus entidades quedan cubiertas
  automáticamente por la misma regla, sin tocar código — se basa en de
  qué app procede la entidad, no en una lista de dispositivos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El inventario de cobertura NO DEBE contar como brecha
  ninguna entidad de Home Assistant generada por la app móvil de Home
  Assistant, en ninguno de los dispositivos que la usan.
- **FR-002**: El inventario de cobertura DEBE seguir evaluando con las
  reglas ya existentes cualquier entidad que no provenga de la app
  móvil de Home Assistant — esta regla nueva no debe alterar ninguna
  otra evaluación.
- **FR-003**: El inventario de cobertura DEBE comprobar si la última
  copia de seguridad automática correcta de Home Assistant tiene menos
  de un día y medio de antigüedad.
- **FR-004**: El inventario de cobertura DEBE contar como brecha el
  sistema de copias de seguridad automáticas de Home Assistant cuando
  la última copia correcta tenga más de un día y medio, o cuando no
  haya ninguna copia correcta registrada todavía.
- **FR-005**: Este feature NO DEBE ejecutar ninguna acción correctiva
  ni modificar la configuración de la app móvil, de ningún dispositivo,
  ni del sistema de copias de Home Assistant — es exclusivamente de
  evaluación de cobertura.
- **FR-006**: Este feature NO DEBE declarar ningún estado esperado
  sobre climatizadores, dispositivos ESP32, el resto de sensores de
  los enchufes inteligentes, scripts, ni el resto de entidades sin
  triar — quedan fuera a propósito para un feature posterior.

### Key Entities

- **Entidad de la app móvil de Home Assistant**: cualquier entidad de
  Home Assistant generada por esa integración, en cualquiera de los
  dispositivos en alcance (iPhone de Miquel, iPhone de Cécile, MacBook
  Air de Miquel). Atributo relevante: de qué integración procede la
  entidad, tal como lo declara el propio registro de HA.
- **Backup automático de Home Assistant**: el sistema de copias de
  seguridad propio de Home Assistant, distinto del backup diario del
  homelab. Atributo relevante: cuándo se completó la última copia
  correcta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El número de brechas de categoría `entidad_ha` baja de
  las 150 actuales en al menos 53 tras desplegar este feature
  (comprobable relanzando el inventario de cobertura).
- **SC-002**: Miquel puede saber, sin abrir Home Assistant a mano, si
  el backup automático propio de Home Assistant sigue completando
  copias correctas — hoy esa información no está en ningún sitio salvo
  entrando en Home Assistant y revisándolo.
- **SC-003**: Ninguna entidad ajena a la app móvil de Home Assistant
  cambia de clasificación tras desplegar este feature — la regla nueva
  no tiene efectos fuera de su alcance declarado.

## Assumptions

- No se declara ninguna excepción dentro de la app móvil de Home
  Assistant (a diferencia de las excepciones de seguridad de feature
  004) — ninguna de sus 53 entidades corresponde a un dispositivo de
  seguridad física; son todas metadatos de dispositivos personales.
- El margen de "un día y medio" para el backup de Home Assistant seguirá
  el mismo criterio que ya usa `verify_backups.py`/`bautista-calendar.sh`
  para crones de una vez al día: diario más margen, sin inventar un
  criterio nuevo. El número exacto en segundos se fija en el plan, no
  en este documento.
- Este feature cubre solo la señal de "última copia correcta" del
  sistema de backup de Home Assistant, no las otras entidades
  relacionadas (estado del administrador, próxima copia programada,
  evento de la última copia, último intento) — es la señal mínima
  suficiente para saber si el backup sigue funcionando; las demás
  quedan disponibles para un feature posterior si hiciera falta más
  detalle.
- No se rediseña ni se cambia la configuración de la app móvil de Home
  Assistant ni del sistema de backup — la brecha que cierra este
  feature es exclusivamente de vigilancia, no de comportamiento.
