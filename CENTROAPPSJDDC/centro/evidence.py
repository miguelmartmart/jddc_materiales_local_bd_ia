"""Fichas de evidencia DEVIA sin copiar preguntas, respuestas ni datos ERP."""
import json
from datetime import datetime
from pathlib import Path
from . import core


def summarize(path, workspace):
    try:
        data = json.loads(core.safe_file(path, workspace, 2 * 1024 * 1024))
        if not isinstance(data, dict): raise ValueError('schema')
        mode = data.get('mode')
        if data.get('schema') == 'devia-client-validation/1':
            if data.get('synthetic_only') is not True: raise ValueError('scope')
            records = data.get('records')
            allowed = {'pass', 'fail', 'error', 'skip', 'expected_failure', 'unexpected_success'}
            if not isinstance(records, list) or any(not isinstance(r, dict) or not isinstance(r.get('status'), str) or r['status'] not in allowed for r in records):
                raise ValueError('records')
            counts = {s: sum(r['status'] == s for r in records) for s in allowed}
            pending = counts['expected_failure'] + counts['skip']
            failed = counts['fail'] + counts['error'] + counts['unexpected_success']
            state = 'fallo' if failed else 'parcial' if pending else 'no_comprobado'
            detail = (f"SINTÉTICO: {counts['pass']} aprobados; {counts['skip']} omitidos; "
                      f"{counts['expected_failure']} fallos conocidos; {failed} fallos inesperados. "
                      'No son conversaciones con IA/ERP reales. No sumar campañas históricas.')
        elif mode in {'real_broker_public_prompts_no_query_execution', 'web_real_no_erp_execution'}:
            steps = data.get('steps', [])
            if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps): raise ValueError('steps')
            turns = sum('case' in s and 'turn' in s for s in steps)
            status = data.get('state')
            if status not in {'running', 'blocked', 'transport_completed_semantic_review_pending'}: raise ValueError('status')
            state = 'bloqueado' if status == 'blocked' else 'no_comprobado'
            label = 'Bloqueada' if status == 'blocked' else 'Sin cierre acreditado' if not data.get('finished_at') else 'Transporte completado; semántica no evaluada'
            detail = f'INTENTO REAL: {label}. Turnos registrados: {turns}. Sin ejecución ERP solicitada. '
            detail += 'No acredita veracidad de datos ni conversaciones completas con ERP. '
            if status == 'running': detail += 'El archivo indica running; no demuestra que el proceso siga activo. '
            if data.get('error_type') in {'TimeoutError', 'ConnectTimeout', 'ReadTimeout', 'RuntimeError', 'ValueError', 'PermissionError'}:
                detail += 'Error tipado: ' + data['error_type'] + '. '
        elif mode == 'real_integrated_one_row':
            status = data.get('state')
            if status not in {'running', 'blocked', 'blocked_plan_not_exact', 'blocked_no_execution',
                              'blocked_result_contract', 'completed_pending_comparison'}:
                raise ValueError('integrated status')
            comparison = data.get('independent_comparison', 'pending')
            if comparison not in {'pending', 'pass', 'fail', 'blocked'}:
                raise ValueError('comparison')
            steps = data.get('steps', [])
            if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
                raise ValueError('integrated steps')
            if status == 'completed_pending_comparison' and not any(s.get('phase') == 'execute' and s.get('executed') is True for s in steps):
                raise ValueError('missing execution')
            closed = data.get('cleanup') == 'pass'
            state = 'parcial' if status == 'completed_pending_comparison' and closed and comparison != 'fail' else 'bloqueado'
            detail = ('INTENTO REAL: prueba integrada de una fila. Estado: ' + str(data.get('state')) +
                      '. Contraste independiente: ' + comparison +
                      ('. Cierre confirmado' if closed else '. Cierre no confirmado') +
                      '. Ver pregunta, plan y filas en el visor privado. No acredita todas las consultas.')
        elif mode == 'real_erp_readonly_sample':
            steps = data.get('steps', [])
            if not isinstance(steps, list) or data.get('state') not in {'completed', 'blocked', 'running'}:
                raise ValueError('ERP schema')
            if len(steps) > 5 or any(not isinstance(s, dict) or s.get('state') != 'pass' for s in steps):
                raise ValueError('ERP steps')
            if data['state'] == 'completed' and len(steps) != 5:
                raise ValueError('ERP incomplete')
            state = 'parcial' if data['state'] == 'completed' and data.get('cleanup') == 'pass' else 'bloqueado'
            detail = ('ERP REAL: ' + data['state'] + '. SELECT registrados: ' + str(len(steps)) +
                      '. Transacción solo lectura; muestra máxima de tres filas numéricas por tabla. '
                      'Sin IA. No acredita conversación integrada ni todas las consultas del ERP. '
                      + ('Cierre confirmado. ' if data.get('cleanup') == 'pass' else 'Cierre no confirmado. ') +
                      'Los datos originales se consultan en el visor privado.')
        elif data.get('http_sent') is False and isinstance(data.get('steps'), list):
            pieces = []
            for step in data['steps']:
                if not isinstance(step, dict) or step.get('service') not in ('broker', 'web', 'alta'): raise ValueError('service')
                if step.get('tcp') not in ('pass', 'fail', 'not_run') or step.get('tls') not in ('pass', 'fail', 'not_run'): raise ValueError('state')
                pieces.append(f"{step['service']}: TCP={step['tcp']}, TLS={step['tls']}")
            state = 'parcial'
            detail = 'RED REAL: ' + '; '.join(pieces) + '. Sin HTTP, login, conversación ni consulta ERP.'
        else:
            raise ValueError('unknown evidence')
        record = core.row('informes', 'DEVIA · ' + path.parent.name + ' · ' + path.name, state, detail, path)
        timestamp = data.get('finished_at') or data.get('generated_at') or data.get('started_at')
        if timestamp:
            stamp = datetime.fromisoformat(timestamp)
            if stamp.tzinfo is None: raise ValueError('timezone')
            record['checked_at'] = stamp.isoformat()
        return record
    except (OSError, ValueError, TypeError, RecursionError):
        return core.row('informes', 'DEVIA · evidencia no interpretable', 'bloqueado',
                        'Formato no reconocido. No se muestran textos privados ni se presume éxito.', path, 'INVALID_CONFIG')


