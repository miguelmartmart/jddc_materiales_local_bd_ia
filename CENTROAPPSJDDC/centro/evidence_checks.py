"""Comprobaciones locales de integridad; no califican la veracidad semántica."""
import hashlib
import json
from datetime import datetime
from . import core


def local_time(value):
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            return value + ' (zona no indicada)'
        return stamp.astimezone().strftime('%d/%m/%Y %H:%M:%S %z') + ' (hora del equipo)'
    except (ValueError, TypeError):
        return 'Fecha no válida'


def integrity(path, workspace):
    raw = core.safe_file(path, workspace, 2 * 1024 * 1024)
    digest = hashlib.sha256(raw).hexdigest()
    report = path.parent / 'RESULTADOS.json'
    expected = None
    if report.is_file():
        data = json.loads(core.safe_file(report, workspace, 2 * 1024 * 1024))
        if not isinstance(data, dict):
            raise ValueError('Invalid report')
        expected = data.get('private_sha256') if path.name in {'DATOS-ERP-PRIVADOS.json', 'INTEGRADA-PRIVADA.json'} else data.get('transcript_sha256')
    if expected is not None and expected != digest:
        raise ValueError('Integrity mismatch')
    return ('Huella coincide con el informe local' if expected else 'Sin huella previa para contraste') + '\nSHA-256: ' + digest + '\nNo es una firma ni acredita autoría o exactitud.\n'


def basic_checks(turns):
    empty = sum(not r['answer'].strip() and not r.get('proposal_received') for r in turns)
    truncated = sum(bool(r.get('answer_truncated')) for r in turns)
    keys = [(r.get('case'), r.get('turn')) for r in turns]
    duplicates = len(keys) - len(set(keys))
    return (f'CONTROL DE CAPTURA: {len(turns)} turnos; {empty} sin respuesta ni propuesta; '
            f'{truncated} truncados; {duplicates} identificadores repetidos.\n'
            'Estos controles no evalúan si la respuesta es correcta o pertinente.\n')


def comparison_text(capture, workspace):
    path = capture.parent / 'CONTRASTE.json'
    if not path.exists():
        return 'Contraste de celdas: pendiente; no hay informe local.\n'
    try:
        data = json.loads(core.safe_file(path, workspace))
        labels = {'match': 'Coinciden las celdas de la muestra', 'mismatch': 'Hay diferencias en la muestra',
                  'blocked': 'Contraste bloqueado', 'inconclusive': 'Contraste no concluyente'}
        if not isinstance(data, dict) or data.get('schema') != 'devia-cell-comparison/1' or data.get('status') not in labels:
            raise ValueError('schema')
        digest = hashlib.sha256(core.safe_file(capture, workspace, 2 * 1024 * 1024)).hexdigest()
        if data.get('capture_sha256') != digest:
            raise ValueError('stale')
        if any(type(data.get(k)) is not int or not 0 <= data[k] <= 3 for k in ('cells_checked', 'different_cells')):
            raise ValueError('counts')
        if data['different_cells'] > data['cells_checked']:
            raise ValueError('counts')
        if data['status'] == 'match' and (data['cells_checked'] == 0 or data['different_cells'] != 0 or data.get('same_dataset_declared') is not True or data.get('same_selection_declared') is not True):
            raise ValueError('false match')
        return ('Contraste: ' + labels[data['status']] + f". Celdas: {data['cells_checked']}; diferencias: {data['different_cells']}.\n"
                'Contexto declarado por el revisor; no acredita autoría, misma base ni veracidad global.\n')
    except (OSError, ValueError, TypeError):
        return 'Contraste no válido o no corresponde a esta captura; no se acepta como comprobado.\n'
