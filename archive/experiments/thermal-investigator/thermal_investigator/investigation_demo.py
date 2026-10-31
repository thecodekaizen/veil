"""Local persistent revision walkthrough; supplied families, no Meta calls."""
import argparse
from pathlib import Path
from .investigation import Investigation
from .physical import ThermalSpec, fit_physical
from .contracts import initial_schedule, experiment_library, schedule, DT
from .lab import parameters
from .validation import hidden_trace
from .run import write_json

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    folder=parser.parse_args().output; folder.mkdir(parents=True,exist_ok=False)
    # Evaluator-only configuration. Never passed to fitting or persistence tools.
    p=parameters(601,True)
    def measured(plan):
        return {'commands_fraction':plan.commands(),'temperature_c':hidden_trace(plan.commands(),p).tolist(),
                'sample_interval_s':DT,'ambient_c':22.,'source':'simulation',
                'noise_std_c':0.,'note':'Noiseless deterministic integration walkthrough, not accuracy evaluation'}
    initial=[measured(plan) for plan in [initial_schedule()]+experiment_library()[:2]]
    baseline=fit_physical(initial,ThermalSpec(False))
    store=Investigation(folder/'investigation.sqlite')
    try:
        store.create('walkthrough',5,initial)
        store.add_model('walkthrough','v1',baseline.executable_model(),['initial-0','initial-1','initial-2'])
        probe=schedule('prospective-sustained',[(60,60)])
        store.prepare('walkthrough','probe','v1',probe.to_dict())
        first=store.execute('walkthrough','probe',lambda action,plan:measured(probe))
        if first['assessment']['status']=='model_mismatch_observed':
            revised=fit_physical(initial+[measured(probe)],ThermalSpec(True))
            store.add_model('walkthrough','v2',revised.executable_model(),['initial-0','initial-1','initial-2','probe'],parent='v1')
            confirm=schedule('new-confirmation',[(45,10),(0,55),(35,35),(10,0),(60,20),(0,0)])
            store.prepare('walkthrough','confirmation','v2',confirm.to_dict(),'confirmation')
            store.close(); store=Investigation(folder/'investigation.sqlite')
            result=store.execute('walkthrough','confirmation',lambda action,plan:measured(confirm))
            # Completed replay must not dispatch again.
            assert store.execute('walkthrough','confirmation',lambda *args:(_ for _ in ()).throw(RuntimeError('duplicate')))==result
        else:
            result={'verdict':'no_revision_triggered','note':'No scripted mismatch is injected'}
        write_json(folder/'export.json',store.export('walkthrough'))
        write_json(folder/'result.json',{'diagnostic':first,'confirmation':result,'meta_calls':0,
             'limitations':['single development walkthrough','noiseless simulation','human-supplied revision policy','not a paired superiority evaluation']})
        print(first); print(result)
    finally: store.close()
if __name__=='__main__': main()
