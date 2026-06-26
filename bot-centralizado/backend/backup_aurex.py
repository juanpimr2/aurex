# -*- coding: utf-8 -*-
"""
Aurex — Backup + verificacion de integridad de datos
====================================================
SOLO LECTURA sobre los datos de trading: copia los ficheros de datos a una
carpeta de backup con marca de tiempo y guarda un manifest con hash SHA256 y
tamano de cada fichero para poder verificar la integridad mas tarde.

NO toca el broker, NI ordenes, NI dinero, NI la estrategia. NUNCA copia .env
ni credenciales.

Uso:
  python backup_aurex.py            -> crea un backup nuevo + verifica
  python backup_aurex.py --verify   -> verifica el ultimo backup existente
  python backup_aurex.py --list     -> lista los backups disponibles

Destino: variable de entorno AUREX_BACKUP_DIR si existe; si no, ./backups/
(la carpeta del proyecto ya se sincroniza con OneDrive, lo que da una copia
cloud automatica; ver docs/AUDITORIA_TECNICA.md para Google Drive/alternativas).
"""
import os
import sys
import csv
import json
import shutil
import hashlib
from datetime import datetime, timezone

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
BACKUP_ROOT = os.environ.get(
    'AUREX_BACKUP_DIR',
    os.path.join(BASE_DIR, 'backups')
)

# Ficheros y carpetas de DATOS a respaldar. NUNCA incluir .env ni secretos.
DATA_FILES = [
    'aurex_trades.db',
    'trade_log.csv',
    'swing_signal_log.csv',
    'm15_signal_log.csv',
    'm15_trade_state.json',
]
DATA_DIRS = [
    'daily_reports',
]
# Patrones que NUNCA se respaldan (seguridad).
DENY = ('.env', '.bak', '__pycache__')


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _is_denied(name: str) -> bool:
    return any(d in name for d in DENY)


def _collect_files():
    """Devuelve lista de rutas absolutas de datos existentes (no secretos)."""
    out = []
    for f in DATA_FILES:
        p = os.path.join(BASE_DIR, f)
        if os.path.isfile(p) and not _is_denied(f):
            out.append(p)
    for d in DATA_DIRS:
        dp = os.path.join(BASE_DIR, d)
        if os.path.isdir(dp):
            for root, _, files in os.walk(dp):
                for f in files:
                    if not _is_denied(f):
                        out.append(os.path.join(root, f))
    return out


def create_backup() -> str:
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_ROOT, 'aurex_backup_' + ts)
    os.makedirs(dest, exist_ok=True)

    manifest = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': BASE_DIR,
        'files': {},
    }

    files = _collect_files()
    for src in files:
        rel = os.path.relpath(src, BASE_DIR)
        dst = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        manifest['files'][rel] = {
            'sha256': _sha256(src),
            'bytes': os.path.getsize(src),
        }

    with open(os.path.join(dest, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print('[BACKUP] Creado: ' + dest)
    print('[BACKUP] Ficheros: ' + str(len(manifest['files'])))
    # Verificacion inmediata
    ok = verify_backup(dest)
    print('[BACKUP] Integridad: ' + ('OK' if ok else 'FALLO'))
    return dest


def verify_backup(path: str) -> bool:
    mpath = os.path.join(path, 'manifest.json')
    if not os.path.isfile(mpath):
        print('[VERIFY] No hay manifest en ' + path)
        return False
    with open(mpath, encoding='utf-8') as f:
        manifest = json.load(f)
    all_ok = True
    for rel, meta in manifest['files'].items():
        fp = os.path.join(path, rel)
        if not os.path.isfile(fp):
            print('  [!] FALTA: ' + rel)
            all_ok = False
            continue
        if _sha256(fp) != meta['sha256']:
            print('  [!] HASH NO COINCIDE: ' + rel)
            all_ok = False
    return all_ok


def list_backups():
    if not os.path.isdir(BACKUP_ROOT):
        print('No hay backups todavia en ' + BACKUP_ROOT)
        return []
    items = sorted(
        d for d in os.listdir(BACKUP_ROOT)
        if d.startswith('aurex_backup_')
    )
    for d in items:
        print('  ' + d)
    return items


def latest_backup():
    items = list_backups()
    return os.path.join(BACKUP_ROOT, items[-1]) if items else None


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if arg == '--list':
        list_backups()
    elif arg == '--verify':
        last = latest_backup()
        if last:
            ok = verify_backup(last)
            print('[VERIFY] ' + last + ' -> ' + ('OK' if ok else 'FALLO'))
            sys.exit(0 if ok else 1)
        else:
            print('No hay backups que verificar.')
            sys.exit(1)
    else:
        create_backup()
