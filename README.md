# Descargar por trozos cuando el servidor corta la descarga

*English summary at the bottom.*

Cuando un servidor o CDN corta una descarga grande a los pocos MiB, pero entrega bien rangos pequeños, se puede bajar el archivo pidiéndolo **por trozos de 1 MiB con reintentos** y comprobando al final la huella SHA-256 publicada por el proveedor.

Este repositorio documenta el caso real que lo motivó y trae el script.

## El caso (24-11-2026, São Paulo, Brasil)

No se podía descargar el instalador de Inkscape 1.4.4 para macOS (Apple Silicon) desde inkscape.org, ni con el navegador ni con `curl`.

Lo que se midió desde otra máquina (Linux) de la misma ciudad:

| Prueba | Resultado |
|---|---|
| Descarga normal con `curl -L` | Se corta siempre a 4.194.304 bytes (4 MiB). Archivo completo: 156.920.591 bytes |
| Error de `curl` | `(92) HTTP/2 stream reset` o `(18) end of response with N bytes missing` |
| Con `--http1.1` y reintentos | Mismo corte a los 4 MiB |
| Página de descarga | Error 502 en 6 de 10 intentos; cuando carga, tarda 30 a 40 s |
| Respuesta del servidor al fallar | `503 Backend unavailable, connection timeout` (Varnish, nodo `cache-gru-*` de Fastly) |
| Otros servidores (100 MB de Hetzner, 10 MB de OVH) | Se descargan completos: la conexión no era el problema |

Conclusión: el fallo estaba en el servidor de Inkscape, no en el equipo ni en la red del usuario. Los rangos pequeños (`Range: bytes=...`) sí se servían, aunque con muchos reintentos fallidos.

Resultado: 150 trozos de 1 MiB, unos 15 minutos y 150 reintentos fallidos en total. El archivo final tuvo el mismo SHA-256 que publica Inkscape y que declara el cask de Homebrew.

> Eso describe un momento y un nodo concretos. Hoy el servidor puede estar bien, y no lo probé desde otras ciudades ni operadoras. No encontré nada que indique un bloqueo en Brasil.

## Uso

Solo necesita Python 3 (biblioteca estándar).

```bash
python3 descarga_por_trozos.py URL SALIDA --sha256 HUELLA_PUBLICADA
```

Ejemplo con el caso original (la huella sale del proveedor, no de este repositorio):

```bash
python3 descarga_por_trozos.py \
  https://media.inkscape.org/dl/resources/file/Inkscape-1.4.4_arm64.dmg \
  Inkscape-1.4.4_arm64.dmg \
  --sha256 eacca94ab01e59467cdd5452a2867c3734450f9a4cfb3346956cc9b07f34f3f1
```

Opciones: `--trozo-mib N` (tamaño del trozo, 1 por defecto) y `--intentos N` (reintentos por trozo, 14 por defecto).

Qué hace:

1. Averigua el tamaño total (`HEAD` o un rango de 1 byte).
2. Pide cada trozo con `Range: bytes=inicio-fin` y lo reintenta hasta que llega con el tamaño exacto. En los intentos pares añade un parámetro `?cb=` para saltar un caché defectuoso.
3. Si un trozo falla todos los intentos, se detiene y avisa: el archivo parcial no sirve.
4. Calcula el SHA-256 y, si diste `--sha256`, termina con error cuando no coincide.
5. No sobrescribe un archivo existente.

## Cautelas

- **Verifica siempre la huella contra la fuente oficial**, no contra la que te dé quien te pasó el archivo. Descargar por trozos no cambia lo que te entrega el servidor; la huella es lo que prueba que el archivo es el correcto.
- Si el servidor no acepta rangos (`Accept-Ranges: bytes`), este método no sirve.
- Respeta los términos del sitio. Son una petición por trozo, con una pausa corta tras cada fallo; no lo uses para saturar un servidor.
- Cuando hay otra forma oficial de instalar (por ejemplo `brew install --cask inkscape`), prueba esa primero.
- Software sin garantía, uso bajo tu responsabilidad.
- Probé el script con un archivo pequeño; el caso completo de Inkscape lo hizo una versión previa del mismo método, con el resultado descrito arriba.

## English summary

If a server/CDN cuts large downloads after a few MiB but still serves small `Range` requests, download the file in 1 MiB chunks with retries and verify the vendor-published SHA-256. `descarga_por_trozos.py` does exactly that (Python 3 stdlib only). Case study: Inkscape 1.4.4 macOS `.dmg` from São Paulo on 2026-11-24: plain `curl` always stopped at 4 MiB (HTTP/2 stream reset, 503 "Backend unavailable" from the CDN edge), while 150 ranged requests assembled a file whose SHA-256 matched the published one. Always verify the checksum against the official source.

MIT License.
