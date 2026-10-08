# Plan: driver propio para Maschine MK3

Fecha: 2026-10-07

## Objetivo

Reemplazar el programa de Native Instruments que corre en segundo plano por un
driver propio, sin cambiar el mapeo actual
([maschine-mk3-ableton-virtualdj](../maschine-mk3-ableton-virtualdj/)).

- **Modo Ableton:** todo funciona como hoy con el script `CustomMaschineMK3`.
- **Modo DJ (SAMPLING):** las pantallas muestran VirtualDJ: las ondas de los dos
  decks alineadas, un medidor de fase y la diferencia de BPM, para sincronizar
  a mano.
- **Después:** el mismo driver en Push 3 standalone (Linux), sin VirtualDJ.

## Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Lenguaje | Go | Un binario liviano, el mismo código en Windows y Linux, reúso de `core/` de push-hack |
| Sistema primero | Windows | Ahí corren Ableton y VirtualDJ |
| Protocolo base | [ni-controllers-lib](https://github.com/asutherland/ni-controllers-lib) (ISC) | Ya decodifica entradas, LEDs y pantallas de la MK3; su JSON de configuración se lee tal cual |
| Tabla de controles a MIDI | Se genera desde `Configuration.ncc` (XML) | Misma salida que la plantilla CUSTOM MASCHINE, sin cargar nada a mano |
| Puertos MIDI virtuales (Windows) | Primero puertos de loopMIDI creados a mano; después evaluar los dispositivos virtuales de Windows MIDI Services | loopMIDI es lo más simple; los de Windows MIDI Services necesitan interoperar con WinRT desde Go |
| Acceso USB (Windows) | hidapi para HID; libusb + WinUSB (Zadig) **solo en la interfaz 5** para las pantallas | El HID no necesita cambiar drivers; las pantallas sí |
| Toolchain | Go + cgo con MSYS2/mingw (gcc) | hidapi y libusb son librerías de C |

## Datos del hardware (de ni-controllers-lib)

- USB: vendor `0x17CC`, producto `0x1600`.
- Entradas: interfaz 4, endpoint `0x83`. Reporte `0x01` = botones y perillas
  (bits); reporte `0x02` = pads con presión (hasta 21 bloques de 3 bytes).
- LEDs: reporte `0x80` (63 bytes, botones), reporte `0x81` (42 bytes, LEDs
  RGB indexados).
- Pantallas: interfaz 5, endpoint bulk 4, 2 pantallas de 480×272, RGB565.
  Cabecera de 16 bytes (`0x84`, pantalla, `0x60`, x, y, ancho, alto), comando
  con la cantidad de píxeles, píxeles, `0x03` (dibujar), `0x40` (fin).
  Permite actualizar solo un rectángulo.

## Fases

### Fase 0: preparación y medición de referencia (½ día)

- Instalar Go, MSYS2 (gcc), loopMIDI, Zadig, USBPcap y Wireshark.
- Anotar cómo volver atrás con Zadig (restaurar el driver de NI en la
  interfaz 5).
- **Medir el sistema actual con el programa de NI** (sin esto no hay con qué
  comparar):
  - Latencia del pad al sonido (ver "Cómo medir" más abajo).
  - CPU y RAM de los procesos de NI.

**Listo cuando:** están anotados los números de referencia.

### Fase 1: prueba de pantallas (½–1 día)

- Zadig: WinUSB solo en la interfaz 5.
- Programa Go que pinta una imagen de prueba en cada pantalla.
- Medir cuántos cuadros por segundo salen con la pantalla completa y con un
  rectángulo de la mitad.

**Listo cuando:** las dos pantallas muestran la imagen y hay números de fps.
**Si falla:** se para todo. Las pantallas son lo que justifica el proyecto.

### Fase 2: entradas (1–2 días)

- Leer el HID y decodificarlo con el JSON de ni-controllers-lib.
- Herramienta `monitor`: muestra en vivo cada control que tocás.
- Completar lo que falte (touch strip, encoder grande, pedal) con USBPcap,
  cambiando un control por vez.
- Medir cada cuánto llegan los reportes de los pads.

**Listo cuando:** cada control de la Maschine aparece con su nombre en el
monitor.

### Fase 3: velocity (½–1 día; prioridad baja)

El usuario toca casi siempre con velocity fija en 127, y la elige con el botón
**FIXED VEL**: CC 80, que el script ya asigna a `Accent` (`full_velocity`) en
`Mappings.py`. El driver solo manda la nota; el script decide si va a 127.

- **Velocity fija sin espera:** el driver sigue el estado del LED de FIXED
  VEL que manda el script. Si está prendido, manda la nota apenas el pad
  supera un umbral mínimo de presión, sin esperar a medir la velocity
  (ahorra 1–4 ms).
- **Velocity variable:** una curva simple (pico de presión en los primeros
  milisegundos), configurable. Igualar la curva de NI queda para después, si
  hace falta.

**Listo cuando:** con FIXED VEL prendido, los pads suenan a 127 sin retraso
perceptible; con FIXED VEL apagado, golpes suaves y fuertes dan velocities
distintas.

### Fase 4: paridad con el setup actual (4–8 días)

- Generar la tabla desde `Configuration.ncc`.
- Dos puertos virtuales: `Maschine Ableton` y `Maschine VDJ`. Todo lo que
  entra va a los dos; los LEDs que manda cada uno se aplican según el modo,
  como hoy.
- Modo: SAMPLING → DJ; MIXER/PLUGIN → Ableton (los mismos botones que ya usa el
  mapeo).
- Pantallas: interpretar el texto MCU de cada programa (4×28,
  `F0 00 00 66 17 12 <pos>`), guardarlo por separado y dibujar el del modo
  activo.
- Configurar Ableton y VirtualDJ con los nuevos puertos y cerrar el programa
  de NI.

**Listo cuando:**
- Tu set funciona completo sin el programa de NI.
- Latencia ≤ la de referencia + 1 ms, con jitter < 1 ms.
- CPU < 1 % de un núcleo en modo Ableton.

### Fase 5: pantallas del modo DJ (3–5 días)

- Mapeo de VirtualDJ (solo XML):
  - Mandar la posición del beat de cada deck.
  - SHIFT + perillas 3/4 = tempo fino (por ejemplo, 0,05 BPM por paso).
- Medidor de fase y diferencia de BPM, con los datos de VirtualDJ por MIDI.
  Interpolar con el BPM entre mensajes para que se mueva suave.
- Ondas apiladas: capturar la zona de ondas de VirtualDJ con Desktop
  Duplication (DXGI), solo esa región, a 30 fps.
- Diseño:
  - Izquierda: las dos ondas.
  - Derecha: fase, BPM, SYNC/MASTER y los textos que ya manda el mapeo.

**Listo cuando:**
- Podés sincronizar dos temas mirando solo la Maschine.
- CPU < 5 % de un núcleo en modo DJ.
- La latencia de los pads no cambia con las pantallas DJ andando.

### Fase 6: robustez (2–3 días)

- Desenchufar y volver a enchufar sin reiniciar nada.
- Arranque con Windows, archivo de configuración y log.
- Si el driver se cierra, apagar los LEDs y dejar un mensaje en pantalla.

### Fase 7: Linux y Push 3 standalone (4–8 días)

- Compilar para linux/amd64 y probar en una PC con Linux o una Raspberry Pi.
- Puertos ALSA y `hidraw`, sin modo DJ.
- Empaquetarlo como hack de push-hack: servicio con espera de 30 s al
  arrancar (por el bloqueo del USB-A) y el script en la User Library.
- Medir el CPU en Push con Live tocando.

## Latencia

**Camino de un golpe de pad:**

| Tramo | Estimación | Comentario |
|---|---|---|
| Maschine → PC (reporte HID) | ~1 ms | Depende del intervalo de sondeo USB; se mide en la fase 2 |
| Cálculo de velocity | 0 ms con FIXED VEL; 1–4 ms sin él | Con velocity fija, la nota sale al primer contacto |
| Driver (decodificar + enviar MIDI) | < 0,1 ms | Sin reservar memoria en el camino de los pads |
| Puerto virtual → Ableton | < 1 ms | loopMIDI o Windows MIDI Services |
| Buffer de audio de Ableton | 3–10 ms | Igual que hoy, no cambia |

Con esto, la latencia debería quedar **igual que con el programa de NI**, que
hace el mismo recorrido (HID → su propio puerto MIDI virtual).

**Cómo evitar sorpresas:**
- El lector de HID corre en su propio hilo con prioridad alta (MMCSS "Pro
  Audio" en Windows); las pantallas, en otro hilo con prioridad normal.
- **Las pantallas no frenan a los pads:** USB les da ancho de banda reservado
  a los reportes HID (transferencias periódicas), y las imágenes usan lo que
  sobra (bulk) en otra interfaz.
- Go: las pausas del recolector de basura suelen ser de menos de 0,5 ms. Se
  minimizan sin reservar memoria en el camino de los pads; se verifica con la
  medición de jitter.

**Pantallas DJ:** de la captura al cuadro en la Maschine, ~30–60 ms. Para
mirar está bien; el medidor de fase usa datos de VirtualDJ y no la captura, así
que es más preciso.

**Cómo medir:**
- Interna: el driver registra el momento del reporte HID y el del MIDI
  enviado.
- De punta a punta: grabar con un micrófono el golpe del pad y el sonido de
  Ableton en la misma toma, y comparar la distancia entre los dos con el
  programa de NI y con el driver.

## Consumo

| Recurso | Modo Ableton | Modo DJ | Comentario |
|---|---|---|---|
| CPU | < 1 % de un núcleo | < 5 % de un núcleo | En modo Ableton solo se redibuja cuando cambia el texto |
| RAM | ~10–20 MB | ~20–40 MB | Binario Go; la captura agrega buffers de imagen |
| USB | Mínimo | ~5–10 MB/s | Solo se manda el rectángulo de las ondas, no la pantalla entera (USB 2.0 da ~35 MB/s útiles) |

- Probablemente consuma menos que el programa de NI; se confirma con la
  medición de la fase 0.
- La captura de pantalla usa la GPU; el costo en CPU es convertir y escalar
  ~130 mil píxeles por cuadro.
- **Recomendación:** conectar la Maschine a un puerto USB distinto del de la
  placa de audio (si es posible, otro controlador USB).
- **Push 3 standalone:** sin modo DJ, el consumo es casi nulo; con el kernel
  de tiempo real no hay que darle prioridad mayor que al audio de Live.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Zadig choca con el driver de NI | Medio día perdido | Probar primero solo la interfaz 5; tener anotado cómo volver atrás |
| La velocity variable no se siente igual | Poco, porque se usa casi siempre fija en 127 | Curva configurable; ajustarla solo si hace falta |
| loopMIDI y Windows MIDI Services no conviven bien | Ableton o VirtualDJ no ven los puertos | Probar en la fase 4; alternativa: dispositivos virtuales de Windows MIDI Services |
| VirtualDJ cambia el diseño de su pantalla | La captura de ondas se rompe | Región configurable; a futuro, plugin de VirtualDJ con ondas propias |
| Push: hardware cerrado, pruebas lentas | Fase 7 más larga | Probar todo antes en una PC con Linux |

## Tiempo estimado

- Fases 0–4 (tu setup sin el programa de NI): ~6–13 días de trabajo efectivo.
- Fase 5 (pantallas DJ): +3–5 días.
- Fases 6–7 (robustez y Push): +6–11 días.
- Part-time (~10 h por semana): 1–2 meses hasta la fase 5.
