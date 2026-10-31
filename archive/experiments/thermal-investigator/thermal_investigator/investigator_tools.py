"""Shared bounded tools over persisted public evidence; no evaluator capability.

Fitting is capped and cached. Proposals do not dispatch physical experiments.
The numerical baseline and both Meta policies can use this same interface.
"""
import hashlib
import math
import json
import numpy as np
from .adequacy import probe_library
from .physical import ThermalSpec,fit_physical
from .nonlinear import fit_quadratic
from .investigation import encode

FAMILIES=('linear','sensor_lag','quadratic_loss')
OBS_FIELDS=('commands_fraction','temperature_c','ambient_c','sample_interval_s','noise_std_c','source')

class InvestigationTools:
    def __init__(self,store,session,max_fits=8):
        if type(max_fits) is not int or not 1<=max_fits<=12:raise ValueError('Invalid fitting cap')
        self.store=store;self.session=session
        store.export(session)
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS tool_limits(session TEXT PRIMARY KEY,max_fits INTEGER);
        CREATE TABLE IF NOT EXISTS candidate_fits(session TEXT,id TEXT,request TEXT,status TEXT,result TEXT,PRIMARY KEY(session,id));
        CREATE TABLE IF NOT EXISTS tool_decisions(session TEXT,id TEXT,request TEXT,result TEXT,PRIMARY KEY(session,id));
        ''')
        with store.transaction():
            existing=store.db.execute('SELECT max_fits FROM tool_limits WHERE session=?',(session,)).fetchone()
            if existing and existing[0]!=max_fits:raise ValueError('Persisted fitting cap cannot change')
            store.db.execute('INSERT OR IGNORE INTO tool_limits VALUES(?,?)',(session,max_fits))
    def evidence(self):
        return [{'observation_id':row['id'],**{k:v for k,v in json.loads(row['body']).items() if k in OBS_FIELDS}}
                for row in self.store.export(self.session)['observations']]
    def context(self):
        exported=self.store.export(self.session)
        fits=[{'candidate_id':r['id'],**json.loads(r['result'])} for r in self.store.db.execute(
            "SELECT * FROM candidate_fits WHERE session=? AND status='completed' ORDER BY id",(self.session,))]
        context={'goal':'Investigate model mismatch within a bounded thermal experiment budget.',
                 'observations':self.evidence(),
                 'registered_models':[{'model_id':r['id'],'parent_id':r['parent'],'evidence_ids':json.loads(r['evidence']),
                                       'model':json.loads(r['body'])} for r in exported['models']],
                 'candidate_fits':fits,
                 'revision_semantics':{'register_revision':'Stage a provisional fitted candidate for testing, not acceptance or causal identification.',
                    'confirmation':'To test a fitted candidate: register_revision first, then propose_experiment on its returned model_id with kind confirmation.',
                    'verdict':'Only measured confirmation supports or rejects a staged revision on that tested input.'},
                 'previous_decisions':[{'decision_id':r['id'],'decision':json.loads(r['request']),'result':json.loads(r['result'])}
                    for r in self.store.db.execute('SELECT * FROM tool_decisions WHERE session=? ORDER BY rowid',(self.session,))],
                 'observed_assessments':[json.loads(r['result']) for r in exported['actions'] if r['status']=='completed'],
                 'recorded_mismatches':[{'model_id':r['model'],'action_id':r['id'],'assessment':json.loads(r['result'])['assessment']}
                    for r in exported['actions'] if r['status']=='completed' and json.loads(r['result'])['assessment']['status']=='model_mismatch_observed'],
                 'actions_remaining':exported['session']['budget']-exported['session']['used'],
                 'unresolved_actions':[{'action_id':r['id'],'status':r['status']} for r in exported['actions'] if r['status']!='completed'],
                 'legal_schedules':[p.to_dict() for p in probe_library()],
                 'allowed_families':list(FAMILIES),'fit_calls_remaining':self.fit_remaining(),
                 'limitations':['supplied structures','simulation evidence only','no calibrated uncertainty',
                                'proposal does not execute experiment','fitting score is not independent confirmation']}
        context['context_id']=hashlib.sha256(encode(context).encode()).hexdigest()
        return context
    def fit_remaining(self):
        limit=self.store.db.execute('SELECT max_fits FROM tool_limits WHERE session=?',(self.session,)).fetchone()[0]
        used=self.store.db.execute('SELECT count(*) FROM candidate_fits WHERE session=?',(self.session,)).fetchone()[0]
        return limit-used
    def fit(self,family,evidence_ids):
        if family not in FAMILIES:raise ValueError('Unsupported candidate family')
        evidence={r['observation_id']:r for r in self.evidence()}
        if not evidence_ids or len(set(evidence_ids))!=len(evidence_ids) or any(i not in evidence for i in evidence_ids):
            raise ValueError('Unknown or duplicate evidence')
        observations=[evidence[i] for i in sorted(evidence_ids)]
        request=encode({'family':family,'observations':observations})
        candidate_id='fit-'+hashlib.sha256(request.encode()).hexdigest()[:24]
        with self.store.transaction():
            previous=self.store.db.execute('SELECT * FROM candidate_fits WHERE session=? AND id=?',(self.session,candidate_id)).fetchone()
            if previous:
                if previous['status']!='completed':raise ValueError('Previous fit is incomplete; no automatic retry')
                return {'candidate_id':candidate_id,**json.loads(previous['result'])}
            if self.fit_remaining()<=0:raise ValueError('Fitting budget exhausted')
            self.store.db.execute('INSERT INTO candidate_fits VALUES(?,?,?,?,?)',(self.session,candidate_id,request,'reserved',None))
            self.store.event(self.session,'candidate_fit_reserved',{'candidate_id':candidate_id,'family':family,'evidence_ids':sorted(evidence_ids)})
        try:
            model=fit_quadratic(observations,max_nfev=180) if family=='quadratic_loss' else fit_physical(observations,ThermalSpec(family=='sensor_lag'),max_nfev=180)
            result={'family':family,'evidence_ids':sorted(evidence_ids),'model':model.executable_model(),
                    'training_rmse_c':model.training_rmse_c,
                    'bic':sum((len(o['temperature_c'])-1)*2 for o in observations)*math.log(max(model.training_rmse_c**2,1e-15))+len(model.executable_model()['estimated_parameters'])*math.log(sum((len(o['temperature_c'])-1)*2 for o in observations)),
                    'validation_status':'not_independently_confirmed',
                    'optimizer_evaluations':model.optimizer_evaluations}
            with self.store.transaction():
                self.store.db.execute("UPDATE candidate_fits SET status='completed',result=? WHERE session=? AND id=?",(encode(result),self.session,candidate_id))
                self.store.event(self.session,'candidate_fit_completed',{'candidate_id':candidate_id})
            return {'candidate_id':candidate_id,**result}
        except Exception:
            with self.store.transaction():
                self.store.db.execute("UPDATE candidate_fits SET status='failed' WHERE session=? AND id=?",(self.session,candidate_id))
            raise
    def apply(self,decision_id,decision):
        request=encode(decision)
        previous=self.store.db.execute('SELECT * FROM tool_decisions WHERE session=? AND id=?',(self.session,decision_id)).fetchone()
        if previous:
            if previous['request']!=request:raise ValueError('Decision ID reused')
            return json.loads(previous['result'])
        context=self.context();validate_tool_decision(decision,context)
        if decision['operation']=='fit_candidate':
            result=self.fit(decision['family'],decision['evidence_ids'])
        elif decision['operation']=='register_revision':
            candidate=next(c for c in context['candidate_fits'] if c['candidate_id']==decision['candidate_id'])
            if not set(candidate['evidence_ids']).issubset(set(decision['evidence_ids'])):
                raise ValueError('Revision must preserve fitted evidence references')
            model_id='revision-'+hashlib.sha256(decision_id.encode()).hexdigest()[:24]
            self.store.add_model(self.session,model_id,candidate['model'],decision['evidence_ids'],parent=decision['model_id'])
            result={'status':'revision_registered','model_id':model_id,'candidate_id':decision['candidate_id'],'provisional':True,'next_step':'Propose independent confirmation on this model_id; registration is not acceptance'}
        elif decision['operation']=='propose_experiment':
            plan=next(p for p in probe_library() if p.id==decision['schedule_id'])
            result={'status':'proposal_only','model_id':decision['model_id'],'schedule':plan.to_dict(),
                    'kind':decision['kind'],'evidence_ids':decision['evidence_ids'],
                    'note':'Explicit preparation and dispatch through Investigation are required'}
        else:result={'status':'stop_requested','reason':decision['rationale'],'note':'Controller must honor this request; no execution is dispatched by these tools'}
        with self.store.transaction():
            self.store.db.execute('INSERT INTO tool_decisions VALUES(?,?,?,?)',(self.session,decision_id,request,encode(result)))
            self.store.event(self.session,'tool_decision',{'decision_id':decision_id,'decision':decision})
        return result


def tool_schema(context):
    return {'type':'object','properties':{
        'context_id':{'type':'string','enum':[context['context_id']]},
        'operation':{'type':'string','enum':['fit_candidate','register_revision','propose_experiment','stop']},
        'family':{'type':['string','null'],'enum':[*FAMILIES,None]},
        'candidate_id':{'type':['string','null']},'model_id':{'type':['string','null']},'schedule_id':{'type':['string','null']},
        'kind':{'type':['string','null'],'enum':['diagnostic','confirmation',None]},
        'evidence_ids':{'type':'array','items':{'type':'string'}},'rationale':{'type':'string'}},
        'required':['context_id','operation','family','candidate_id','model_id','schedule_id','kind','evidence_ids','rationale'],
        'additionalProperties':False}

def validate_tool_decision(value,context):
    fields=set(tool_schema(context)['required'])
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('Unknown decision fields')
    if any(value[k] is not None and not isinstance(value[k],str) for k in ('family','candidate_id','model_id','schedule_id','kind')) or not isinstance(value['operation'],str):
        raise ValueError('Invalid operation field types')
    if value['context_id']!=context['context_id']:raise ValueError('Stale evidence context')
    if not isinstance(value['rationale'],str) or not 1<=len(value['rationale'].strip())<=2000:raise ValueError('Bounded rationale required')
    ids=value['evidence_ids'];known={o['observation_id'] for o in context['observations']}
    if not isinstance(ids,list) or not ids or any(not isinstance(i,str) or i not in known for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('Observed evidence references required')
    op=value['operation']
    if op=='fit_candidate':
        if value['family'] not in FAMILIES or any(value[k] is not None for k in ('candidate_id','model_id','schedule_id','kind')):raise ValueError('Invalid fit request')
        if context['fit_calls_remaining']<=0:raise ValueError('Fitting budget exhausted')
    elif op=='register_revision':
        candidates={c['candidate_id']:c for c in context['candidate_fits']}
        if value['candidate_id'] not in candidates or value['model_id'] not in {m['model_id'] for m in context['registered_models']} or any(value[k] is not None for k in ('family','schedule_id','kind')):
            raise ValueError('Invalid revision registration')
        failures={r['action_id'] for r in context['observed_assessments'] if r['assessment']['status']=='model_mismatch_observed'}
        if not failures.intersection(ids):raise ValueError('Measured mismatch required')
    elif op=='propose_experiment':
        models={m['model_id']:m for m in context['registered_models']}
        if value['family'] is not None or value['candidate_id'] is not None or value['model_id'] not in models or value['schedule_id'] not in {p['id'] for p in context['legal_schedules']} or value['kind'] not in ('diagnostic','confirmation'):
            raise ValueError('Invalid experiment proposal')
        if context['actions_remaining']<=0 or context['unresolved_actions']:raise ValueError('No available execution slot')
        if value['kind']=='confirmation' and models[value['model_id']]['parent_id'] is None:raise ValueError('Confirmation requires a revision')
    elif op=='stop':
        if any(value[k] is not None for k in ('family','candidate_id','model_id','schedule_id','kind')):raise ValueError('Invalid stop request')
    else:raise ValueError('Unsupported operation')
    return value


def tool_wire_schema(context):
    """Nested operation branches encode field relationships in the provider schema."""
    branches=[]
    for operation in ('fit_candidate','register_revision','propose_experiment','stop'):
        if operation=='fit_candidate' and context['fit_calls_remaining']<=0:continue
        if operation=='register_revision' and (not context['candidate_fits'] or not context['recorded_mismatches']):continue
        if operation=='propose_experiment' and (context['actions_remaining']<=0 or context['unresolved_actions']):continue
        schema=json.loads(json.dumps(tool_schema(context)))
        properties=schema['properties'];properties['operation']={'type':'string','enum':[operation]}
        used={'fit_candidate':{'family'},'register_revision':{'candidate_id','model_id'},
              'propose_experiment':{'model_id','schedule_id','kind'},'stop':set()}[operation]
        for field in ('family','candidate_id','model_id','schedule_id','kind'):
            if field not in used:properties[field]={'type':'null'}
        if 'family' in used:properties['family']={'type':'string','enum':list(FAMILIES)}
        if 'candidate_id' in used:properties['candidate_id']={'type':'string','enum':[c['candidate_id'] for c in context['candidate_fits']]}
        if 'model_id' in used:properties['model_id']={'type':'string','enum':[m['model_id'] for m in context['registered_models']]}
        if 'schedule_id' in used:properties['schedule_id']={'type':'string','enum':[p['id'] for p in context['legal_schedules']]}
        if 'kind' in used:properties['kind']={'type':'string','enum':['diagnostic','confirmation']}
        properties['evidence_ids']['items']['enum']=[o['observation_id'] for o in context['observations']]
        if operation=='propose_experiment':
            # Confirmation is legal only for registered revisions. Encode the
            # relationship in separate nested branches, not just in prose.
            diagnostic=json.loads(json.dumps(schema))
            diagnostic['properties']['kind']={'type':'string','enum':['diagnostic']}
            branches.append(diagnostic)
            revised=[m['model_id'] for m in context['registered_models'] if m['parent_id'] is not None]
            if revised:
                confirmation=json.loads(json.dumps(schema))
                confirmation['properties']['kind']={'type':'string','enum':['confirmation']}
                confirmation['properties']['model_id']={'type':'string','enum':revised}
                branches.append(confirmation)
        elif operation=='register_revision':
            # Only a parent with measured mismatch may receive a staged revision.
            eligible={r['model_id'] for r in context['recorded_mismatches']}
            properties['model_id']={'type':'string','enum':[m['model_id'] for m in context['registered_models'] if m['model_id'] in eligible]}
            branches.append(schema)
        else:branches.append(schema)
    return {'type':'object','properties':{'decision':{'anyOf':branches}},'required':['decision'],'additionalProperties':False}


def decide_with_tools(provider,tools,policy):
    if policy not in ('meta_direct','meta_investigator'):raise ValueError('Unknown comparison policy')
    context=tools.context()
    instruction=('Choose one bounded investigation tool operation from observed evidence. All model families are supplied. '
                 'Cite observations. A training fit cannot establish mechanism or future accuracy. Proposals do not run experiments. '
                 'Use null for fields irrelevant to the operation. Never infer hidden system labels or future measurements. '
                 'A measured mismatch remains evidence against that model on that input even if other inputs pass. '
                 'One failed trial is sufficient to compare bounded predictive candidates; fitting is not a claim of causation. '
                 'Use available numerical fitting tools to compare explanations before consuming scarce physical experiments. '
                 'register_revision only stages a PROVISIONAL fitted candidate; it does not accept it. '
                 'To independently test a fitted candidate, first register_revision, then propose_experiment with its returned model_id and kind confirmation. '
                 'Testing the original model again cannot confirm the alternative candidate. '
                 'If stopping with recorded mismatch, explicitly report the unresolved limitation; never treat easier passing trials as resolving it.')
    if policy=='meta_investigator':
        instruction+=' Maintain evidence-linked hypotheses. When mismatch is measured, compare predictive alternatives and seek independent confirmation before accepting a revision. Keep all unresolved mismatch visible.'
    instruction+=' Return an object with a decision field matching exactly one operation branch.'
    def validate_wire(value):
        if not isinstance(value,dict) or set(value)!={'decision'}:raise ValueError('Expected operation envelope')
        return validate_tool_decision(value['decision'],context)
    # Provider cache stores the validated flat decision; accept it only on cache replay.
    def validate_response(value):
        return validate_wire(value) if isinstance(value,dict) and 'decision' in value else validate_tool_decision(value,context)
    return provider.decide_contract(context,instruction,tool_wire_schema(context),validate_response)
