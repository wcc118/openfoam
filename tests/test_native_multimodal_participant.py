"""Independent oscillator mechanics, modal work and coupling protocol checks."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scripts.experiments.native_multimodal_participant import run
from scripts.modal_dynamics import ModalSystem, State
from tests.test_native_modal_participant import Participant


class NativeMultimodalTests(unittest.TestCase):
    def setUp(self):
        hp = np.zeros((3, 3, 2))
        hp[:, 2, :] = [[1., -2.], [2., -1.], [0., 3.]]
        self.assets = dict(points=np.array([[0.,0,0],[1.,0,0],[0.,1,0]]),
                           centers=np.array([[1/3,1/3,0]]), point_modes=hp,
                           face_modes=hp.mean(axis=0)[None], mode_indices=np.array([0,4]),
                           frequencies_hz=np.array([2.,3.]), native_modal_sha256=np.array('a'*64))
        # Add a second independent face to excite both modes through physical forces.
        self.assets['centers'] = np.array([[1/3,1/3,0],[.5,0,0]])
        self.assets['face_modes'] = np.array([hp.mean(axis=0), hp[:2].mean(axis=0)])
        self.settings = dict(mode_indices=[0,4], modal_frequencies_hz=[2.,3.],
            native_modal_sha256='a'*64, assets_sha256='b'*64, damping_ratio=[0.,0.],
            reference_q=[0.,0.], initial_q=[0.,0.], initial_v=[0.,0.], initial_force=[0.,0.],
            absolute_displacement_limit_m=1., mesh_increment_limit_m=1.,
            coupling='implicit', max_iterations=5, end_time_s=.02)

    def execute(self, trials, settings=None, assets=None, dt=.01):
        p = Participant(trials,dt)
        with tempfile.TemporaryDirectory() as folder:
            rows=run(p, assets or self.assets, settings or self.settings, folder)
            h=json.loads((Path(folder)/'multimodal-history.json').read_text())
            trace=[json.loads(line) for line in (Path(folder)/'trials.jsonl').read_text().splitlines()]
        return rows,p,h,trace

    def test_projection_virtual_work_and_mode_sign(self):
        force=np.array([[0.,0.,2.],[0.,0.,4.]])
        rows,p,h,_=self.execute([(force,False)]*2)
        np.testing.assert_allclose(rows[0]['Q_generalized'],[8.,-6.])
        dq=np.array(rows[0]['q'])
        point_motion=p.writes[1]
        face_motion=np.array([point_motion.mean(axis=0),point_motion[:2].mean(axis=0)])
        self.assertAlmostEqual(float(np.sum(force*face_motion)),float(np.dot([8.,-6.],dq)),14)
        flipped=copy.deepcopy(self.assets)
        flipped['point_modes'][:,:,1]*=-1;flipped['face_modes'][:,:,1]*=-1
        r,pf,_,_=self.execute([(force,False)]*2,assets=flipped)
        self.assertAlmostEqual(rows[-1]['q'][1],-r[-1]['q'][1],14)
        np.testing.assert_allclose(p.writes,pf.writes,atol=1e-14)
        self.assertTrue(h['completed']);self.assertTrue(p.finalized)
        self.assertEqual(h['units']['q'],'sqrt(kg)*m')

    def test_nonzero_loaded_hold_and_independent_release(self):
        force=np.array([[0.,0.,2.],[0.,0.,4.]])
        omega=2*np.pi*np.array([2.,3.]);qeq=np.array([8.,-6.])/omega**2
        s={**self.settings,'reference_q':qeq.tolist(),'initial_q':qeq.tolist(),'initial_force':[8.,-6.]}
        rows,p,_,_=self.execute([(force,False)]*2,settings=s)
        np.testing.assert_allclose(p.writes,0.,atol=1e-14)
        np.testing.assert_allclose(rows[-1]['q'],qeq,atol=1e-14)
        errors=[]
        for dt in (.002,.001):
            initial=np.array([.01,-.02]);duration=.2
            s={**self.settings,'initial_q':initial.tolist(),'end_time_s':duration}
            rows,_,_,_=self.execute([(np.zeros((2,3)),False)]*round(duration/dt),settings=s,dt=dt)
            exact=initial*np.cos(omega*duration)
            errors.append(np.linalg.norm(rows[-1]['q']-exact))
            self.assertLess(max(abs(r['structural_energy_defect_J']) for r in rows),1e-12)
        self.assertLess(errors[1],errors[0]/3.9)

    def test_rollback_restores_force_acceleration_time(self):
        f=lambda z:np.array([[0.,0.,z],[0.,0.,2*z]])
        base,_,_,_=self.execute([(f(2),False),(f(3),False)])
        rows,_,h,trace=self.execute([(f(2),False),(f(80),True),(f(3),False)])
        for a,b in zip(base,rows):
            for key in ('q','v','time_s','Q_generalized','energy_J','structural_load_work_J'):
                self.assertEqual(a[key],b[key])
        self.assertEqual(h['rollbacks'],1)
        self.assertEqual(trace[1]['time_s'],trace[2]['time_s'])

    def test_failures_finalize_and_preserve_incomplete_history(self):
        f=np.ones((2,3))
        cases=[([(f,True),(f,False)],{'max_iterations':2},.01,'cap'),
               ([(f,True),(f,True)],{'max_iterations':2},.01,'cap'),
               ([(f,False)],{},.01,'end time'),
               ([(f,False)],{},0.,'dt'),
               ([(np.ones((1,3)),False)],{},.01,'native face loads'),
               ([(f*1e6,False)],{},.01,'displacement')]
        for trials,updates,dt,message in cases:
            with self.subTest(message=message),tempfile.TemporaryDirectory() as folder:
                p=Participant(trials,dt)
                with self.assertRaisesRegex((ValueError,RuntimeError),message):
                    run(p,self.assets,{**self.settings,**updates},folder)
                self.assertTrue(p.finalized)
                h=json.loads((Path(folder)/'multimodal-history.json').read_text())
                self.assertFalse(h['completed']);self.assertIsNotNone(h['failure'])

    def test_physical_cancellation_guard_and_initial_guard(self):
        a=copy.deepcopy(self.assets);a['point_modes'][:,:,1]=-a['point_modes'][:,:,0]
        # Large opposing coefficients give zero physical motion at initialization.
        s={**self.settings,'initial_q':[10.,10.], 'reference_q':[10.,10.],
           'initial_force':(np.array([10.,10.])*(2*np.pi*np.array([2.,3.]))**2).tolist()}
        with tempfile.TemporaryDirectory() as folder:
            p=Participant([], .01)
            with self.assertRaisesRegex(RuntimeError,'end time'):run(p,a,s,folder)
            np.testing.assert_allclose(p.writes[0],0.)
        for updates in ({'initial_q':[10.,0.]},{'reference_q':[10.,0.]},):
            with tempfile.TemporaryDirectory() as folder:
                p=Participant([], .01)
                with self.assertRaisesRegex(RuntimeError,'displacement'):
                    run(p,self.assets,{**self.settings,**updates},folder)
                self.assertEqual(len(p.writes),0)

    def test_metadata_and_shapes_rejected(self):
        changes=[('mode_indices',np.array([0,0])),('mode_indices',np.array([0.,4.])),
                 ('mode_indices',np.array([-1,4])),('frequencies_hz',np.array([2.,4.])),
                 ('native_modal_sha256',np.array('c'*64)),('point_modes',np.zeros((3,3,1))),
                 ('face_modes',np.zeros((2,3,3))),('points',np.zeros((0,3))),
                 ('centers',np.full((2,3),np.nan))]
        for key,value in changes:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):run(Participant([],.01),{**self.assets,key:value},self.settings,folder)
        changes=[('mode_indices',[0.5,4]),('max_iterations',2.5),('max_iterations',True),
                 ('damping_ratio',[-1.,0.]),('coupling','unknown'),('initial_q',[np.nan,0]),
                 ('mesh_increment_limit_m',0.),('end_time_s',float('inf'))]
        for key,value in changes:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):run(Participant([],.01),self.assets,{**self.settings,key:value},folder)

    def test_energy_violation_is_rejected(self):
        original=ModalSystem.step
        def corrupt(system,state,force,dt):
            end=original(system,state,force,dt)
            return State(end.q,np.array(end.v)+.1,end.a,end.force,end.time)
        with patch.object(ModalSystem,'step',corrupt), tempfile.TemporaryDirectory() as folder:
            p=Participant([(np.ones((2,3)),False)],.01)
            with self.assertRaisesRegex(RuntimeError,'energy'):run(p,self.assets,self.settings,folder)
            self.assertTrue(p.finalized)

    def test_trace_exclusivity_and_cli_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'trials.jsonl').write_text('prior evidence\n')
            with self.assertRaises(FileExistsError):run(Participant([],.01),self.assets,self.settings,path)
            self.assertEqual((path/'trials.jsonl').read_text(),'prior evidence\n')
            np.savez(path/'assets.npz',**self.assets);(path/'settings.json').write_text(json.dumps(self.settings))
            result=subprocess.run([sys.executable,'-m','scripts.experiments.native_multimodal_participant',
                '--assets',str(path/'assets.npz'),'--settings',str(path/'settings.json'),
                '--config','unused.xml','--output',str(path/'out')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('assets hash mismatch',result.stderr)
            self.assertNotIn('precice',result.stderr)


if __name__=='__main__':unittest.main()