def inventory(workspace):
    workspace = Path(workspace)
    rows = []
    delivery = workspace / '.portal_private/entregas'
    roots = list(delivery.glob('*/devia-tests')) if delivery.is_dir() else []
    roots.append(workspace / '.portal_private/validacion-devia')
    for root in roots[:100]:
        paths = list(root.glob('*/RESULTADOS.json')) + list(root.glob('diagnostico-red*.json'))
        for path in paths[:200]:
            rows.append(summarize(path, workspace))
        if len(paths) > 200:
            rows.append(core.row('pendientes', 'DEVIA · límite de evidencias', 'parcial', 'Más de 200 informes en esta raíz.', root, 'LIMIT_REACHED'))
    rows.append(core.row('pendientes', 'DEVIA · conversaciones completas con ERP real', 'no_comprobado',
        'Estas fuentes historicas del19/10 no contienen una conversación completa acreditada con datos ERP reales y oráculo independiente. '
        'Consultar Resumen Windows para las evidencias posteriores del20/10. '
        'No se ejecutan consultas desde este inventario.'))
    rows.append(core.row('pendientes', 'DEVIA · protección multiusuario del ERP', 'no_comprobado',
        'Revisión 0.1.8: admisión ERP común y cancelación del trabajo subyacente pendientes. '
        'Consultar el informe y sus fallos conocidos; no demuestra el estado actual de Ubuntu.',
        workspace / 'DEVIA_VALIDACION/informes/RECURSOS-Y-CONCURRENCIA-20261019.txt'))
    rows.append(core.row('pendientes', 'DEVIA · pendientes historicos19/10 y siguientes pasos', 'no_comprobado',
        'Indice historico del19/10; consultar Resumen Windows para20/10 y21/10. '
        'El bloqueo local de ejecutores no sustituye la admisión multiusuario del servidor.',
        workspace / 'DEVIA_VALIDACION/informes/PENDIENTES-ACTUALES.txt'))
    rows.append(core.row('informes', 'DEVIA · ejemplos de conversaciones: guion, NO ejecutado', 'no_comprobado',
        'Ejemplo 1: saludo → capacidades → aclaración. Ejemplo 2: compras 2025/2026 → '
        'confirmar reglas de documentos → aprobar SELECT acotado → contrastar celdas con oráculo → '
        'seguimiento por proveedor → cierre. No son transcripciones reales. '
        'Los ejemplos completos y criterios están en el plan de aceptación.',
        workspace / 'DEVIA_VALIDACION/planes/ACEPTACION-REAL.txt'))
    return [dict(r, source='evidence') for r in rows]
