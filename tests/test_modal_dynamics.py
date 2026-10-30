"""Independent physical identities and lifecycle checks for the modal primitive."""
import unittest
import math
from dataclasses import FrozenInstanceError
import numpy as np
from scripts.modal_dynamics import ModalSystem, State


class ModalTests(unittest.TestCase):
    def test_validation(self):
        for args in (([0],[0],[1]), ([1],[-1],[1]), ([1],[0],[-1]),
                     ([math.nan],[0],[1]), ([1],[math.inf],[1]),
                     ([[1]],[0],[1]), ([],[],[]), ([1,2],[0],[1,2])):
            with self.subTest(args=args), self.assertRaises(ValueError):
                ModalSystem(*args)
        s = ModalSystem([1],[0],[1]); x = s.initial_state([1],[0],[0])
        for dt in (0,-1,math.nan,math.inf,[.1]):
            with self.subTest(dt=dt), self.assertRaises(ValueError): s.step(x,[0],dt)
        for f in ([math.nan],[],[1,2],[[1]]):
            with self.assertRaises(ValueError): s.step(x,f,.1)
        with self.assertRaises(ValueError): s.step(State([1],[0],[0],[0]),[0],.1)

    def test_equilibrium_and_positive_force(self):
        s = ModalSystem([2],[3],[4]); x = s.initial_state([.5],[.25],[7])
        self.assertEqual(x.a, (2.125,))
        rigid = ModalSystem([2],[0],[0]); x = rigid.initial_state([0],[0],[6])
        y = rigid.step(x,[6],.2)
        np.testing.assert_allclose(y.q,[.06],atol=1e-15)
        np.testing.assert_allclose(y.v,[.6],atol=1e-15)

    def test_rigid_free_motion(self):
        s=ModalSystem([2],[0],[0]); x=s.initial_state([.3],[-.7],[0])
        for _ in range(100): x=s.step(x,[0],.01)
        np.testing.assert_allclose(x.q,[-.4],atol=1e-14)
        self.assertEqual(x.v,(-.7,))

    def test_analytic_second_order(self):
        # Non-period endpoint avoids cancellation that can masquerade as order four.
        for damping in (0.,.8):
            m,k,q0,v0,T=2.,18.,.7,-.4,.73
            s=ModalSystem([m],[damping],[k]); decay=damping/(2*m)
            wd=math.sqrt(k/m-decay**2)
            A=q0; B=(v0+decay*q0)/wd
            q=math.exp(-decay*T)*(A*math.cos(wd*T)+B*math.sin(wd*T))
            v=math.exp(-decay*T)*(-decay*(A*math.cos(wd*T)+B*math.sin(wd*T))
                                      +wd*(-A*math.sin(wd*T)+B*math.cos(wd*T)))
            errors=[]
            for n in (80,160,320):
                x=s.initial_state([q0],[v0],[0])
                for _ in range(n): x=s.step(x,[0],T/n)
                errors.append(np.linalg.norm([x.q[0]-q,x.v[0]-v]))
            for ratio in (errors[0]/errors[1],errors[1]/errors[2]):
                self.assertGreater(ratio,3.9); self.assertLess(ratio,4.1)
            self.assertLess(errors[-1],5e-5)

    def test_discrete_energy_with_varying_load(self):
        for c in ([0.,0.],[.4,.7]):
            m=np.array([2.,3.]); k=np.array([5.,0.]); c=np.array(c)
            s=ModalSystem(m,c,k); x=s.initial_state([.3,-.1],[.7,.2],[.2,-.3])
            energy=lambda z: .5*np.sum(m*np.array(z.v)**2+k*np.array(z.q)**2)
            for i in range(60):
                dt=.01+.001*(i%3); f=np.array([math.sin(i*.2),.3*math.cos(i*.1)])
                y=s.step(x,f,dt); dq=np.array(y.q)-x.q
                vm=.5*(np.array(y.v)+x.v)
                work=.5*np.dot(np.array(x.force)+y.force,dq)
                loss=dt*np.dot(vm,c*vm)
                self.assertAlmostEqual(energy(y)-energy(x),work-loss,delta=2e-14)
                x=y

    def test_owned_checkpoint_and_replay(self):
        mass=[1.]; q=[.2]; f=[.4]; s=ModalSystem(mass,[.3],[2.])
        x=s.initial_state(q,[.1],f); cp=s.checkpoint(x)
        mass[0]=99; q[0]=99; f[0]=99
        self.assertEqual(s.mass,(1.,)); self.assertEqual(x.q,(.2,)); self.assertEqual(cp.force,(.4,))
        with self.assertRaises(FrozenInstanceError): cp.time=2
        rejected=s.step(x,[20],.1)
        restored=s.restore(cp)
        self.assertNotEqual(rejected,restored)
        clean=s.step(x,[.7],.03); replay=s.step(restored,[.7],.03)
        self.assertEqual(clean,replay)
        self.assertEqual(cp,x)

if __name__=='__main__': unittest.main()
