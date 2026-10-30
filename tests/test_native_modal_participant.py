"""Offline protocol tests with independent mechanics and controlled retries."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scripts.experiments.native_modal_participant import run


class Participant:
    def __init__(self, trials, dt):
        self.trials=trials; self.dt=dt; self.index=0; self.writes=[]; self.finalized=False
    def set_mesh_vertices(self, name, vertices): return np.arange(len(vertices))
    def requires_initial_data(self): return True
    def initialize(self): pass
    def finalize(self): self.finalized=True
    def is_coupling_ongoing(self): return self.index<len(self.trials)
    def requires_writing_checkpoint(self): return self.index==0 or not self.trials[self.index-1][1]
    def get_max_time_step_size(self): return self.dt
    def read_data(self, mesh, data, ids, relative_time):
        assert relative_time==self.dt
        return self.trials[self.index][0]
    def write_data(self, mesh, data, ids, values): self.writes.append(np.array(values,copy=True))
    def advance(self, dt): self.index+=1
    def requires_reading_checkpoint(self): return self.trials[self.index-1][1]


class NativeModalTests(unittest.TestCase):
    def setUp(self):
        self.assets=dict(points=np.array([[0.,0,0],[1,0,0],[0,1,0]]),
                         centers=np.array([[1/3,1/3,0]]),
                         point_mode=np.array([[.1,0,.5],[.2,0,1.],[.3,0,1.5]]),
                         face_mode=np.array([[.2,0,1.]]))
        self.settings=dict(mass_kg=2., stiffness_N_m=18., damping_N_s_m=0.,
                           displacement_limit_m=1., max_iterations=5,
                           coupling='implicit',end_time_s=.02)
    def execute(self,trials,dt=.01,settings=None,assets=None):
        p=Participant(trials,dt)
        with tempfile.TemporaryDirectory() as folder:
            rows=run(p,assets or self.assets,settings or self.settings,folder)
            history=json.loads((Path(folder)/'modal-history.json').read_text())
            trace=[json.loads(x) for x in (Path(folder)/'trials.jsonl').read_text().splitlines()]
        return rows,p,history,trace
    def test_force_changes_motion_and_mode_sign_preserves_physical_motion(self):
        forces=[(np.array([[0.,0,2.]]),False)]*2
        a,p,h,_=self.execute(forces)
        b,pb,_,_=self.execute([(np.zeros((1,3)),False)]*2)
        self.assertGreater(a[-1]['q_m'],0);self.assertEqual(b[-1]['q_m'],0)
        flipped={**self.assets,'point_mode':-self.assets['point_mode'],'face_mode':-self.assets['face_mode']}
        c,pc,_,_=self.execute(forces,assets=flipped)
        self.assertEqual(a[-1]['q_m'],-c[-1]['q_m'])
        self.assertEqual(a[-1]['Q_N'],-c[-1]['Q_N'])
        np.testing.assert_allclose(p.writes,pc.writes,rtol=0,atol=1e-15)
        self.assertTrue(h['completed']);self.assertTrue(p.finalized)
    def test_independent_undamped_oscillator_with_initial_load_ramp(self):
        # Exact ODE solution for Q rising linearly from zero over first dt,
        # then held constant. Undamped motion does NOT settle to Q/K.
        errors=[]
        for dt in (.002,.001):
            duration=.4;w=3.;equilibrium=2./18.
            q1=equilibrium*(1-np.sin(w*dt)/(w*dt))
            v1=equilibrium/dt*(1-np.cos(w*dt))
            exact=equilibrium+(q1-equilibrium)*np.cos(w*(duration-dt))+v1/w*np.sin(w*(duration-dt))
            rows,_,_,_=self.execute([(np.array([[0.,0,2.]]),False)]*round(duration/dt),dt,
                                     {**self.settings,'end_time_s':duration})
            errors.append(abs(rows[-1]['q_m']-exact))
        self.assertLess(errors[1],1e-7)
        self.assertLess(errors[1],errors[0]/3.8)
    def test_rejected_trial_restores_accepted_state(self):
        f=lambda z:np.array([[0.,0,z]])
        baseline,_,_,_=self.execute([(f(2),False),(f(3),False)])
        rows,_,h,trace=self.execute([(f(2),False),(f(90),True),(f(3),False)])
        for a,b in zip(rows,baseline):
            for key in ('time_s','q_m','v_m_s','Q_N','energy_J','structural_load_work_J'):
                self.assertEqual(a[key],b[key])
        self.assertEqual(h['rollbacks'],1);self.assertEqual(len(trace),3)
        self.assertTrue(trace[1]['rejected']);self.assertEqual(trace[1]['time_s'],trace[2]['time_s'])
        self.assertNotEqual(trace[1]['q_m'],trace[2]['q_m'])
    def test_iteration_cap_never_counts_as_success(self):
        for last_rejected in (True,False):
            p=Participant([(np.ones((1,3)),True),(np.ones((1,3)),last_rejected)],.01)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(RuntimeError,'cap'):
                    run(p,self.assets,{**self.settings,'max_iterations':2},folder)
                h=json.loads((Path(folder)/'modal-history.json').read_text())
                self.assertFalse(h['completed']);self.assertEqual(h['rows'],[])
                self.assertTrue(p.finalized)
    def test_bad_loads_fail_without_success(self):
        for force in (np.full((1,3),np.nan),np.ones((2,3))):
            with tempfile.TemporaryDirectory() as folder:
                p=Participant([(force,False)],.01)
                with self.assertRaisesRegex(ValueError,'native face loads'):
                    run(p,self.assets,self.settings,folder)
                h=json.loads((Path(folder)/'modal-history.json').read_text())
                self.assertFalse(h['completed']);self.assertEqual(h['rows'],[])
                self.assertTrue(p.finalized)
    def test_missing_end_and_runaway_are_failures(self):
        for override,message in (({},'end time'),({'displacement_limit_m':1e-10},'displacement limit')):
            p=Participant([(np.ones((1,3)),False)],.01)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(RuntimeError,message):
                    run(p,self.assets,{**self.settings,**override},folder)
                self.assertFalse(json.loads((Path(folder)/'modal-history.json').read_text())['completed'])
    def test_damping_energy_accounting(self):
        rows,_,_,_=self.execute([(np.ones((1,3)),False)]*2,settings={**self.settings,'damping_N_s_m':.4})
        self.assertGreater(sum(r['damping_loss_J'] for r in rows),0)
        self.assertLess(max(abs(r['structural_energy_defect_J']) for r in rows),1e-15)


if __name__=='__main__':unittest.main()
