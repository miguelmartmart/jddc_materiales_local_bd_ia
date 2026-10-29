"""Synthetic Tk rendering benchmark; no inventory, vault, network, AI or ERP."""
import argparse,json,statistics,sys,time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--count',type=int,default=3000)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 1<=args.count<=10000:parser.error('count must be1..10000')
    sys.path.insert(0,str(args.source.resolve()))
    from centro.ui import Center
    from centro import core,__version__
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='centro-render-fixture-') as tmp:
        app=Center(Path(tmp),autoload=False);app.withdraw()
        app.rows=[core.row('informes',f'DEVIA synthetic item{i:05}',detail=f'Alpha invoice customer period record{i%11}',path=f'C:/synthetic/{i}.txt') for i in range(args.count)]
        # Time one explicit render per query, rather than differences in trace scheduling.
        for mode,callback in app.search.trace_info():app.search.trace_remove(mode,callback)
        timings=[]
        for query in ('','invoice','item','nothing-matches','alpha',''):
            app.search.set(query)
            start=time.perf_counter();app.render();app.update_idletasks();timings.append(time.perf_counter()-start)
        def nodes(tree,parent=''):
            children=tree.get_children(parent)
            return len(children)+sum(nodes(tree,child) for child in children)
        count=sum(nodes(tree) for tree in app.trees.values())
        result={'schema':'jddc-render-benchmark/1','version':__version__,'synthetic_records':args.count,
                'seconds_per_render':[round(x,6) for x in timings],'median_seconds':round(statistics.median(timings),6),
                'final_tree_nodes':count,'scope':'One synthetic rendering process;not startup,server capacity or end-user latency',
                'real_erp_calls':0,'real_ai_calls':0,'network_calls':0}
        app.close()
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
