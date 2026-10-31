"""Transactional local investigation state; external execution is never retried blindly.

SQLite prevents duplicate reservations. A crash after dispatch leaves an uncertain
execution requiring reconciliation; it cannot guarantee exactly-once hardware I/O.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import numpy as np
from .contracts import Schedule, DT, RESET_SECONDS
from .model_registry import execute_candidate
from .adequacy import assess


def encode(value):
    return json.dumps(value,allow_nan=False,sort_keys=True)


def validate_observation(value, commands=None):
    u=np.asarray(value['commands_fraction'],dtype=float)
    y=np.asarray(value['temperature_c'],dtype=float)
    if u.shape!=(60,2) or y.shape!=(61,2) or not np.isfinite(u).all() or not np.isfinite(y).all():
        raise ValueError('Expected finite 120-second experiment observations')
    if np.any(u<0) or np.any(u>.65) or value['sample_interval_s']!=DT or value['ambient_c']!=22.:
        raise ValueError('Unsupported experiment bounds, interval or ambient')
    if commands is not None and not np.array_equal(u,np.asarray(commands)):
        raise ValueError('Observed commands differ from frozen schedule')
    return json.loads(encode(value))


class Investigation:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,budget INTEGER NOT NULL,used INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS observations(session TEXT,id TEXT,body TEXT NOT NULL,PRIMARY KEY(session,id));
        CREATE TABLE IF NOT EXISTS models(session TEXT,id TEXT,parent TEXT,evidence TEXT,body TEXT NOT NULL,PRIMARY KEY(session,id));
        CREATE TABLE IF NOT EXISTS actions(session TEXT,id TEXT,model TEXT,kind TEXT,request TEXT NOT NULL,
          prediction TEXT NOT NULL,status TEXT NOT NULL,result TEXT,PRIMARY KEY(session,id));
        CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,session TEXT,kind TEXT,body TEXT);
        ''')
    def close(self): self.db.close()
    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise
    def event(self,session,kind,body):
        self.db.execute('INSERT INTO events(session,kind,body) VALUES(?,?,?)',(session,kind,encode(body)))
    def create(self,session,budget,initial_observations):
        if type(budget) is not int or budget<len(initial_observations) or budget<1:
            raise ValueError('Invalid total action budget')
        observations=[validate_observation(x) for x in initial_observations]
        with self.transaction():
            self.db.execute('INSERT INTO sessions VALUES(?,?,?)',(session,budget,len(observations)))
            for index,obs in enumerate(observations):
                self.db.execute('INSERT INTO observations VALUES(?,?,?)',(session,f'initial-{index}',encode(obs)))
            self.event(session,'created',{'initial_actions_charged':len(observations),'budget':budget,
                                         'source':'imported initial trials; no live execution claimed'})
    def add_model(self,session,model_id,model,evidence_ids,parent=None):
        # Validate executable specification before storing it; no generated code.
        execute_candidate(model,[[0.,0.]])
        if not evidence_ids or len(set(evidence_ids))!=len(evidence_ids):
            raise ValueError('Unique observed evidence IDs required')
        with self.transaction():
            for evidence in evidence_ids:
                if not self.db.execute('SELECT 1 FROM observations WHERE session=? AND id=?',(session,evidence)).fetchone():
                    raise ValueError('Unknown observation evidence')
            count=self.db.execute('SELECT count(*) FROM models WHERE session=?',(session,)).fetchone()[0]
            if parent is None and count:
                raise ValueError('Revision requires a parent model')
            if parent is not None:
                if not self.db.execute('SELECT 1 FROM models WHERE session=? AND id=?',(session,parent)).fetchone():
                    raise ValueError('Unknown parent model')
                failures=self.db.execute("SELECT id,result FROM actions WHERE session=? AND model=? AND status='completed'",(session,parent)).fetchall()
                linked=[r['id'] for r in failures if r['id'] in evidence_ids and json.loads(r['result'])['assessment']['status']=='model_mismatch_observed']
                if not linked: raise ValueError('Revision must cite a measured parent mismatch')
            self.db.execute('INSERT INTO models VALUES(?,?,?,?,?)',(session,model_id,parent,encode(evidence_ids),encode(model)))
            self.event(session,'model_registered',{'id':model_id,'parent':parent,'evidence_ids':evidence_ids})
    def prepare(self,session,action_id,model_id,plan,kind='diagnostic'):
        if kind not in ('diagnostic','confirmation'): raise ValueError('Unknown action kind')
        schedule=Schedule.from_dict(plan)
        request=encode({'model':model_id,'schedule':schedule.to_dict(),'kind':kind})
        with self.transaction():
            existing=self.db.execute('SELECT * FROM actions WHERE session=? AND id=?',(session,action_id)).fetchone()
            if existing:
                if existing['request']!=request: raise ValueError('Action ID reused with different request')
                return json.loads(existing['prediction'])
            model=self.db.execute('SELECT * FROM models WHERE session=? AND id=?',(session,model_id)).fetchone()
            if model is None: raise ValueError('Unknown model')
            if kind=='confirmation' and model['parent'] is None:
                raise ValueError('Confirmation requires a revision')
            session_row=self.db.execute('SELECT * FROM sessions WHERE id=?',(session,)).fetchone()
            if session_row is None or session_row['used']>=session_row['budget']:
                raise ValueError('Experiment budget exhausted')
            prediction=execute_candidate(json.loads(model['body']),schedule.commands()).tolist()
            self.db.execute('UPDATE sessions SET used=used+1 WHERE id=?',(session,))
            self.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',
                (session,action_id,model_id,kind,request,encode(prediction),'prepared',None))
            self.event(session,'prediction_frozen',{'action':action_id,'model':model_id,'kind':kind,
                'charged_experiment_s':120,'charged_reset_s':RESET_SECONDS})
            return prediction
    def execute(self,session,action_id,runner):
        with self.transaction():
            row=self.db.execute('SELECT * FROM actions WHERE session=? AND id=?',(session,action_id)).fetchone()
            if row is None: raise ValueError('Unknown action')
            if row['status']=='completed': return json.loads(row['result'])
            if row['status']!='prepared':
                raise RuntimeError('Execution outcome uncertain; reconcile measurement before continuing, do not retry')
            self.db.execute("UPDATE actions SET status='dispatched' WHERE session=? AND id=?",(session,action_id))
            self.event(session,'dispatched',{'action':action_id})
        # Stable action ID is supplied for an external executor's own idempotency.
        observation=runner(action_id,json.loads(row['request'])['schedule'])
        return self.reconcile(session,action_id,observation)
    def reconcile(self,session,action_id,observation):
        with self.transaction():
            row=self.db.execute('SELECT * FROM actions WHERE session=? AND id=?',(session,action_id)).fetchone()
            if row is None or row['status']!='dispatched': raise ValueError('Only dispatched actions can be reconciled')
            commands=Schedule.from_dict(json.loads(row['request'])['schedule']).commands()
            observation=validate_observation(observation,commands)
            assessment=assess(json.loads(row['prediction']),observation['temperature_c'])
            verdict=('revision_rejected' if assessment['status']=='model_mismatch_observed' else 'revision_supported_on_confirmation') if row['kind']=='confirmation' else assessment['status']
            result={'action_id':action_id,'assessment':assessment,'verdict':verdict,
                    'scope':'Evidence for this experiment only; no global reliability claim'}
            self.db.execute('INSERT INTO observations VALUES(?,?,?)',(session,action_id,encode(observation)))
            self.db.execute("UPDATE actions SET status='completed',result=? WHERE session=? AND id=?",(encode(result),session,action_id))
            self.event(session,'measurement_recorded',result)
            return result
    def export(self,session):
        row=self.db.execute('SELECT * FROM sessions WHERE id=?',(session,)).fetchone()
        if row is None: raise ValueError('Unknown session')
        return {'session':dict(row),'models':[dict(r) for r in self.db.execute('SELECT * FROM models WHERE session=?',(session,))],
                'observations':[dict(r) for r in self.db.execute('SELECT * FROM observations WHERE session=?',(session,))],
                'actions':[dict(r) for r in self.db.execute('SELECT * FROM actions WHERE session=?',(session,))],
                'events':[dict(r) for r in self.db.execute('SELECT * FROM events WHERE session=? ORDER BY sequence',(session,))]}
