"""Inventario acotado. Nunca ejecuta SQL ERP, scripts descubiertos ni lee claves."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sqlite3
import ssl
import stat
import subprocess
import tempfile
import time
import zipfile
import urllib.request
import urllib.error
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

LIMIT = 512 * 1024
CONFIG_NAMES = {'.env', 'config.env', 'deployment.json', 'ai_connections.json',
                'access-policy.json', 'broker.json', 'broker-identities.json'}
REPORT_SUFFIXES = {'.log', '.jsonl', '.xml', '.txt', '.json', '.zip'}
EXCLUDED = {'.git', '.venv', 'node_modules', '__pycache__', 'site-packages',
            '.pytest_cache'}
STATES = {'detectado', 'no_comprobado', 'correcto', 'fallo', 'bloqueado', 'parcial'}
PUBLIC_CODES = {'OK', 'READ_FAILED', 'LIMIT_REACHED', 'LINK_SKIPPED', 'INVALID_CONFIG',
                'TIMEOUT', 'TLS_INVALID', 'DNS_FAILED', 'CONNECT_FAILED', 'INVALID_URL',
                'WINDOWS_UNAVAILABLE', 'WINDOWS_FAILED', 'CERT_PARSE_FAILED', 'KEY_SKIPPED',
                'ACCOUNT_READ_FAILED', 'EXPORT_FAILED', 'AUDIT_FAILED', 'UNKNOWN',
                'HTTP_FAILED', 'UNEXPECTED_HEALTH'}

ADVICE = {
    'OK': 'Revisa el alcance: detectado o TCP correcto no equivale a funcionamiento completo.',
    'READ_FAILED': 'Comprueba que la ruta exista y sea legible. No cambies permisos de forma indiscriminada.',
    'LIMIT_REACHED': 'Añade una subcarpeta concreta para examinarla por separado. No se presume cobertura completa.',
    'LINK_SKIPPED': 'Selecciona la carpeta de destino real si está autorizada; no se siguen enlaces automáticamente.',
    'INVALID_CONFIG': 'Comprueba formato, tamaño y codificación del archivo original sin compartir valores privados.',
    'TIMEOUT': 'Correlaciona hora y destino con Ubuntu. Revisa ruta, NAT y filtros; no presupongas un token inválido.',
    'TLS_INVALID': 'Revisa CA, SAN, vigencia y hora del equipo. Nunca desactives la validación TLS.',
    'DNS_FAILED': 'Revisa DNS y VPN del equipo. Conserva el nombre previsto en el certificado.',
    'CONNECT_FAILED': 'Comprueba destino, puerto y CA seleccionada. No modifiques certificados o firewall por suposición.',
    'ACCOUNT_READ_FAILED': 'Comprueba la ruta de cuentas del portal y su formato; no pruebes escrituras.',
    'HTTP_FAILED': 'El servicio local no respondió como se esperaba. Revisa su registro de arranque.',
    'UNEXPECTED_HEALTH': 'Otro servicio o contrato no reconocido puede ocupar el puerto. No atribuyas identidad solo por el puerto.',
}


def family(record):
    """Agrupación orientativa por ubicación/nombre, no atribución de proceso activo."""
    text = (str(record.get('path', '')) + ' ' + str(record.get('name', ''))).lower().replace('\\', '/')
    if record.get('source') == 'windows':
        return 'Windows'
    if record.get('source') == 'history':
        return 'Centro JDDC'
    if 'devia' in text:
        return 'DEVIA'
    if any(x in text for x in ('api_clone', 'api-clone', 'api clone', 'api_explorer', 'api explorer')):
        return 'API SQL Obras'
    if any(x in text for x in ('portal', 'notice_', 'coordinated')):
        return 'Portal de Avisos'
    return 'Otros / por clasificar'


def read_history(path, limit=200):
    """Historial propio con esquema cerrado; no carga logs de otras aplicaciones."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        data = safe_file(path, path.parent, 2 * 1024 * 1024).decode('utf-8')
        result = []
        invalid = False
        events = {'scan', 'windows', 'probe', 'health', 'export', 'open', 'startup'}
        for line in data.splitlines():
            try:
                item = json.loads(line)
                if not isinstance(item, dict) or set(item) != {'time', 'event', 'state', 'code'}:
                    raise ValueError('schema')
                if item['event'] not in events or item['state'] not in STATES or item['code'] not in PUBLIC_CODES:
                    raise ValueError('enum')
                stamp = datetime.fromisoformat(item['time'])
                if stamp.tzinfo is None:
                    raise ValueError('timezone')
                record = row('informes', 'Historial: ' + item['event'], item['state'],
                             'Evento del centro; no contiene la respuesta original del servicio.', code=item['code'])
                record.update(checked_at=stamp.isoformat(), source='history')
                result.append(record)
            except (ValueError, TypeError, KeyError):
                invalid = True
        truncated = len(result) > limit
        result = result[-limit:]
        if invalid or truncated:
            result.append(dict(row('pendientes', 'Historial parcial', 'parcial',
                                   'Se omitieron registros inválidos o anteriores al límite.', code='LIMIT_REACHED'), source='history'))
        return result
    except (OSError, ValueError, UnicodeError, RecursionError):
        return [dict(row('pendientes', 'Historial no disponible', 'bloqueado',
                         'No se pudo validar el historial local.', code='READ_FAILED'), source='history')]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_health():
    """Solo GET del contrato público de salud en loopback; no planes ni inferencias."""
    url = 'http://127.0.0.1:8781/api/health'
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(url, timeout=3) as response:
            if response.status != 200:
                raise ValueError('status')
            data = response.read(4097)
        if len(data) > 4096:
            raise ValueError('size')
        payload = json.loads(data)
        if not isinstance(payload, dict) or payload.get('status') != 'configured' or payload.get('mode') not in ('synthetic-demo', 'local-client'):
            raise ValueError('contract')
        mode = payload['mode']
        detail = ('El servicio declara modo DEMO: respuesta fija y datos ficticios; no usa ERP/IA real.'
                  if mode == 'synthetic-demo' else 'El servicio declara modo cliente. No acredita ERP, IA, credenciales o permisos.')
        return dict(row('aplicaciones', 'DEVIA local — salud HTTP', 'correcto', detail), source='health')
    except (OSError, urllib.error.URLError):
        return dict(row('aplicaciones', 'DEVIA local — salud HTTP', 'fallo', 'No se completó el GET local. Sin reintento.', code='HTTP_FAILED'), source='health')
    except (ValueError, UnicodeError, RecursionError):
        return dict(row('aplicaciones', 'DEVIA local — salud HTTP', 'bloqueado', 'Respuesta no reconocida; cuerpo descartado.', code='UNEXPECTED_HEALTH'), source='health')


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def linked(path: Path):
    s = path.lstat()
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, 'st_file_attributes', 0) & 0x400)


