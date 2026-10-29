import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Centro de aplicaciones JDDC')
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--smoke', action='store_true', help='Abrir/cerrar ventana sin red ni inventario')
    parser.add_argument('--inventory-json', type=Path, help='Generar únicamente resumen depurado local')
    from centro import __version__
    parser.add_argument('--version', action='version', version=f'Centro JDDC {__version__} | codigo: {Path(__file__).resolve().parent}')
    parser.add_argument('--check-continuity', action='store_true', help='Validar indice y enlaces locales sin GUI ni red')
    args = parser.parse_args()
    if args.check_continuity:
        import json
        from centro import knowledge
        try:
            report = knowledge.check(args.workspace)
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            report = {'schema':'jddc-continuity-check/1','all_paths_available':False,'error':'Indice local no interpretable'}
        print(json.dumps(report,ensure_ascii=True,indent=2))
        raise SystemExit(0 if report['all_paths_available'] else 1)
    if args.inventory_json:
        import json
        from centro.core import scan, public_report
        with args.inventory_json.open('x', encoding='utf-8') as f:
            json.dump(public_report(scan(args.workspace)), f, ensure_ascii=False, indent=2)
        return
    from centro.ui import Center
    app = Center(args.workspace, autoload=not args.smoke)
    if args.smoke:
        app.after(500, app.close)
    app.mainloop()


if __name__ == '__main__':
    main()
