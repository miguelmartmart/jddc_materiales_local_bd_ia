"""Resumen editorial local con fuentes fechadas; sin sondeos ni ejecuciones."""
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
from . import core,knowledge

RELATIVE = 'CENTROAPPSJDDC/docs/RESUMEN-EQUIPO-WINDOWS-20261026.json'


def inventory(workspace):
    workspace = Path(workspace).absolute()
    path = workspace / RELATIVE
    try:
        path = knowledge.data_path(workspace,'equipment_summary',RELATIVE)
        if not path.exists():return []
        data = json.loads(core.safe_file(path, workspace))
        if not isinstance(data, dict) or data.get('schema') != 'jddc-equipment-summary/1':
            raise ValueError('schema')
        stamp = datetime.fromisoformat(data['generated_at'])
        entries = data['entries']
        if stamp.tzinfo is None or not isinstance(entries, list) or len(entries) > 40:
            raise ValueError('shape')
        rows = []
        kinds = {'informes', 'aplicaciones', 'pendientes', 'red', 'certificados', 'actualizaciones', 'configuracion'}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'kind', 'name', 'state', 'detail', 'path'}:
                raise ValueError('entry')
            if any(not isinstance(value, str) for value in entry.values()):
                raise ValueError('type')
            if entry['kind'] not in kinds or entry['state'] not in core.STATES:
                raise ValueError('state')
            relative = PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or ':' in entry['path'] or '\\' in entry['path']:
                raise ValueError('path')
            row = core.row(entry['kind'], entry['name'], entry['state'], entry['detail'], workspace / str(relative))
            row.update(source='equipment_summary', checked_at=stamp.isoformat())
            rows.append(row)
        return rows
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        return [dict(core.row('informes', 'Resumen Windows | no disponible', 'bloqueado',
            'No se pudo validar el resumen local. Consultar los originales; no se presume exito.',
            path, 'INVALID_CONFIG'), source='equipment_summary')]