def checked_path(path: Path, root: Path, limit=LIMIT):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError('outside root')
    current = root
    if linked(current):
        raise ValueError('linked root')
    for part in path.relative_to(root).parts:
        current /= part
        if linked(current):
            raise ValueError('linked path')
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('file limit')
    return path


def safe_file(path: Path, root: Path, limit=LIMIT):
    path = checked_path(path, root, limit)
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('file grew')
    return data


def walk(root, max_files=6000, max_depth=7):
    """Devuelve archivos ordinarios; no sigue symlinks/junctions ni enlaces de carpetas."""
    root = Path(root).absolute()
    found, issues = [], []
    if not root.is_dir():
        return found, ['READ_FAILED']
    try:
        if linked(root):
            return found, ['LINK_SKIPPED']
        pending = [(root, 0)]
        visited = 0
        while pending:
            folder, depth = pending.pop()
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        visited += 1
                        if visited > max_files:
                            return found, issues + ['LIMIT_REACHED']
                        p = Path(entry.path)
                        if linked(p):
                            issues.append('LINK_SKIPPED')
                        elif entry.is_dir(follow_symlinks=False):
                            if entry.name in EXCLUDED or entry.name.startswith('.venv'):
                                continue
                            if depth < max_depth:
                                pending.append((p, depth + 1))
                            else:
                                issues.append('LIMIT_REACHED')
                        elif entry.is_file(follow_symlinks=False):
                            found.append(p)
            except OSError:
                issues.append('READ_FAILED')
    except OSError:
        issues.append('READ_FAILED')
    return found, sorted(set(issues))


