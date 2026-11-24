"""Portable observation paths and stable identities for relocated local runs."""
from pathlib import Path


def observation_path(data_dir, recorded):
    # Prefer this run's local copy. Historic indices recorded absolute paths.
    local = Path(data_dir) / 'observations' / Path(recorded).name
    if local.is_file():
        return local
    legacy = Path(recorded)
    if legacy.is_absolute() and legacy.is_file():
        return legacy
    raise FileNotFoundError('Missing observation: ' + str(local))


def stable_index(index):
    records = []
    for record in index['records']:
        row = {k:v for k,v in record.items() if k != 'cached'}
        if 'observation' in row:
            row['observation'] = Path(row['observation']).name
        records.append(row)
    return dict(index, records=sorted(records, key=lambda r:r['path']))
