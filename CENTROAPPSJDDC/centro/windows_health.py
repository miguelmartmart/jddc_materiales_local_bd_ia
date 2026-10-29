"""Orientacion de capacidad sobre observaciones Windows; no repara ni mide CPU."""
import math
from . import core


def _number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValueError('number')
    try:result=float(value)
    except OverflowError:raise ValueError('number') from None
    if not math.isfinite(result):raise ValueError('number')
    return result


def assess(data):
    """Umbrales operativos orientativos; una instantanea no diagnostica una fuga."""
    rows=[]
    def add(name,state,detail):
        rows.append(dict(core.row('configuracion','Capacidad Windows | '+name,state,detail),source='windows'))
    systems=data.get('system') if isinstance(data,dict) else None
    try:
        if not isinstance(systems,list) or len(systems)!=1:raise ValueError('system')
        total=_number(systems[0]['TotalVisibleMemorySize'])*1024
        free=_number(systems[0]['FreePhysicalMemory'])*1024
        if not math.isfinite(total) or not math.isfinite(free) or total<=0 or not 0<=free<=total:raise ValueError('range')
        low=free<1024**3 or free/total<0.10
        add('RAM','parcial' if low else 'detectado',
            f'{free/1024**3:.2f} GiB libres de {total/1024**3:.2f} GiB ({100*free/total:.1f}%). '
            +('Disponibilidad baja; revisar tendencia y tareas antes de decidir cambios. ' if low else 'Sin aviso de capacidad por estos umbrales. ')
            +'Umbral orientativo:menos de1GiB o10% libre. Instantanea, no prueba de rendimiento, fuga o salud general. No se cierran procesos.')
    except (KeyError,TypeError,ValueError,IndexError):
        add('RAM','no_comprobado','Falta una observacion numerica valida. No se supone capacidad suficiente.')
    disks=data.get('disks') if isinstance(data,dict) else None
    if not isinstance(disks,list) or not disks:
        add('Disco','no_comprobado','No hay observaciones validas de discos locales. No se supone espacio suficiente.')
    else:
        for disk in disks[:100]:
            try:
                size=_number(disk['Size']);free=_number(disk['FreeSpace'])
                label=disk.get('DeviceID','disco')
                if not isinstance(label,str) or len(label)>20 or size<=0 or not 0<=free<=size:raise ValueError('range')
                low=free<10*1024**3 or free/size<0.10
                add('Disco '+label,'parcial' if low else 'detectado',
                    f'{free/1024**3:.2f} GiB libres de {size/1024**3:.2f} GiB ({100*free/size:.1f}%). '
                    +('Espacio bajo; revisar crecimiento, retencion y copias verificadas. ' if low else 'Sin aviso de espacio por estos umbrales. ')
                    +'Umbral orientativo:menos de10GiB o10% libre. No se borran archivos ni se certifica salud fisica, copias o espacio futuro.')
            except (KeyError,TypeError,ValueError):
                add('Disco','no_comprobado','Observacion no interpretable. No se muestran valores invalidos ni se deduce espacio suficiente.')
    return rows
