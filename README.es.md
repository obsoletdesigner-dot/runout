# Runout

[English](README.md) · **Español**

Editor de metadatos para másters de audio que **no toca el audio**. Lee y edita archivos WAV, AIFF, FLAC, MP3, M4A (AAC o ALAC), Ogg Vorbis y Opus (ver [Formatos admitidos](#formatos-admitidos)).

En los WAV escribe a la vez todas las capas:

- `id3 ` (ID3v2.3 por defecto, o v2.4): todos los frames de texto, créditos, fechas, ordenación, URLs, `COMM`, `USLT`, `TXXX` estándar de la industria (catálogo, UPC/EAN, ISWC, país, tipo y estado del lanzamiento, ReplayGain, MusicBrainz) y campos `TXXX` libres. Admite cuatro imágenes: portada, contraportada, foto del artista y logo del sello. `TLEN` se calcula solo a partir del audio. En v2.3, los frames que solo existen en v2.4 (`TMOO`, `TPRO`, `TSST`, `TDRL`, `TDEN`, `TDTG`) se guardan como `TXXX`, igual que hace MusicBrainz Picard.
- `axml` (EBU Tech 3352, EBUCore): ISRC, título, artista, sello, fecha, ISWC, UPC/EAN, número de catálogo, idioma y derechos. Va justo antes de `data`. Si el archivo trae un axml de otra herramienta con más datos, solo se cambia el ISRC y el resto se conserva byte a byte.
- `LIST-INFO` (en UTF-8, como espera BWF MetaEdit; opción Windows-1252 en Preferencias): INAM, IART, IPRD, ICRD, IGNR, ICMT, ICOP, IENG, ISFT, ISRC (*Source*), ITRK, IKEY, ISBJ, IMED, ISRF, ITCH, IARL e ICMS. El código ISRC nunca se escribe en `INFO/ISRC`, porque ese campo significa *Source*, y el sello tampoco. Si el archivo ya traía ahí un código ISRC (REAPER y Sound Forge lo hacen), se mantiene igual que el ISRC de la pista.
- `bext` (BWF): descripción, originador, referencia, fecha, hora, sonoridad (EBU R128, versión 2) y CodingHistory. TimeReference y UMID se muestran pero no se pueden editar. Si no cambia ningún campo, el `bext` se copia byte a byte.

Cada campo valida su formato: ISRC, ISWC con dígito de control, UPC/EAN con dígito de control, idioma ISO 639-3, país ISO 3166-1, alfabeto ISO 15924, fechas reales, BPM, tonalidad, URLs, ReplayGain, UUID de MusicBrainz, ASCII y longitudes de `bext`, y rangos de sonoridad. Una pista con algún campo no válido no se puede guardar. El listado completo de campos está en `docs/`.

El Explorador y los reproductores nativos de Windows no leen la carátula incrustada en un WAV. Para ellos, la opción «Guardar también la portada como folder.jpg» de Preferencias (activada por defecto) copia la portada como `folder.jpg` en la carpeta de los WAV.

Si VLC no muestra una carátula nueva, es su caché: VLC guarda las carátulas por artista y álbum. Cierra VLC y borra `%APPDATA%\vlc\art` en Windows, `~/Library/Caches/org.videolan.vlc/art` en macOS o `~/.cache/vlc/art` en Linux.

Las imágenes se convierten a JPEG RGB normal de 2 MB como máximo si pesan más de 2 MB, miden más de 3000 px, están en CMYK o son JPEG progresivos.

## Formatos admitidos

| Formato | Extensiones | Metadatos que escribe | Lo que tiene que quedar idéntico (SHA-256) |
|---|---|---|---|
| WAV / BWF | `.wav`, `.wave` | `id3 `, `axml`, `LIST-INFO`, `bext` | chunks `data` y `fmt `, y todos los chunks que se conservan |
| AIFF / AIFF-C | `.aif`, `.aiff`, `.aifc` | chunk `ID3 ` (todos los campos ID3 y las cuatro imágenes) | chunks `SSND` y `COMM` |
| FLAC | `.flac` | Vorbis Comments y bloques `PICTURE` | todas las tramas de audio y el bloque `STREAMINFO` (que guarda el MD5 del audio decodificado) |
| MP3 | `.mp3` | ID3v2 al principio del archivo | todo lo que va después de la etiqueta ID3v2 (tramas MPEG, cabecera Xing/LAME, ID3v1 si lo hay) |
| M4A | `.m4a` | átomos `ilst` de iTunes y campos `----:com.apple.iTunes`, portada | contenido de `mdat`, tablas de muestras y offsets de los fragmentos respecto al audio |
| Ogg Vorbis / Opus | `.ogg`, `.oga`, `.opus` | Vorbis Comments y `METADATA_BLOCK_PICTURE` | todos los paquetes menos el de comentarios, y la posición (granule) de cada página de audio |

El editor solo muestra los campos y huecos de imagen que los archivos seleccionados pueden guardar. Si hay archivos de formatos distintos seleccionados, muestra los campos que tienen en común. Los campos de otras capas (`axml`, `LIST-INFO`, `bext`) solo existen en WAV. En M4A solo se puede incrustar la portada, porque el formato no tiene tipos de imagen. Las etiquetas desconocidas (claves Vorbis, `TXXX`, átomos libres) se muestran en Personalizados y se conservan.

**Por qué de momento solo estos formatos.** Runout solo guarda un archivo cuando puede demostrar, con un hash, que el audio es byte a byte el mismo que había antes. Para eso hace falta, en cada formato, una definición exacta de qué bytes son «el audio» y un escritor que los copie sin pasar por un decodificador. Los formatos de arriba tienen esa definición y están cubiertos por las pruebas. Los demás quedan fuera hasta que puedan tener la misma garantía:

- **WMA / ASF**: contenedor propietario, con objetos de metadatos mal documentados y variantes con DRM.
- **APE, WavPack, TTA, Musepack, DSF / DFF (DSD)**: sus etiquetas (APEv2, ID3 en DSF) son conocidas, pero todavía no hay una verificación del audio para ellos, y no son habituales en las entregas a distribuidoras.
- **RF64 / BW64 (WAV de más de 4 GB)**: necesitan tamaños de 64 bits y el chunk `ds64`, que el escritor RIFF no gestiona.
- **Ogg encadenados o multiplexados** (varios flujos lógicos, Ogg FLAC, Speex, vídeo): solo se aceptan Vorbis y Opus de un único flujo.
- **Vídeo MP4, `.m4b`, `.mp4`**: tienen más pistas que el audio, y un cambio de etiquetas puede mover offsets de flujos que no se verifican.

Los archivos con otra extensión simplemente no se cargan. Los que tienen una extensión admitida pero una estructura que Runout no espera se marcan como «No apto» y nunca se escriben.

## Garantía Zero-Touch Audio

1. Un escritor RIFF propio (`runout/core/riff.py` y `writer.py`) reconstruye el archivo en un temporal. `fmt `, `data`, `bext`, `cue `, `LIST-adtl`, `iXML` y cualquier chunk desconocido se copian byte a byte.
2. `mutagen` **nunca abre el WAV**: solo genera y lee los bytes de la etiqueta ID3 en memoria.
3. Antes de reemplazar nada, el temporal se vuelve a leer como un archivo desconocido. Se comprueba que el SHA-256 de `data` y de `fmt ` es idéntico al original, que el hash de cada chunk conservado no ha cambiado, que el tamaño RIFF es igual al tamaño del archivo menos 8, que todos los offsets son pares y que el ISRC y el título releídos son los escritos.
4. Solo si todo cuadra se hace `os.replace` (atómico). Si algo falla, se borra el temporal y el original queda intacto.
5. Cada guardado se anota en `runout.log`, en la carpeta de destino, junto con el SHA-256 de `data`.

Los demás formatos siguen los mismos pasos (`runout/core/formats/base.py`): hash de la parte de audio indicada en la tabla de arriba, archivo nuevo escrito en un temporal dentro de la carpeta de destino, el mismo hash calculado sobre el temporal, relectura de las etiquetas, y solo entonces `os.replace`. FLAC y AIFF usan escritores propios de bloques y chunks, y el MP3 se rehace como una etiqueta ID3v2 nueva seguida de los bytes originales. En M4A y Ogg, `mutagen` escribe en una copia, nunca en el original, y la comparación de hashes decide si esa copia se usa.

No se admiten archivos RF64/BW64 (más de 4 GB) ni WAV truncados. La app los marca como «No apto».

## Instalación y uso (desde el código)

Hace falta Python 3.10 o posterior.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt     # PySide6, mutagen, Pillow, pycountry
python main.py                 # o: python main.py "/ruta/al/album"
```

Flujo de trabajo:

1. Arrastra la carpeta del álbum o varios archivos de audio a la ventana. Al soltar una carpeta se cargan los archivos admitidos que contiene, sin entrar en subcarpetas.
2. Selecciona una pista o varias (Ctrl+A para todas). El editor de la derecha muestra arriba la portada, el título y el artista, y a la izquierda sus secciones: Álbum, Pista, Créditos, Identificadores, Webs, RIFF INFO, BWF (bext), Imágenes y Personalizados.
   - Cada cambio se aplica al momento a todas las pistas seleccionadas. No hay botón «Aplicar».
   - Con varias pistas seleccionadas, los campos con valores distintos muestran «(varios valores)» y solo cambian si escribes en ellos. Los campos propios de cada pista (título, ISRC, nº de pista, letra...) se bloquean.
   - Un campo no válido se marca en rojo con el motivo, y su sección lleva un punto rojo. El idioma, el país y el alfabeto muestran su nombre en verde cuando son correctos.
3. Nº, Título e ISRC también se pueden editar directamente en la tabla. El ISRC se limpia solo: `ES-ABC-26-00001` pasa a `ESABC2600001`.
4. O pulsa **Importar CSV** con columnas `pista,titulo,isrc` (también vale `track,title,isrc`). Acepta `,` o `;`, UTF-8 o Windows-1252. Los datos se asignan por número de pista.
5. Elige el modo de guardado en la barra inferior y pulsa el botón, que indica cuántas pistas se van a escribir (Ctrl+S):
   - *Sobrescribir originales*: guarda solo las pistas con cambios, siempre con la verificación SHA-256.
   - *Exportar a /tagged*: escribe copias de todas las pistas en `carpeta/tagged/` y no modifica los originales. Después, cada fila pasa a trabajar con su copia de `/tagged`, y un nuevo guardado actualiza esa misma copia.

Las columnas Etiquetas, Portada y AXML muestran lo que contiene el archivo cargado en disco (✔ verde o ✘ rojo). Etiquetas son ID3, Vorbis Comments o átomos MP4, según el formato. AXML solo se aplica a WAV y muestra «–» en el resto. Al pasar el ratón por el nombre del archivo se ven su formato y su estructura. La columna Estado resume cada pista y da el detalle al pasar el ratón: ✔ gris sin cambios, ● ámbar con cambios sin guardar, ▲ ámbar con avisos, ✔ verde guardada y verificada, ✘ rojo con errores.

La barra de estado muestra el resultado de cada operación. El registro detallado, con el SHA-256 de cada archivo, se abre con el botón **Registro** y se abre solo si algo falla.

En **Preferencias** (Ctrl+, o ⌘,) están la versión de ID3, la codificación de LIST-INFO, folder.jpg, el tema (claro, oscuro o el del sistema) y el idioma. La interfaz está en inglés por defecto y en español; el cambio de idioma se aplica al reiniciar.

## Traducciones

Los textos de la interfaz están en inglés en el código, dentro de `tr("...")`. Cada idioma adicional es un archivo JSON en `runout/locales/` que asocia el texto en inglés con su traducción, más una entrada `"_language_name"` con el nombre del idioma, que es el que aparece en Preferencias. Los nombres de idiomas, países y alfabetos ISO salen de las traducciones que ya incluye pycountry.

Para añadir un idioma:

1. Copia `runout/locales/es.json` como `runout/locales/<código>.json` (por ejemplo `fr.json`) y cambia `_language_name`.
2. Traduce los valores. Lo que quede sin traducir se muestra en inglés.
3. Ejecuta `python tools/i18n_check.py`, que lista las entradas que faltan o sobran en cada archivo (`--write` las añade vacías o las quita).

Las pruebas comprueban que cada catálogo está completo y que los marcadores (`%s`, `%d`...) coinciden con el original.

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

`tests/make_test_wavs.py` genera WAV sintéticos con `data` de tamaño impar, `bext`, `cue `, `LIST-adtl`, `iXML`, ID3 previo en mayúsculas, `axml` EBUCore ajeno, tamaño RIFF incorrecto, basura al final y falta del byte de relleno. `tests/test_ebucore_schema.py` valida el axml generado (solo ISRC, ampliado y el que queda dentro de un WAV guardado) contra el esquema oficial EBUCore 2012 de la EBU (necesita `lxml`, que está en `requirements-dev.txt`). Los esquemas no están en el repositorio: la prueba los descarga la primera vez, comprueba su SHA-256 y los guarda en `tests/.schemas/`. Sin conexión, esa prueba se salta. Las pruebas verifican hashes, padding, tamaño RIFF, el orden de los chunks y que una corrupción provocada se detecta sin tocar el original. `tests/test_formats.py` hace lo mismo con el resto de formatos usando los archivos de `tests/fixtures/`: ida y vuelta de los campos, hash del audio sin cambios, segundo guardado estable, etiquetas libres e imágenes conservadas, y detección de un byte cambiado dentro del audio.

## Compilar ejecutables con PyInstaller

PyInstaller no compila de forma cruzada: cada ejecutable se genera en su propio sistema operativo, con el entorno virtual activado y `pip install -r requirements-dev.txt`.

**Recomendado: con la receta incluida** (excluye módulos de Qt que no se usan y reduce el tamaño):

```bash
pyinstaller --noconfirm --clean runout.spec
```

Resultado en `dist/`: `Runout.exe` en Windows, `Runout.app` en macOS y `Runout` en Linux.

**Equivalente en una sola línea, sin receta:**

```bash
# Windows (PowerShell o cmd)
pyinstaller --noconfirm --clean --windowed --onefile --name Runout --add-data "runout/locales/*.json;runout/locales" main.py

# macOS (genera dist/Runout.app)
pyinstaller --noconfirm --clean --windowed --name Runout --osx-bundle-identifier io.github.obsoletdesigner-dot.runout --add-data "runout/locales/*.json:runout/locales" main.py

# Linux
pyinstaller --noconfirm --clean --windowed --onefile --name Runout --add-data "runout/locales/*.json:runout/locales" main.py
```

La receta ya usa el icono de `assets/` (`runout.ico` en Windows, `runout.icns` en macOS). Con la línea sin receta, añade `--icon assets/runout.ico` o `--icon assets/runout.icns`. Los iconos se regeneran con `python tools/make_icons.py`.

Notas por sistema:

- **macOS**: una app sin firmar se abre la primera vez con clic derecho y *Abrir*. Para distribuirla a terceros, fírmala y notarízala (`codesign --deep --options runtime -s "Developer ID Application: …" dist/Runout.app` y luego `xcrun notarytool submit`). Compila en un Mac con Apple Silicon para arm64 y en uno Intel para x86_64.
- **Windows**: algunos antivirus marcan los `.exe` de PyInstaller en modo `--onefile`. Si ocurre, usa el modo carpeta (quita `--onefile`) o firma el ejecutable.
- **Linux**: compila en la distribución más antigua que quieras soportar, porque el binario depende de su glibc. Necesita las librerías de sistema de Qt (en Debian/Ubuntu: `libegl1 libxkbcommon0 libgl1 libfontconfig1`).

## Compilación automática (GitHub Actions)

El flujo `.github/workflows/build.yml` hace en Windows, macOS (Apple Silicon) y Linux lo mismo que los pasos anteriores: instala las dependencias, pasa las pruebas y compila con `runout.spec`.

- **En cada push a `main` y en cada pull request**: los ejecutables quedan como artefactos descargables durante 14 días, en la pestaña *Actions*, dentro de la ejecución.
- **A mano**: en *Actions → Build → Run workflow*. El resultado es el mismo.
- **Al publicar una versión**: sube `__version__` en `runout/__init__.py`, haz commit y crea la etiqueta correspondiente:

  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```

  Si la etiqueta no coincide con `__version__`, el flujo se detiene. Si coincide, crea una versión en *Releases* con `Runout-windows-x64.zip`, `Runout-macos-arm64.zip` y `Runout-linux-x64.tar.gz`.

En repositorios privados, los minutos de Actions son limitados y cada minuto de macOS cuenta como diez. En repositorios públicos son gratuitos.

## Estructura

```
main.py                     punto de entrada
runout/core/                núcleo sin Qt (se puede usar y probar sin interfaz)
    riff.py                 parser RIFF (struct), hash en streaming
    writer.py               plan de chunks, escritura en temporal, reemplazo atómico
    integrity.py            verificación estructural y SHA-256
    axml.py                 EBUCore / ISRC (conserva el resto del XML existente)
    id3chunk.py             mutagen solo en memoria (conserva frames ajenos)
    listinfo.py             LIST-INFO (conserva subchunks ajenos)
    bext.py                 BWF bext (conserva TimeReference, UMID y reservados)
    fields.py               registro de todos los campos y su destino en cada capa
    validators.py           normalización y validación de cada tipo de campo
    cover.py                preparación de imágenes (JPEG RGB, máx. 2 MB)
    reader.py               lectura de todas las capas
    isrc.py, csv_import.py, model.py
    formats/                un manejador por formato, con el guardado verificado común
        base.py             huella, temporal, relectura, reemplazo atómico
        wav.py, id3file.py  WAV; MP3 y AIFF (ID3)
        flac.py, ogg.py     bloques FLAC; Ogg Vorbis y Opus
        vorbis.py, mp4.py   correspondencia de Vorbis Comments; átomos M4A
runout/ui/                  interfaz PySide6 (tabla, editor por secciones, tema e iconos)
runout/i18n.py              traducciones (tr) e idioma activo
runout/locales/             catálogos de traducción (es.json)
assets/                     icono de la app (png, ico, icns)
tools/make_icons.py         genera los iconos
tools/i18n_check.py         revisa los catálogos de traducción
.github/workflows/build.yml compilación y publicación automáticas
docs/                       listado completo de metadatos por estándar (en español)
tests/                      WAV sintéticos, archivos de muestra de cada formato y pruebas
tests/fixtures/             archivos cortos de un seno de 440 Hz (AIFF, FLAC, MP3, M4A, Ogg, Opus)
```

## Licencia

Copyright © 2026 Daniel Rodilla Cahill

Runout es software libre: puedes redistribuirlo y modificarlo bajo los términos de la GNU General Public License publicada por la Free Software Foundation, versión 3 o (a tu elección) cualquier versión posterior. Se distribuye sin ninguna garantía. El texto completo está en [`LICENSE`](LICENSE).

Dependencias y sus licencias: mutagen (GPL-2.0-or-later), PySide6 (LGPL-3.0), Pillow (MIT-CMU), pycountry (LGPL-2.1). Esquemas de validación usados solo en las pruebas, que se descargan al ejecutarlas y no se redistribuyen:

- EBUCore (`EBU_CORE_20130107.xsd`) © European Broadcasting Union, bajo [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). Fuente: [github.com/ebu/MXFTools](https://github.com/ebu/MXFTools), carpeta `EBUCoreSchema/`.
- `simpledc20021212.xsd` (Dublin Core Metadata Initiative) y `xml.xsd` (W3C), tal como los publica la EBU en [github.com/ebu/OSCIED](https://github.com/ebu/OSCIED), carpeta `tools/EBUCore/schemas/`.