def row(kind, name, state='detectado', detail='', path='', code='OK'):
    return dict(kind=kind, name=name, state=state, detail=detail,
                path=str(path), code=code, checked_at=now())


def config_summary(path, root):
    """Solo indicadores de presencia. No devuelve valores ni claves desconocidas."""
    try:
        data = safe_file(path, root).decode('utf-8-sig')
        if path.suffix == '.json':
            obj = json.loads(data)
            if not isinstance(obj, dict):
                raise ValueError('not object')
            keys = [str(k).upper() for k in obj]
        else:
            keys = [line.split('=', 1)[0].strip().upper() for line in data.splitlines()
                    if '=' in line and not line.lstrip().startswith('#')]
        categories = []
        for name, words in [('ERP', ('DB_', 'ERP', 'FIREBIRD')),
                            ('IA', ('AI_', 'IA_', 'MODEL')),
                            ('TLS', ('TLS', 'CERT', 'CA_FILE', 'KEY_FILE')),
                            ('cuentas', ('AUTH', 'USER')),
                            ('red', ('HOST', 'PORT', 'ORIGIN', 'NETWORK', 'URL'))]:
            if any(any(w in k for w in words) for k in keys):
                categories.append(name)
        return row('configuracion', path.name, 'no_comprobado',
                   'Campos presentes: ' + (', '.join(categories) or 'otros') +
                   '. Valores ocultos; no acredita conectividad.', path)
    except (OSError, ValueError, UnicodeError, RecursionError):
        return row('configuracion', path.name, 'bloqueado', 'No se pudo validar el archivo.', path, 'INVALID_CONFIG')


def cert_summary(path, root):
    try:
        data = safe_file(path, root)
        if b'PRIVATE KEY' in data:
            return row('certificados', path.name, 'bloqueado', 'Material privado: no inspeccionado.', path, 'KEY_SKIPPED')
        if b'-----BEGIN CERTIFICATE-----' not in data:
            data = ssl.DER_cert_to_PEM_cert(data).encode('ascii')
        with tempfile.TemporaryDirectory(prefix='jddc-public-cert-') as tmp:
            public = Path(tmp) / 'public.pem'
            public.write_bytes(data)
            info = ssl._ssl._test_decode_cert(str(public))
        expires = ssl.cert_time_to_seconds(info['notAfter'])
        starts = ssl.cert_time_to_seconds(info['notBefore'])
        remaining = int((expires - time.time()) // 86400)
        state = 'fallo' if expires <= time.time() or starts > time.time() else 'no_comprobado'
        subject = ', '.join(v for fields in info.get('subject', ()) for k, v in fields if k == 'commonName')
        der = ssl.PEM_cert_to_DER_cert(data.decode('ascii'))
        detail = f'{subject}; vence {info["notAfter"]} UTC; {remaining} días. SHA256 {hashlib.sha256(der).hexdigest()}. '
        detail += 'No comprueba cadena, revocación, SAN del servicio ni clave asociada.'
        if 0 <= remaining <= 30:
            detail += ' Renovación prioritaria.'
        return row('certificados', path.name, state, detail, path)
    except (OSError, ValueError, UnicodeError, ssl.SSLError, KeyError):
        return row('certificados', path.name, 'bloqueado', 'Certificado no interpretable.', path, 'CERT_PARSE_FAILED')


def portal_accounts(db, root):
    """Solo SQLite del portal, modo ro; ninguna conexión a Firebird."""
    rows = []
    try:
        checked_path(db, root, 32 * 1024 * 1024)
        with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)) as conn:
            conn.execute('PRAGMA query_only=ON')
            fields = {r[1] for r in conn.execute('PRAGMA table_info(users)')}
            if 'name' not in fields:
                raise ValueError('unknown schema')
            for (name,) in conn.execute('SELECT name FROM users LIMIT 201'):
                rows.append(row('cuentas', str(name)[:150], 'no_comprobado',
                                'Cuenta del portal local. No acredita acceso ni permisos efectivos.', db))
        if len(rows) > 200:
            rows = rows[:200] + [row('cuentas', 'Límite', 'parcial', 'Más de 200 cuentas.', code='LIMIT_REACHED')]
    except (OSError, ValueError, sqlite3.Error):
        rows.append(row('cuentas', 'Cuentas portal', 'bloqueado', 'No se pudo leer el registro local en modo lectura.', db, 'ACCOUNT_READ_FAILED'))
    return rows


