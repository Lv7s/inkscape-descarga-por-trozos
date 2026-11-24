#!/usr/bin/env python3
"""Descarga un archivo grande por rangos HTTP pequeños, reintentando cada trozo.

Sirve cuando un servidor o CDN corta la descarga normal a los pocos MiB
(curl: "HTTP/2 stream reset", "end of response with N bytes missing", o un
503 intermitente) pero sí entrega rangos pequeños.

Uso:
  python3 descarga_por_trozos.py URL SALIDA [--sha256 HUELLA] [--trozo-mib 1] [--intentos 14]

Si pasas --sha256, el archivo solo se da por bueno si la huella coincide.
Solo usa la biblioteca estándar de Python 3.
"""
import argparse, hashlib, os, sys, time, urllib.request


def tamano_total(url, intentos):
    """Tamaño total: Content-Length de HEAD, o Content-Range de un rango de 1 byte."""
    for i in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=90) as r:
                n = r.headers.get("Content-Length")
                if n:
                    return int(n)
        except Exception as e:
            print(f"HEAD intento {i}: {type(e).__name__} {e}", flush=True)
        try:
            req = urllib.request.Request(url, headers={"Range": "bytes=0-0", "User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=90) as r:
                cr = r.headers.get("Content-Range", "")
                if "/" in cr:
                    return int(cr.rsplit("/", 1)[1])
        except Exception as e:
            print(f"rango 0-0 intento {i}: {type(e).__name__} {e}", flush=True)
        time.sleep(1)
    sys.exit("No pude saber el tamaño total del archivo.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("salida")
    ap.add_argument("--sha256", help="huella publicada por el proveedor")
    ap.add_argument("--trozo-mib", type=int, default=1)
    ap.add_argument("--intentos", type=int, default=14)
    a = ap.parse_args()

    if os.path.exists(a.salida):
        sys.exit(f"{a.salida} ya existe; no se sobrescribe.")

    chunk = a.trozo_mib * 1024 * 1024
    total = tamano_total(a.url, a.intentos)
    n = (total + chunk - 1) // chunk
    print(f"tamaño={total} bytes, trozos={n}", flush=True)

    with open(a.salida, "wb") as f:
        f.truncate(total)

    fallos, t0 = 0, time.time()
    with open(a.salida, "r+b") as f:
        for i in range(n):
            ini = i * chunk
            fin = min(ini + chunk, total) - 1
            esperado = fin - ini + 1
            data = None
            for intento in range(1, a.intentos + 1):
                # En los intentos pares se añade un parámetro para saltar un caché defectuoso.
                url = a.url if intento % 2 else f"{a.url}{'&' if '?' in a.url else '?'}cb={ini}x{intento}"
                req = urllib.request.Request(url, headers={"Range": f"bytes={ini}-{fin}", "User-Agent": "curl/8"})
                try:
                    with urllib.request.urlopen(req, timeout=90) as r:
                        buf = r.read()
                    if len(buf) == esperado:
                        data = buf
                        break
                    print(f"trozo {i} intento {intento}: corto {len(buf)}/{esperado}", flush=True)
                except Exception as e:
                    print(f"trozo {i} intento {intento}: {type(e).__name__} {e}", flush=True)
                fallos += 1
                time.sleep(0.6)
            if data is None:
                sys.exit(f"TROZO {i} FALLIDO ({ini}-{fin}). Se detiene; el archivo parcial NO es válido.")
            f.seek(ini)
            f.write(data)
            if i % 10 == 0:
                print(f"progreso {i+1}/{n} ({100*(i+1)//n}%) reintentos={fallos} t={time.time()-t0:.0f}s", flush=True)

    h = hashlib.sha256()
    with open(a.salida, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    print(f"trozos={n} reintentos={fallos} segundos={time.time()-t0:.0f}")
    print("sha256 =", h.hexdigest())
    if a.sha256:
        ok = h.hexdigest() == a.sha256.lower()
        print("coincide con la huella publicada:", ok)
        sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
