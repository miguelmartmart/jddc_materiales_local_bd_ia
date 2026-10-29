"""Explicit source/document exports. No ERP, credentials, binaries or installation."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,re,zipfile
from . import project_catalog as projects,core,knowledge

MAX_FILES=20000
MAX_VISITS=50000
MAX_BYTES=128*1024*1024
MAX_FILE_BYTES=5*1024*1024
EXTENSIONS={'.py','.js','.ts','.tsx','.jsx','.html','.css','.scss','.md','.rst','.txt','.toml','.yml','.yaml','.json','.cmd','.sh','.ps1','.svg'}
PRIVATE_NAME=re.compile(r'(credential|password|passwd|secret|token|cookie|session|capture|captura|transcript|conversacion|conversation|factura|invoice|backup|\.env)',re.I)
SECRET_LITERAL=re.compile(rb'''(?im)["']?(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)["']?\s*[:=]\s*["']([^"'\r\n]{4,})["']''')

def export_sources(workspace,selected,destination,cancel,progress=lambda text:None):
    root=Path(workspace).absolute();destination=Path(destination).absolute()
    if destination.suffix.lower()!='.zip':raise ValueError('ZIP required')
    if destination.exists() or destination.is_symlink():raise FileExistsError('Destination already exists')
    if not selected:raise ValueError('No projects')
    # Only validated catalog records can choose source roots, never arbitrary UI paths.
    valid={p['id']:p for p in projects.load(root)['projects']}
    for p in selected:
        if valid.get(p['id'])!=p:raise ValueError('Unknown or changed project')
    resources={r['id']:r for r in knowledge.load(root)['resources']}
    files={};omitted=Counter();visited=0;total=0;per_project={};created=None
    def check_cancel():
        if cancel.is_set():raise ValueError('Cancelled')
    def add(relative,owner):
        nonlocal total,visited
        check_cancel();visited+=1
        if visited>MAX_VISITS:raise ValueError('Visit limit;export smaller groups')
        if relative in files:return
        path=root/relative
        if PRIVATE_NAME.search(path.name) or path.suffix.lower() not in EXTENSIONS:
            omitted['private_name_or_unsupported_type']+=1;return
        if path.suffix.lower()=='.json' and 'docs' not in Path(relative).parts and path.name not in {'package.json','tsconfig.json'}:
            omitted['configuration_json']+=1;return
        try:data=core.safe_file(path,root,MAX_FILE_BYTES)
        except (OSError,ValueError):omitted['unavailable_linked_or_large']+=1;return
        if b'\x00' in data or b'-----BEGIN ' in data and b'PRIVATE KEY-----' in data or SECRET_LITERAL.search(data):
            omitted['binary_or_potential_secret']+=1;return
        if len(files)>=MAX_FILES or total+len(data)>MAX_BYTES:raise ValueError('Export limit;export smaller groups')
        # Avoid retaining all source bytes: read again and compare at write time.
        files[relative]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'project':owner}
        total+=len(data)
    for p in selected:
        check_cancel();progress('Recopilando '+p['title']+'...');before=len(files)
        for rel in p['roots']:
            try:path=projects.local_path(root,rel)
            except (OSError,ValueError):omitted['root_unavailable']+=1;continue
            if path.is_file():add(rel,p['id']);continue
            pending=[(rel,0)]
            while pending:
                check_cancel();folder,depth=pending.pop()
                if depth>30:raise ValueError('Depth limit')
                try:
                    safe=projects.local_path(root,folder)
                    with os.scandir(safe) as entries:
                        for entry in entries:
                            check_cancel();visited+=1
                            if visited>MAX_VISITS:raise ValueError('Visit limit')
                            relative=(Path(folder)/entry.name).as_posix()
                            try:target=projects.local_path(root,relative)
                            except (OSError,ValueError):omitted['private_runtime_or_link']+=1;continue
                            if target.is_dir():
                                if PRIVATE_NAME.search(entry.name):omitted['private_folder']+=1
                                else:pending.append((relative,depth+1))
                            elif target.is_file():add(relative,p['id'])
                except OSError:omitted['folder_unavailable']+=1
        for id in p['resource_ids']:
            if id in resources:add(resources[id]['path'],p['id'])
            else:omitted['guide_unavailable']+=1
        per_project[p['id']]={'new_unique_files':len(files)-before,'roots':p['roots']}
    if not files:raise ValueError('No exportable files')
    manifest={'schema':'jddc-project-source-export/1','projects':per_project,'files':files,'omissions':dict(omitted),'scope':'Selected source and documents only;not a full backup,not a production build. Shared files stored once. Review before sharing.'}
    info='''EXPORTACION LOCAL DE FUENTES Y DOCUMENTOS
No instala,ejecuta o publica proyectos. No acredita produccion ni firma.
Incluye solo tipos admitidos de los proyectos elegidos;archivos compartidos una vez.
Omite carpetas privadas/configuracion/datos/logs/runtimes,binarios,ZIP,claves y
archivos con nombres sensibles o patrones de posibles secretos. El manifiesto
declara omisiones y archivos:esta copia NO sustituye una copia de seguridad.
Los filtros son preventivos,no una certificacion de ausencia de informacion
empresarial. Revisar antes de compartir. Credenciales:solicitar en su gestor.
Entregas revisadas completas:usar Entregas y accesos para copiarlas por separado.
Las campanas permanecen pausadas;ERP real siempre solo lectura.
'''.encode()
    try:
        check_cancel()
        with destination.open('xb') as stream:
            created=os.fstat(stream.fileno())
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for i,(rel,metadata) in enumerate(files.items()):
                    check_cancel();data=core.safe_file(root/rel,root,MAX_FILE_BYTES)
                    if hashlib.sha256(data).hexdigest()!=metadata['sha256']:raise ValueError('Source changed during export')
                    archive.writestr(rel,data)
                    if i%100==0:progress(f'Guardando {i+1}/{len(files)} archivos...')
                archive.writestr('LEER-EXPORTACION.txt',info)
                archive.writestr('MANIFIESTO-PROYECTOS.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())
            stream.flush();os.fsync(stream.fileno())
        check_cancel()
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip() is not None:raise ValueError('CRC mismatch')
            for rel,metadata in files.items():
                check_cancel()
                if hashlib.sha256(archive.read(rel)).hexdigest()!=metadata['sha256']:raise ValueError('Copy hash mismatch')
        return {'files':len(files),'source_bytes':total,'omissions':dict(omitted),'projects':len(selected)}
    except Exception:
        if created is not None:
            try:
                current=destination.stat()
                if (current.st_dev,current.st_ino)==(created.st_dev,created.st_ino):destination.unlink()
            except OSError:pass
        raise