def resource_summary(path, root):
    """Metadatos operativos; no ejecuta, extrae ni muestra contenido."""
    name, suffix = path.name.lower(), path.suffix.lower()
    category, kind = None, 'informes'
    if name in {'pyproject.toml', 'package.json', 'package-lock.json', 'poetry.lock', 'uv.lock', 'pipfile', 'dockerfile', 'compose.yaml', 'docker-compose.yml'} or (name.startswith('requirements') and suffix == '.txt'):
        category, kind = 'Dependencias / despliegue', 'configuracion'
    elif suffix in {'.cmd', '.bat', '.ps1', '.service'}:
        category, kind = 'Arranque / operación', 'aplicaciones'
    elif name.startswith(('readme', 'leeme', 'indice', 'agents')) or suffix in {'.md', '.rst'}:
        category = 'Documentación'
    elif name.startswith(('test_', 'test-')) or name.endswith(('.test.js', '.test.cjs', '.spec.js')):
        category = 'Pruebas disponibles (no ejecutadas por el inventario)'
    elif suffix in {'.mbtiles', '.pmtiles', '.geojson', '.gpkg'}:
        category, kind = 'Cartografía / catálogo geográfico', 'configuracion'
    elif suffix in {'.zip', '.7z', '.rar', '.bak'}:
        category = 'Paquete / posible copia (restauración no comprobada)'
    if category is None:
        return None
    try:
        checked_path(path, root, 2**63 - 1)
        info = path.stat()
        modified = datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec='seconds')
        return row(kind, category + ': ' + path.name, 'no_comprobado',
                   f'{info.st_size} bytes. Modificado: {modified}. '
                   'Solo metadatos: contenido, integridad y uso activo no comprobados. No se ejecutó ni extrajo.', path)
    except (OSError, ValueError, OverflowError):
        return row(kind, category + ': ' + path.name, 'bloqueado', 'No se pudieron leer los metadatos.', path, 'READ_FAILED')


