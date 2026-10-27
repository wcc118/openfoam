"""Independent values, work, scaling, and input-contract checks."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('modal', Path(__file__).resolve().parents[1] / 'scripts/modal_surface.py')
modal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modal)


class ModalSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.basis = [[[1., 2., 0.], [-1., 0., 1.]],
                      [[2., -1., 1.], [0., 3., -2.]]]
        self.forces = [[4., -2., 3.], [1., 2., -1.]]

    def test_hand_values(self):
        self.assertEqual(modal.displacements(self.basis, [2., -.5]),
                         [[1., 4.5, -.5], [-2., -1.5, 3.]])
        self.assertEqual(modal.generalized_forces(self.basis, self.forces), [-2., 21.])
        # weights2,3: norms (5,2),(6,13), dot products(0,-2)
        self.assertEqual(modal.mass_gram(self.basis, [2., 3.]), [[16., -6.], [-6., 51.]])

    def test_nonorthogonal_virtual_work(self):
        q = [2., -.5]
        u = modal.displacements(self.basis, q)
        Q = modal.generalized_forces(self.basis, self.forces)
        self.assertEqual(sum(a*b for p,f in zip(u,self.forces) for a,b in zip(p,f)), -14.5)
        self.assertEqual(sum(a*b for a,b in zip(q,Q)), -14.5)

    def test_general_mode_scaling_preserves_motion_work_and_energy(self):
        scales = [2., -.25]
        scaled = [[[s*x for x in p] for p in mode] for s,mode in zip(scales,self.basis)]
        q = [2., -.5]; qs = [x/s for x,s in zip(q,scales)]
        self.assertEqual(modal.displacements(scaled,qs), modal.displacements(self.basis,q))
        Q = modal.generalized_forces(self.basis,self.forces)
        Qs = modal.generalized_forces(scaled,self.forces)
        self.assertEqual(Qs,[s*x for s,x in zip(scales,Q)])
        self.assertEqual(sum(x*y for x,y in zip(q,Q)),sum(x*y for x,y in zip(qs,Qs)))
        M = modal.mass_gram(self.basis,[2.,3.]); Ms = modal.mass_gram(scaled,[2.,3.])
        energy = lambda a,m: sum(a[i]*m[i][j]*a[j] for i in range(2) for j in range(2))
        self.assertEqual(energy(q,M),energy(qs,Ms))

    def test_zero_root_and_owned_output(self):
        b = [[[0.,0.,0.],[1.,2.,3.]]]; f=[[1.,2.,3.],[4.,5.,6.]]; q=[.5]; m=[.1,.2]
        before=copy.deepcopy((b,f,q,m))
        u=modal.displacements(b,q); self.assertEqual(u[0],[0.,0.,0.]); u[1][0]=99
        Q=modal.generalized_forces(b,f); Q[0]=99
        M=modal.mass_gram(b,m); M[0][0]=99
        self.assertEqual((b,f,q,m),before)
        self.assertEqual(modal.displacements(b,[0.]),[[0.,0.,0.],[0.,0.,0.]])

    def test_compensated_summation(self):
        b=[[[1.e16,0.,0.]],[[1.,0.,0.]],[[-1.e16,0.,0.]]]
        self.assertEqual(modal.displacements(b,[1.,1.,1.])[0][0],1.)
        self.assertEqual(modal.generalized_forces([[[1.e16,1.,-1.e16]]],[[1.,1.,1.]]),[1.])

    def test_reject_invalid_basis_for_all_functions(self):
        invalid=[None,[],[[]],[[[1.,2.]]],[[[1.,2.,3.,4.]]],
                 [[[1.,2.,3.]],[]],[[['bad',0.,0.]]]]
        for value in [float('nan'), float('inf'), -float('inf')]:
            invalid.append([[[value, 0., 0.]]])
        for b in invalid:
            for fn,arg in [(modal.displacements,[1.]),(modal.generalized_forces,[[1.,2.,3.]]),(modal.mass_gram,[1.])]:
                with self.subTest(b=b,fn=fn.__name__), self.assertRaises(ValueError): fn(b,arg)

    def test_reject_invalid_coordinates_forces_and_masses(self):
        b=[[[1.,2.,3.]]]
        groups=[(modal.displacements,[None,[],[1.,2.],['bad'],[float('nan')],[float('inf')]]),
                (modal.generalized_forces,[None,[],[[1.,2.]],[[1.,2.,3.],[1.,2.,3.]],[[float('nan'),0.,0.]],[['bad',0.,0.]]]),
                (modal.mass_gram,[None,[],[1.,2.],[0.],[-1.],['bad'],[float('nan')],[float('inf')]])]
        for fn,args in groups:
            for arg in args:
                with self.subTest(fn=fn.__name__,arg=arg),self.assertRaises(ValueError): fn(b,arg)


if __name__ == '__main__': unittest.main()
