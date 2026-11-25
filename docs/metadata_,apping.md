================================================================================
REFERENCIA COMPLETA DE METADATOS DE AUDIO POR ESTÁNDAR
Uso recomendado: Especificación técnica para desarrollo de software de audio,
sellos discográficos independientes, distribución digital, radio y sync.
================================================================================

ÍNDICE
1. ID3v2 (v2.3 / v2.4) - Estándar para MP3 y chunk 'id3 ' en WAV
2. RIFF LIST-INFO - Metadatos nativos clásicos de archivos WAV
3. BWF (Broadcast Wave Format - chunk 'bext') - Estándar EBU Tech 3285
4. AXML (chunk 'axml' / EBUCore) - Estándar EBU Tech 3352 para Radio / ISRC
5. VORBIS COMMENTS - Estándar para FLAC, OGG y Opus
6. TABLA MAESTRA DE EQUIVALENCIAS (Mapeo simultáneo para WAV)

================================================================================
1. ID3v2 (v2.3 / v2.4)
================================================================================
Es el estándar más extenso. En archivos WAV se incrusta dentro de un chunk 
llamado 'id3 ' (con espacio al final) o 'ID3 '.

--- A. IDENTIFICACIÓN DE PISTA Y ÁLBUM ---
TIT1 | Agrupación de contenido / Obra (Content group description)
TIT2 | Título de la pista / canción (Title)
TIT3 | Subtítulo / Versión / Remix (Subtitle / Description refinement)
TALB | Título del álbum (Album)
TOAL | Título del álbum original (para versiones/reediciones)
TRCK | Número de pista / Total de pistas (ej. 01/10)
TPOS | Número de disco / Total de discos (ej. 1/2)
TSST | Subtítulo del disco (Set subtitle, útil en cajas o discos dobles)
TCON | Género musical (Content type)
TMED | Tipo de soporte original (Media type, ej. DIG, CD, VINYL)

--- B. ARTISTAS, AUTORES Y CRÉDITOS ---
TPE1 | Artista principal / Intérprete (Lead performer)
TPE2 | Artista del álbum / Banda (Album Artist)
TPE3 | Director de orquesta (Conductor)
TPE4 | Remezclador / Modificado por (Interpreted, remixed, or modified by)
TOPE | Artista original (Original artist, clave en versiones/parodias)
TCOM | Compositor de la música (Composer)
TEXT | Letrista / Autor del texto (Lyricist)
TOLY | Letrista original (Original lyricist)
TIPL | Personas involucradas (Involved people list - ID3v2.4; en v2.3 es IPLS)
TMCL | Créditos de músicos e instrumentos (Musician credits list - v2.4)
TPUB | Sello discográfico / Editorial (Publisher)
TENC | Codificado por (Encoded by)
TSSE | Software/Hardware usado para la codificación

--- C. FECHAS Y ORDENACIÓN (SORTING) ---
TDRC | Fecha de grabación / lanzamiento en formato ISO (v2.4, ej. 2026-11-25)
TYER | Año de lanzamiento (solo v2.3, sustituido por TDRC en v2.4)
TDAT | Día y mes en formato DDMM (solo v2.3)
TIME | Hora en formato HHMM (solo v2.3)
TDOR | Fecha de lanzamiento original (v2.4; en v2.3 es TORY)
TDRL | Fecha oficial de publicación (Release time - v2.4)
TDEN | Fecha de codificación (Encoding time - v2.4)
TDTG | Fecha de etiquetado (Tagging time - v2.4)
TSOA | Ordenación de álbum (Album sort order, ej. "Buena Gente" sin "La")
TSOP | Ordenación de artista (Performer sort order)
TSOT | Ordenación de título (Title sort order)

--- D. DERECHOS, PROPIEDAD E IDENTIFICADORES ---
TSRC | Código ISRC (12 caracteres alfanuméricos sin guiones)
TCOP | Aviso de Copyright (ej. "2026 Discos Ejemplo")
TPRO | Aviso de producción / Fonograma ℗ (Produced notice - v2.4)
TOWN | Propietario del archivo / Licenciatario (File owner)
TRSN | Nombre de la emisora de radio por internet
TRSO | Propietario de la emisora de radio
UFID | Identificador único de archivo (Unique File Identifier)
MCDI | Identificador de CD de música (TOC binario del CD)
PRIV | Marco privado (datos propietarios de software/sellos)
GRID | Registro de identificación de grupo
COMR | Marco comercial (precio, validez, vendedor)
OWNE | Marco de propiedad (precio pagado, fecha de compra, vendedor)