def scan(root):
    root = Path(root).absolute()
    files, issues = walk(root)
    rows = []
    known = [('Portal de Avisos', 'backend/notice_portal'),
             ('API Explorer — SQL Obras', 'backend/modules/api_explorer'),
             ('API Clone — Firebird', 'backend/modules/api_clone')]
    for name, rel in known:
        if (root / rel).is_dir():
            rows.append(row('aplicaciones', name, 'no_comprobado', 'Código localizado; ejecución no acreditada.', root / rel))
    modules = root / 'backend/modules'
    if modules.is_dir() and not linked(modules):
        for p in modules.iterdir():
            if p.is_dir() and not linked(p) and p.name not in {'api_clone', 'api_explorer', '__pycache__'}:
                rows.append(row('aplicaciones', 'Módulo: ' + p.name, 'no_comprobado', 'Componente del proyecto original.', p))
    for p in files:
        resource = resource_summary(p, root)
        if resource:
            rows.append(resource)
        if p.name == 'pyproject.toml':
            try:
                text = safe_file(p, root).decode('utf-8')
                if 'devia-pilot' in text:
                    import re
                    version = re.search(r'^version\s*=\s*"([0-9.]+)"', text, re.M)
                    rows.append(row('aplicaciones', 'DEVIA ' + (version[1] if version else '?'),
                                    'no_comprobado', 'Entrega localizada. Demo y modo conectado se comprueban por separado.', p.parent))
            except (OSError, ValueError, UnicodeError):
                issues.append('READ_FAILED')
        if p.name in CONFIG_NAMES:
            rows.append(config_summary(p, root))
        if p.suffix.lower() in {'.crt', '.cer'}:
            rows.append(cert_summary(p, root))
        if resource is None and p.suffix.lower() in REPORT_SUFFIXES and any(w in p.name.lower() for w in
                ('informe', 'diagnos', 'result', 'validation', 'synthetic', 'stdout', 'stderr', 'resumen', 'indice', 'audit')):
            rows.append(row('informes', p.name, 'no_comprobado',
                            f'{p.stat().st_size} bytes. Contenido original no examinado; puede ser privado.', p))
        if p.name == 'deployment.json':
            try:
                cfg = json.loads(safe_file(p, root))
                value = cfg.get('PORTAL_AUTH_DB') if isinstance(cfg, dict) else None
                if isinstance(value, str):
                    db = Path(value)
                    if not db.is_absolute():
                        db = p.parent / db
                    if db.absolute().is_relative_to(root):
                        rows.extend(portal_accounts(db, root))
            except (OSError, ValueError, RecursionError):
                pass
    for code in sorted(set(issues)):
        rows.append(row('pendientes', 'Cobertura del inventario', 'parcial',
                        'Escaneo acotado: pueden faltar rutas, enlaces o archivos sin permiso.', root, code))
    rows.append(row('pendientes', 'Ubuntu / ERP / IA', 'no_comprobado',
                    'Cuentas remotas, servicio broker, permisos ERP, inferencia, revocación y actualizaciones requieren conectores autorizados.'))
    return rows


def public_report(rows):
    """Esquema cerrado: ningún texto libre, nombre, ruta, IP, cuenta o certificado."""
    groups = {}
    allowed = {'aplicaciones', 'configuracion', 'certificados', 'cuentas', 'informes', 'pendientes', 'red', 'procesos', 'firewall', 'servicios', 'actualizaciones'}
    for r in rows:
        kind = r.get('kind') if r.get('kind') in allowed else 'pendientes'
        state = r.get('state') if r.get('state') in STATES else 'no_comprobado'
        code = r.get('code') if r.get('code') in PUBLIC_CODES else 'UNKNOWN'
        key = (kind, state, code)
        groups[key] = groups.get(key, 0) + 1
    return {'schema': 'jddc-center-support/1', 'generated_at': now(),
            'scope': 'inventario local acotado; no certifica producción',
            'groups': [dict(kind=k[0], state=k[1], code=k[2], count=n) for k, n in sorted(groups.items())],
            'omissions': ['nombres', 'rutas', 'IP/DNS', 'cuentas', 'certificados', 'secretos', 'logs originales'],
            'production_accepted': False}


