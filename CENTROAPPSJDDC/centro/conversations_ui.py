"""Visor local de capturas de conversación; no exporta su contenido."""
import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from . import core
from .evidence_checks import integrity, local_time, basic_checks, comparison_text


def read_turns(path, workspace):
    raw = core.safe_file(path, workspace, 2 * 1024 * 1024).decode('utf-8')
    turns = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (not isinstance(row, dict) or row.get('schema') != 'devia-private-turn/1'
                or row.get('origin') not in {'web_real_no_erp_execution', 'real_broker_public_prompts_no_query_execution'}
                or row.get('erp_execution_requested') is not False
                or not isinstance(row.get('question'), str)
                or not isinstance(row.get('answer'), str)):
            raise ValueError('invalid transcript')
        turns.append(row)
        if len(turns) > 200:
            raise ValueError('turn limit')
    return turns


class ConversationsWindow(tk.Toplevel):
    def __init__(self, parent, workspace):
        super().__init__(parent)
        self.workspace = workspace
        self.title('Conversaciones · contenido privado local')
        self.geometry('930x680')
        ttk.Label(self, text='Conversaciones capturadas', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=12, pady=8)
        ttk.Label(self, text='Contenido privado: solo se muestra en este equipo. No se incluye en el ZIP del centro.\nCaptura declarativa del cliente: no certifica por sí sola el modelo ni la exactitud de datos.', wraplength=850).pack(anchor='w', padx=12)
        bar = ttk.Frame(self)
        bar.pack(fill='x', padx=12, pady=8)
        ttk.Button(bar, text='Actualizar conversaciones', command=self.refresh).pack(side='left')
        ttk.Button(bar, text='Iniciar prueba web con captura local', command=self.start).pack(side='left', padx=8)
        self.choice = ttk.Combobox(self, state='readonly')
        self.choice.pack(fill='x', padx=12)
        self.choice.bind('<<ComboboxSelected>>', self.show)
        frame = ttk.Frame(self)
        frame.pack(fill='both', expand=True, padx=12, pady=8)
        self.text = tk.Text(frame, wrap='word', font=('Segoe UI', 11), state='disabled')
        scroll = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.refresh()

    def display(self, text):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)
        self.text.configure(state='disabled')

    def refresh(self):
        root = self.workspace / '.portal_private/validacion-devia'
        self.paths = sorted(list(root.glob('*/CONVERSACION-PRIVADA.jsonl')) + list(root.glob('*/DATOS-ERP-PRIVADOS.json')) + list(root.glob('*/INTEGRADA-PRIVADA.json')), reverse=True)[:200]
        self.choice.configure(values=[('Integrada · ' if p.name == 'INTEGRADA-PRIVADA.json' else 'ERP · ' if p.suffix == '.json' else 'Conversación · ') + p.parent.name for p in self.paths])
        if self.paths:
            self.choice.current(0)
            self.show()
        else:
            self.choice.set('Sin conversaciones capturadas')
            self.display('No hay transcripciones locales en las carpetas conocidas.\n\n'
                'Las pruebas antiguas guardaron estados, no preguntas y respuestas. No pueden reconstruirse.\n\n'
                'Iniciar prueba web abre una consola para introducir tu cuenta de forma local. '
                'Realiza seis turnos públicos secuenciales, guarda respuestas aquí y cancela las propuestas ERP. '
                'No consulta filas ERP. No repite peticiones fallidas automáticamente.\n\n'
                'Para acreditar conversaciones con datos ERP faltan una captura de lectura autorizada y '
                'un contraste independiente de sus resultados. No se presentan como realizadas.')

    def show(self, event=None):
        index = self.choice.current()
        if index < 0:
            return
        try:
            provenance = integrity(self.paths[index], self.workspace)
            if self.paths[index].name == 'INTEGRADA-PRIVADA.json':
                data = json.loads(core.safe_file(self.paths[index], self.workspace, 2 * 1024 * 1024))
                report = json.loads(core.safe_file(self.paths[index].parent / 'RESULTADOS.json', self.workspace))
                if not isinstance(data, dict) or not isinstance(report, dict):
                    raise ValueError('Integrated schema')
                self.display('PRUEBA INTEGRADA IA / ERP\nEstado: ' + str(report.get('state')) +
                    '\nMotivo: ' + {'missing_plan': 'La respuesta no contiene un plan ejecutable.',
                        'missing_approval': 'Falta la aprobación vinculada al plan.',
                        'plan_outside_scope': 'El plan excede o cambia el alcance permitido.'}.get(report.get('reason'), 'Consultar el resultado y el plan.') +
                    '\nContraste independiente: ' + str(report.get('independent_comparison', 'pending')) +
                    '\nInicio: ' + local_time(report.get('started_at')) + '\n' + provenance +
                    comparison_text(self.paths[index], self.workspace) +
                    '\nTÚ\n' + str(data.get('question', '')) + '\n\nRESPUESTA\n' + str(data.get('answer', '')) +
                    '\n\nPLAN PROPUESTO\n' + json.dumps(data.get('plan'), ensure_ascii=False, indent=2) +
                    '\n\nERP ejecutado según respuesta: ' + str(data.get('erp_executed', False)) +
                    '\nFILAS DEVUELTAS\n' + json.dumps(data.get('data', []), ensure_ascii=False, indent=2) +
                    '\n\nSIGUIENTE PASO: si falta el plan, Ubuntu debe correlacionar este horario y revisar el planificador. No repetir automáticamente ni ampliar permisos.' +
                    '\n\nLímite: una fila, sin agregados. No acredita toda la aplicación ni exactitud contable.\n')
                return
            if self.paths[index].name == 'DATOS-ERP-PRIVADOS.json':
                data = json.loads(core.safe_file(self.paths[index], self.workspace, 2 * 1024 * 1024))
                if not isinstance(data, list) or len(data) > 5:
                    raise ValueError('ERP schema')
                chunks = ['LECTURA ERP REAL DIRECTA · no pasó por la IA\nMuestra acotada, no informe contable completo.\n', provenance]
                for item in data:
                    if not isinstance(item, dict) or not isinstance(item.get('rows'), list):
                        raise ValueError('ERP row')
                    chunks.append('\n' + str(item.get('case', '')) + '\nConsulta: ' + str(item.get('sql', '')) + '\nColumnas: ' + str(item.get('fields', [])) + '\nFilas:\n' + json.dumps(item['rows'], ensure_ascii=False, indent=2) + '\n')
                self.display(''.join(chunks))
                return
            turns = read_turns(self.paths[index], self.workspace)
            chunks = ['IA / portal: turnos capturados. ERP: no se solicitó ejecutar consultas.\n'
                      'Exactitud semántica: pendiente de revisión.\n', provenance, basic_checks(turns)]
            for r in turns:
                chunks.append(f"\n{local_time(r.get('at', ''))} · {r.get('case', '')} · turno {r.get('turn', '?')}\n"
                    f"TÚ\n{r['question']}\n\nRESPUESTA\n{r['answer'] or '[Sin texto de respuesta]'}\n"
                    f"\nPropuesta ERP recibida: {'sí; no ejecutada' if r.get('proposal_received') else 'no'}.\n")
                if r.get('answer_truncated'):
                    chunks.append('[Respuesta truncada por límite de captura]\n')
            self.display(''.join(chunks) if turns else 'Archivo sin turnos completos.')
        except (OSError, ValueError, TypeError, UnicodeError):
            self.display('No se pudo validar la captura. No se muestra como conversación acreditada.')

    def start(self):
        path = self.workspace / 'DEVIA_VALIDACION/PROBAR_WEB_REAL.cmd'
        try:
            core.safe_file(path, self.workspace)
            os.startfile(str(path))
            self.display('Consola de prueba solicitada. Introduce tu cuenta allí; no pegues la contraseña en informes.\n'
                         'Al terminar pulsa Actualizar conversaciones. El lanzamiento no acredita ningún resultado.\n'
                         'No vuelvas a iniciar mientras siga en curso: evita duplicar peticiones.')
        except (OSError, ValueError, AttributeError):
            self.display('No se pudo abrir el ejecutor local. Revisa DEVIA_VALIDACION/PROBAR_WEB_REAL.cmd.')