--- E. MUSICALES, SYNC, DJs Y LETRAS ---
TBPM | Tempo en pulsaciones por minuto (BPM, número entero)
TKEY | Tonalidad musical inicial (Initial key, ej. Am, F#m, C)
TMOO | Ambiente / Estado de ánimo (Mood - v2.4, ej. Energetic, Dark)
TLAN | Idioma de la pista (código ISO-639-2 de 3 letras, ej. spa, eng, cat)
TLEN | Duración del audio en milisegundos
USLT | Letra no sincronizada (Unsynchronised lyrics)
SYLT | Letra sincronizada con códigos de tiempo (Synchronised lyrics)
COMM | Comentarios (muy usado para añadir contacto de Sync/Licensing)
POPM | Popularidad / Valoración (Rating 0-255 + contador)
PCNT | Contador de reproducciones (Play counter)
RVA2 | Ajuste relativo de volumen (v2.4; en v2.3 es RVAD)

--- F. ENLACES WEB (URLs) ---
WCOM | Información comercial (enlace a tienda/Shopify)
WCOP | Información legal / Copyright
WOAF | Web oficial del archivo de audio
WOAR | Web oficial del artista / banda
WOAS | Web oficial de la fuente de audio
WORS | Web oficial de la emisora de radio
WPAY | Enlace de pago / compra directa
WPUB | Web oficial del sello discográfico (Publisher)
WXXX | URL personalizada definida por el usuario

--- G. IMÁGENES, ADJUNTOS Y CAMPOS PERSONALIZADOS ---
APIC | Imagen incrustada (Carátula frontal, trasera, foto artista, logo sello)
GEOB | Objeto encapsulado genérico (permite incrustar un PDF o archivo)
TXXX | Campo de texto definido por el usuario (Par Clave = Valor)

   * Campos TXXX estandarizados de facto en la industria musical:
     - CATALOGNUMBER    : Número de catálogo del sello (ej. DEJ-001)
     - BARCODE          : Código UPC / EAN del lanzamiento
     - ISWC             : Código internacional de la obra musical
     - RELEASECOUNTRY   : País de lanzamiento (ISO 3166-1, ej. ES)
     - RELEASETYPE      : Tipo de lanzamiento (album, single, ep, compilation)
     - RELEASESTATUS    : Estado (official, promotion, bootleg)
     - SCRIPT           : Alfabeto usado (ej. Latn)
     - REPLAYGAIN_TRACK_GAIN / REPLAYGAIN_TRACK_PEAK
     - REPLAYGAIN_ALBUM_GAIN / REPLAYGAIN_ALBUM_PEAK
     - MUSICBRAINZ_TRACKID / MUSICBRAINZ_ALBUMID / MUSICBRAINZ_ARTISTID


================================================================================
2. RIFF LIST-INFO (NATIVO DE ARCHIVOS WAV)
================================================================================
Bloque nativo de la especificación RIFF (Microsoft/IBM). No soporta carátulas
y tiene limitaciones con caracteres especiales (se recomienda ASCII/UTF-8),
pero es lo que lee el Explorador de Windows y software antiguo.

INAM | Título de la pista (Name)
IART | Artista / Autor (Artist)
IPRD | Nombre del álbum / Producto (Product)
ICRD | Fecha de creación / Año (Creation date, ej. 2026-11-25)
IGNR | Género musical (Genre)
ICMT | Comentarios (Comments)
ICOP | Copyright (ej. "2026 Discos Ejemplo")
IENG | Ingeniero de sonido / Mastering (Engineer)
ISFT | Software utilizado para crear el archivo (Software)
ISRC | Fuente / Sello / Proveedor original (Source - OJO: no siempre es el código ISRC)
ITRK | Número de pista (Track number - extensión estándar de facto)
IPRT | Número de pista (Part - variante usada por algunos editores)
IKEY | Palabras clave / Etiquetas de búsqueda (Keywords)
ISBJ | Asunto / Descripción breve (Subject)
IMED | Soporte físico original (Medium)
ISRF | Forma de la fuente original (Source form)
ITCH | Técnico que digitalizó el archivo (Technician)
IARL | Ubicación física de archivo (Archival location)
ICMS | Entidad que encargó la grabación (Commissioned)


================================================================================
3. BWF - BROADCAST WAVE FORMAT (CHUNK 'bext')
================================================================================
Estándar EBU Tech 3285 usado en radio, cine, TV y estudios de mastering.
Es un bloque de tamaño binario fijo seguido de un campo de texto libre al final.

Description          | 256 bytes | Descripción libre de la pista/escena
Originator           |  32 bytes | Nombre del creador / estudio / sello
OriginatorReference  |  32 bytes | Referencia única del archivo (ej. código sesión)
OriginationDate      |  10 bytes | Fecha de creación (AAAA-MM-DD)
OriginationTime      |   8 bytes | Hora de creación (HH:MM:SS)
TimeReference        |   8 bytes | Posición en muestras desde medianoche (Timecode)
Version              |   2 bytes | Versión BWF (0, 1 o 2; v2 añade Loudness)
UMID                 |  64 bytes | Unique Material Identifier (estándar SMPTE)
LoudnessValue        |   2 bytes | Sonoridad integrada (LUFS * 100, ej. -1400 = -14.0 LUFS)
LoudnessRange        |   2 bytes | Rango dinámico de sonoridad (LU * 100)
MaxTruePeakLevel     |   2 bytes | Pico real máximo (dBTP * 100, ej. -100 = -1.0 dBTP)
MaxMomentaryLoudness |   2 bytes | Sonoridad momentánea máxima (400 ms)
MaxShortTermLoudness |   2 bytes | Sonoridad a corto plazo máxima (3 s)
Reserved             | 180 bytes | Reservado para expansión futura (ceros)
CodingHistory        | Variable  | Historial técnico (ej. A=PCM,F=44100,W=24,M=stereo)


================================================================================
4. AXML (CHUNK 'axml' - EBUCore / EBU Tech 3352)
================================================================================
Estándar oficial de la Unión Europea de Radiodifusión (EBU) para incrustar
metadatos XML estructurados en WAV. Es el bloque que leen las radios FM,
BMAT, Sonoris ISRC Editor y BWF MetaEdit para detectar el código ISRC.

--- ELEMENTOS PRINCIPALES EBUCore ---
dc:title             | Título de la grabación
dc:creator           | Artista / Creador
dc:publisher         | Sello discográfico (Publisher)
dc:rights            | Derechos / Copyright
dc:date              | Fecha de publicación
dc:identifier        | Identificadores oficiales mediante atributo typeLabel:
                       - typeLabel="ISRC" (ej. ISRC:ESABC2600001)
                       - typeLabel="ISWC"
                       - typeLabel="UPC" o "EAN"
                       - typeLabel="CATALOGNUMBER"

--- PLANTILLA XML MÍNIMA OFICIAL PARA ISRC (Compatible con Sonoris / BMAT) ---
<ebucore:ebuCoreMain xmlns:dc="http://purl.org/dc/elements/1.1/"
                     xmlns:ebucore="urn:ebu:metadata-schema:ebuCore_2012">
  <ebucore:coreMetadata>
    <ebucore:identifier typeLabel="GUID" typeDefinition="Globally Unique Identifier" formatLabel="ISRC" formatDefinition="International Standard Recording Code">
      <dc:identifier>ISRC:ESABC2600001</dc:identifier>
    </ebucore:identifier>
  </ebucore:coreMetadata>
</ebucore:ebuCoreMain>

(Nota técnica: El chunk 'axml' en RIFF debe tener longitud en bytes par;
si el XML tiene un número impar de bytes, se añade 1 byte nulo 0x00 al final).


================================================================================
5. VORBIS COMMENTS (FLAC / OGG / OPUS)
================================================================================
Estándar de pares CLAVE=VALOR en UTF-8. Es el formato más limpio y fiable
para venta de audio sin pérdida (lossless) en tiendas digitales como Shopify.
No distingue mayúsculas/minúsculas en las claves (por convención, MAYÚSCULAS).

--- CAMPOS OFICIALES XIPH.ORG ---
TITLE          | Título de la canción
VERSION        | Versión / Remix / Subtítulo
ALBUM          | Título del álbum
TRACKNUMBER    | Número de pista
ARTIST         | Artista principal
PERFORMER      | Intérpretes / Músicos
COPYRIGHT      | Aviso de Copyright
LICENSE        | Información de licencia
ORGANIZATION   | Sello discográfico (equivalente a Publisher)
DESCRIPTION    | Descripción o comentarios
GENRE          | Género musical
DATE           | Fecha de lanzamiento (AAAA o AAAA-MM-DD)
LOCATION       | Lugar de grabación
CONTACT        | Correo o web de contacto (ideal para Sync/Sello)
ISRC           | Código ISRC (12 caracteres sin guiones)

--- CAMPOS EXTENDIDOS ESTÁNDAR EN LA INDUSTRIA (FLAC) ---
ALBUMARTIST    | Artista del álbum
TRACKTOTAL     | Total de pistas del álbum (o TOTALTRACKS)
DISCNUMBER     | Número de disco
DISCTOTAL      | Total de discos (o TOTALDISCS)
COMPOSER       | Compositor
LYRICIST       | Letrista
PUBLISHER      | Sello discográfico (se suele duplicar junto a ORGANIZATION)
LABEL          | Sello discográfico (variante común)
CATALOGNUMBER  | Número de catálogo del sello
BARCODE        | Código UPC / EAN
ISWC           | Código de la obra musical
BPM            | Tempo en BPM
INITIALKEY     | Tonalidad musical
MOOD           | Ambiente / Mood
LANGUAGE       | Idioma
LYRICS         | Letra completa
COMMENT        | Comentarios
URL            | Web oficial

(Nota: En FLAC, la carátula no va en Vorbis Comments sino en un bloque
binario dedicado llamado METADATA_BLOCK_PICTURE).


================================================================================
6. TABLA MAESTRA DE EQUIVALENCIAS PARA TU APP (ESCRITURA SIMULTÁNEA EN WAV)
================================================================================
Campo en UI       | ID3v2 (id3 )          | RIFF (LIST-INFO) | AXML (EBUCore)
------------------+-----------------------+------------------+-------------------
Título            | TIT2                  | INAM             | dc:title
Artista           | TPE1                  | IART             | dc:creator
Artista Álbum     | TPE2                  | (no existe)      | -
Álbum             | TALB                  | IPRD             | -
Nº Pista          | TRCK (ej. 01/10)      | ITRK             | -
Año / Fecha       | TDRC (v2.4)/TYER(2.3) | ICRD             | dc:date
Género            | TCON                  | IGNR             | -
Sello / Publisher | TPUB                  | ISRC (o ICMT)    | dc:publisher
Copyright         | TCOP                  | ICOP             | dc:rights
ISRC              | TSRC                  | (no usar ISRC*)  | dc:identifier(ISRC)
Compositor        | TCOM                  | (no existe)      | -
Letrista          | TEXT                  | (no existe)      | -
BPM               | TBPM                  | (no existe)      | -
Tonalidad         | TKEY                  | (no existe)      | -
Nº Catálogo       | TXXX:CATALOGNUMBER    | (no existe)      | dc:identifier
UPC / EAN         | TXXX:BARCODE          | (no existe)      | dc:identifier
Comentarios/Sync  | COMM                  | ICMT             | -
Carátula          | APIC                  | (no soportado)   | (no soportado)

*Nota sobre RIFF 'ISRC': En la especificación antigua de Microsoft RIFF de 1991,
el código 'ISRC' significaba "Source" (proveedor del archivo), NO el código
estándar musical ISRC. Por eso el ISRC real en WAV debe escribirse siempre
en el chunk 'axml' (para radio/pro) y en el frame 'TSRC' de 'id3 ' (para
reproductores modernos).
================================================================================