def export_zip(path, rows):
    path = Path(path)
    report = json.dumps(public_report(rows), ensure_ascii=False, indent=2).encode('utf-8')
    # Crear en exclusiva: nunca sustituir una entrega anterior.
    with path.open('xb') as stream:
        try:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('RESUMEN.json', report)
                archive.writestr('LEEME.txt', 'Resumen depurado de estados y codigos. No contiene archivos originales ni secretos. No sustituye las pruebas reales. Los detalles permanecen en la consola local.')
                archive.writestr('SHA256SUMS.txt', hashlib.sha256(report).hexdigest() + '  RESUMEN.json\n')
        except BaseException:
            stream.close()
            path.unlink(missing_ok=True)
            raise
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('CRC failed')


def probe(url, ca=None, timeout=3):
    """Una conexión TCP/TLS, sin HTTP, sin tokens ni inferencias."""
    try:
        u = urlsplit(url)
        if u.scheme not in {'https', 'http'} or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in {'', '/'}:
            raise ValueError('url')
        if u.scheme == 'http' and u.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('plaintext remote')
        port = u.port or (443 if u.scheme == 'https' else 80)
        if not 1 <= port <= 65535:
            raise ValueError('port')
    except ValueError:
        return row('red', 'Destino', 'bloqueado', 'URL no admitida.', code='INVALID_URL')
    try:
        context = ssl.create_default_context(cafile=str(ca) if ca else None) if u.scheme == 'https' else None
        with socket.create_connection((u.hostname, port), timeout=timeout) as conn:
            if context:
                with context.wrap_socket(conn, server_hostname=u.hostname):
                    pass
        return row('red', url, 'correcto', 'TCP y TLS estricto correctos; no prueba login/API.' if context else 'TCP local correcto; no identifica la aplicación ni prueba HTTP.')
    except ssl.SSLCertVerificationError:
        return row('red', url, 'fallo', 'Validación TLS fallida. No se omitió la CA ni el nombre.', code='TLS_INVALID')
    except (TimeoutError, socket.timeout):
        return row('red', url, 'fallo', 'Tiempo de conexión agotado.', code='TIMEOUT')
    except socket.gaierror:
        return row('red', url, 'fallo', 'No se pudo resolver el nombre.', code='DNS_FAILED')
    except (OSError, ValueError):
        return row('red', url, 'fallo', 'No se completó la conexión o la carga de CA.', code='CONNECT_FAILED')


