import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scripts.cfd_interface_transfer import build_interface, face_displacements, point_forces, verify_interface
from scripts.modal_surface import displacements, generalized_forces


def fixture():
    # A scalene trapezoid: its area centroid differs from the mean of its vertices.
    return dict(schema_version=1, axes=['x_downstream','y_spanwise','z_up'],length_unit='m',area_unit='m2',
                reference_state='exported_mesh',rank=0,patch='wing',time_s=0.,native_runtime='synthetic test fixture',
                point_ids=[90,4,71,9,800],points_m=[[0,0,0],[2,0,0],[1,1,0],[0,1,0],[0,0,1]],
                faces=[dict(id=100,point_indices=[0,1,2,3],center_m=[7/9,4/9,0],area_vector_m2=[0,0,1.5]),
                       dict(id=88,point_indices=[0,4,1],center_m=[2/3,0,1/3],area_vector_m2=[0,1,0])])


class NativeInterfaceTests(unittest.TestCase):
    def test_nonuniform_forces_moments_work_rigid_motion(self):
        e=fixture();m=build_interface(e);f=[[3.,-7.,2.],[-1.,.2,8.]]
        result=verify_interface(e,f)
        self.assertTrue(result['passed'])
        self.assertIn('supplied',result['loads_source'])
        np.testing.assert_allclose(face_displacements(m,e['points_m']),[x['center_m'] for x in e['faces']],atol=1e-14)
        # Deliberately nonuniform displacements and loads; independent scalar work sums.
        u=[[.2,-.3,.4],[.5,.7,-.6],[-.8,.1,.3],[.9,-.2,.6],[-.4,.3,.8]]
        fp=point_forces(m,f);uf=face_displacements(m,u)
        self.assertAlmostEqual(sum(np.dot(a,b) for a,b in zip(f,uf)),sum(np.dot(a,b) for a,b in zip(fp,u)),places=13)
        self.assertGreater(abs(sum(np.dot(a,b) for a,b in zip(f,uf))),.1)
        self.assertFalse(np.allclose(m.weights[:4],.25))

    def test_nonplanar_native_centroid_and_area(self):
        e=fixture();x=np.array([[0.,0.,0.],[2.,0.,0.],[1.5,1.,.2],[0.,1.,0.]])
        c=x.mean(axis=0);area=[];centroid=[]
        for a,b in zip(x,np.roll(x,-1,axis=0)):
            area.append(np.cross(a-c,b-c)/2);centroid.append((a+b+c)/3)
        magnitudes=np.linalg.norm(area,axis=1)
        e['points_m']=x.tolist();e['point_ids']=e['point_ids'][:4];e['faces']=e['faces'][:1]
        e['faces'][0].update(center_m=np.average(centroid,axis=0,weights=magnitudes).tolist(),area_vector_m2=np.sum(area,axis=0).tolist())
        self.assertTrue(verify_interface(e)['passed'])

    def test_signed_mode_rescaling(self):
        e=fixture();m=build_interface(e);x=np.array(e['points_m'])
        H=[np.column_stack((x[:,1],x[:,2],1+x[:,0])).tolist(),np.column_stack((.3+x[:,2],x[:,0],x[:,0]*x[:,1])).tolist()]
        q=[.002,-.003];f=[[4.,2.,-1.],[3.,-5.,2.]];fp=point_forces(m,f)
        u=displacements(H,q);Q=generalized_forces(H,fp)
        h2=(np.array(H)*np.array([-2.,.4])[:,None,None]).tolist();q2=(np.array(q)/[-2.,.4]).tolist()
        Q2=generalized_forces(h2,fp)
        np.testing.assert_allclose(displacements(h2,q2),u,atol=1e-15)
        self.assertAlmostEqual(np.dot(Q,q),np.dot(Q2,q2),places=14)
        self.assertAlmostEqual(np.dot(Q,q),np.sum(np.array(f)*face_displacements(m,u)),places=14)

    def test_point_permutation_preserves_geometry_and_transfer(self):
        e=fixture();f=[[3.,1.,2.],[.5,-2.,4.]];first=verify_interface(e,f)
        order=[4,2,0,3,1];inverse={v:i for i,v in enumerate(order)}
        e['points_m']=[e['points_m'][i] for i in order];e['point_ids']=[e['point_ids'][i] for i in order]
        for face in e['faces']:face['point_indices']=[inverse[i] for i in face['point_indices']]
        second=verify_interface(e,f)
        np.testing.assert_allclose(first['point_total_force_N'],second['point_total_force_N'])
        self.assertAlmostEqual(first['face_modal_work_J'],second['face_modal_work_J'],places=14)
        self.assertTrue(second['passed'])

    def test_mapping_owns_arrays_and_is_sparse(self):
        e=fixture();m=build_interface(e);e['points_m'][0][0]=100
        self.assertEqual(m.points[0,0],0)
        with self.assertRaises(ValueError):m.weights[0]=99
        self.assertEqual(len(m.weights),7)
        self.assertEqual(m.weights.ndim,1)

    def test_invalid_geometry_metadata(self):
        changes=[lambda e:e.update(schema_version=True),lambda e:e.update(length_unit='mm'),
                 lambda e:e.update(area_unit='cm2'),lambda e:e.update(axes=['x','y','z']),
                 lambda e:e.update(rank=False),lambda e:e.update(time_s=True),
                 lambda e:e.update(reference_state='projected'),lambda e:e.update(native_runtime=''),
                 lambda e:e['point_ids'].__setitem__(0,True),lambda e:e['point_ids'].__setitem__(0,4),
                 lambda e:e['faces'][0].update(point_indices=[0,1,1]),lambda e:e['faces'][0].update(point_indices=[0,1,99]),
                 lambda e:e['faces'][0].update(center_m=[.75,.5,0]),lambda e:e['faces'][0].update(area_vector_m2=[0,0,-1.5]),
                 lambda e:e['faces'][0].update(id=88),lambda e:e['points_m'][0].__setitem__(0,float('nan')),
                 lambda e:e['points_m'][0].__setitem__(0,True)]
        for change in changes:
            e=fixture();change(e)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):build_interface(e)
        e=fixture();e['points_m']=[[0,0,0]]*5
        with self.assertRaisesRegex(ValueError,'degenerate'):build_interface(e)

    def test_reject_bad_load_and_mode_shapes(self):
        m=build_interface(fixture())
        for value in ([[True,0,0]]*2,[[float('inf'),0,0]]*2,[[np.complex128(1+2j),0,0]]*2,[[1,2,3]]):
            with self.assertRaises(ValueError):point_forces(m,value)
        with self.assertRaises(ValueError):face_displacements(m,[[1,2,3]])
        with self.assertRaises(ValueError):verify_interface(fixture(),modes=[[[1,0,0]]])

    def test_native_cfd_excerpt(self):
        p=Path(__file__).parent/'fixtures/cfd_interface/native_span32_excerpt.json'
        data=json.loads(p.read_text())
        self.assertEqual(data['loads']['face_ids'],[f['id'] for f in data['geometry']['faces']])
        self.assertEqual(data['modes']['point_ids'],data['geometry']['point_ids'])
        result=verify_interface(data['geometry'],data['loads']['forces_N'],data['modes']['shapes'])
        self.assertTrue(result['passed'])
        self.assertGreater(result['nonzero_weights'],result['face_count']*3)
        self.assertLess(result['geometry_checks']['max_centroid_error_m'],1e-12)

    def test_cli_clean_copy_hashes_and_invalid_input(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'scripts').mkdir()
            for name in ('cfd_interface_transfer.py','modal_surface.py'):
                shutil.copy2(root/'scripts'/name,p/'scripts'/name)
            input_path=p/'interface.json';input_path.write_text(json.dumps(fixture(),indent=2))
            output=p/'result.json'
            cmd=[sys.executable,'-m','scripts.cfd_interface_transfer',str(input_path),'--output',str(output)]
            r=subprocess.run(cmd,cwd=p,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            data=json.loads(output.read_text());self.assertTrue(data['passed'])
            self.assertEqual(data['input_file_sha256']['export'],hashlib.sha256(input_path.read_bytes()).hexdigest())
            self.assertIn('synthetic',data['loads_source']);self.assertIn('synthetic',data['modes_source'])
            loads=p/'loads.json';loads.write_text(json.dumps(dict(quantity='integrated_point_force',force_unit='N',face_ids=[88,100],forces_N=[[1,2,3],[4,5,6]])))
            output.unlink();r=subprocess.run(cmd+['--loads',str(loads)],cwd=p,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse(output.exists());self.assertIn('order',r.stderr)
            loads.write_text(json.dumps(dict(quantity='pressure',force_unit='Pa',face_ids=[100,88],forces_N=[[1,2,3],[4,5,6]])))
            r=subprocess.run(cmd+['--loads',str(loads)],cwd=p,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
