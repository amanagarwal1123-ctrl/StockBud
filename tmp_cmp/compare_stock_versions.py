"""Compare get_current_inventory() output across historical code versions on the
SAME (preview) data. Read-only: uses git archive extracts, never checks out."""
import asyncio
import os
import subprocess
import sys

from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

VERSIONS = [
    ('60b1146', 'Mar 19'),
    ('730a12f', 'Mar 24'),
    ('3e7a3fc', 'Apr 02'),
    ('d91ecbb', 'Jun 01'),
    ('8cc3515', 'Jul 07'),
    ('5b2c5b8', 'Jul 21'),
    ('be2cf9b', 'Oct 01 groups-vanishing fix'),
    ('1dc346c', 'Oct 08 close (yesterday)'),
    ('WORK', 'current working tree'),
]


def extract(sha, dest):
    os.makedirs(dest, exist_ok=True)
    if sha == 'WORK':
        subprocess.run(f'mkdir -p {dest}/backend && cp -r /app/backend/services {dest}/backend/ && cp /app/backend/database.py {dest}/backend/', shell=True, check=True, cwd='/app')
    else:
        subprocess.run(f'git archive {sha} backend/services backend/database.py | tar -x -C {dest}', shell=True, check=True, cwd='/app')


def run_version(sha, label):
    dest = f'/app/tmp_cmp/{sha}'
    try:
        extract(sha, dest)
    except subprocess.CalledProcessError as e:
        print(f'{sha} {label}: extract failed {e}')
        return
    for m in list(sys.modules):
        if m.startswith('services') or m == 'database':
            del sys.modules[m]
    sys.path.insert(0, dest + '/backend')
    try:
        from services.stock_service import get_current_inventory  # noqa
        res = asyncio.run(get_current_inventory())
        inv = res.get('inventory') if isinstance(res, dict) else res
        if inv is None:
            inv = res.get('items', [])
        tot = sum((i.get('net_wt') or 0) for i in inv)
        neg = [i for i in inv if (i.get('net_wt') or 0) < 0]
        off = {k: res.get(k) for k in ('total_net_wt', 'total_gr_wt', 'total_items')} if isinstance(res, dict) else {}
        negl = len(res.get('negative_items') or []) if isinstance(res, dict) else '?'
        print(f'{sha} ({label}): official={off} neg_list={negl} | flat items={len(inv)} flat_net_kg={round(tot/1000,3)}')
    except Exception as e:
        print(f'{sha} ({label}): FAILED -> {type(e).__name__}: {e}')
    finally:
        sys.path.remove(dest + '/backend')


for sha, label in VERSIONS:
    run_version(sha, label)