WINDOWS_COMMAND = r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$r=@{}
foreach($item in @('processes','listeners','firewall','rules','accounts','network','certificates','services','system','hardware','disks','clock','dns','routes')){
 try {
  switch($item){
   system {$r[$item]=@(Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory,@{n='LastBoot';e={$_.LastBootUpTime.ToString('o')}})}
   hardware {$r[$item]=@(Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,NumberOfLogicalProcessors,TotalPhysicalMemory,HypervisorPresent)}
   disks {$r[$item]=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object -First 100 DeviceID,FileSystem,Size,FreeSpace)}
   clock {$r[$item]=@(@{Time=(Get-Date).ToString('o');TimeZone=(Get-TimeZone).Id;TimeService=(Get-Service W32Time).Status.ToString();Scope='Local clock only; synchronization not verified'})}
   dns {$r[$item]=@(Get-DnsClientServerAddress | Select-Object -First 100 InterfaceAlias,AddressFamily,ServerAddresses)}
   routes {$r[$item]=@(Get-NetRoute -PolicyStore ActiveStore | Select-Object -First 300 DestinationPrefix,NextHop,InterfaceIndex,RouteMetric,Protocol)}
   processes {$r[$item]=@(Get-Process | Where-Object {$_.ProcessName -match 'python|uvicorn|node|devia'} | Select-Object -First 100 Id,ProcessName,Path)}
   listeners {$r[$item]=@(Get-NetTCPConnection -State Listen | Select-Object -First 200 LocalAddress,LocalPort,OwningProcess)}
   firewall {$r[$item]=@(Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction)}
   rules {$r[$item]=@(Get-NetFirewallRule -PolicyStore ActiveStore | Where-Object {$_.Enabled -eq 'True'} | Select-Object -First 501 DisplayName,Direction,Action,Profile,PolicyStoreSourceType)}
   accounts {$r[$item]=@(Get-LocalUser | Select-Object -First 100 Name,Enabled)}
   network {$r[$item]=@(Get-NetIPConfiguration | Select-Object InterfaceAlias,@{n='IPv4';e={$_.IPv4Address.IPAddress -join ','}},@{n='Gateway';e={$_.IPv4DefaultGateway.NextHop -join ','}})}
   certificates {$r[$item]=@(Get-ChildItem Cert:\CurrentUser\My,Cert:\LocalMachine\My | Select-Object -First 201 Subject,Thumbprint,@{n='NotAfter';e={$_.NotAfter.ToString('o')}},HasPrivateKey)}
   services {$r[$item]=@(Get-Service | Where-Object {$_.Name -match 'jddc|devia|portal|firebird' -or $_.DisplayName -match 'jddc|devia|portal|firebird'} | Select-Object -First 100 Name,DisplayName,Status,StartType)}
  }
 }catch{$r[$item]=@(@{error='WINDOWS_FAILED'})}
}
$r | ConvertTo-Json -Depth 4 -Compress'''


WINDOWS_SECTIONS = {
    'processes': ('procesos', 100), 'listeners': ('red', 200),
    'firewall': ('firewall', 100), 'rules': ('firewall', 501),
    'accounts': ('cuentas', 100), 'network': ('red', 100),
    'certificates': ('certificados', 201), 'services': ('servicios', 100),
    'system': ('configuracion', 100), 'hardware': ('configuracion', 100),
    'disks': ('configuracion', 100), 'clock': ('configuracion', 100),
    'dns': ('red', 100), 'routes': ('red', 300),
}


def windows_rows(data):
    if not isinstance(data, dict):
        raise ValueError('inventory schema')
    rows = []
    for section, (kind, limit) in WINDOWS_SECTIONS.items():
        items = data.get(section)
        if not isinstance(items, list):
            rows.append(row(kind, section, 'bloqueado', 'Sección ausente o no interpretable.', code='WINDOWS_FAILED'))
            continue
        for item in items[:limit]:
            if not isinstance(item, dict) or 'error' in item:
                rows.append(row(kind, section, 'bloqueado', 'Windows no permitió completar esta lectura.', code='WINDOWS_FAILED'))
            else:
                title = str(item.get('DisplayName') or item.get('Name') or item.get('Subject') or item.get('ProcessName') or item.get('InterfaceAlias') or item.get('DeviceID') or section)
                rows.append(row(kind, title, 'detectado', json.dumps(item, ensure_ascii=False)))
        if len(items) >= limit:
            rows.append(row('pendientes', section, 'parcial', 'Inventario limitado; puede haber más elementos.', code='LIMIT_REACHED'))
    return [dict(r, source='windows') for r in rows]


def windows_inventory():
    if os.name != 'nt':
        return [row('pendientes', 'Windows', 'bloqueado', 'No disponible en esta plataforma.', code='WINDOWS_UNAVAILABLE')]
    try:
        process = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-Command', WINDOWS_COMMAND],
                                 capture_output=True, timeout=25, creationflags=0x08000000)
        if process.returncode or len(process.stdout) > LIMIT:
            raise ValueError('process result')
        data = json.loads(process.stdout.decode('utf-8-sig', errors='replace'))
        from .windows_health import assess
        return windows_rows(data) + assess(data)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return [row('pendientes', 'Inventario Windows', 'bloqueado', 'No se pudo completar; sin cambios de permisos.', code='WINDOWS_FAILED')]


def audit(path, event, state, code='OK'):
    allowed = {'scan', 'windows', 'probe', 'health', 'export', 'open', 'startup'}
    if event not in allowed or state not in STATES or code not in PUBLIC_CODES:
        raise ValueError('audit schema')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': now(), 'event': event, 'state': state, 'code': code}) + '\n')
