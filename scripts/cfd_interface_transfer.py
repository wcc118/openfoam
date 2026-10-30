"""Fixed-geometry native CFD face/point transfer with an exact force transpose.

This is numerical interface verification, not OpenFOAM moving-wall velocity or FSI.
Storage is proportional to face vertices, never faces times mesh points.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scripts.modal_surface import displacements, generalized_forces

AXES = ['x_downstream', 'y_spanwise', 'z_up']


def _numbers(value, shape, name):
    def walk(v):
        if isinstance(v, (list, tuple)):
            for child in v:
                walk(child)
        elif isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)):
            raise ValueError(f'{name}: require numbers, not bool')
    walk(value)
    a = np.array(value, dtype=float, copy=True)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'{name}: require finite shape {shape}')
    return a


def _ids(value, name, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f'{name}: require a list of IDs')
    if any(type(v) is not int or v < 0 for v in value) or len(set(value)) != len(value):
        raise ValueError(f'{name}: require unique nonnegative integer IDs')
    return tuple(value)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Interface:
    point_ids: tuple
    face_ids: tuple
    points: np.ndarray
    centers: np.ndarray
    areas: np.ndarray
    vertices: np.ndarray
    owners: np.ndarray
    weights: np.ndarray
    geometry_hash: str
    centroid_error_m: float
    area_error_m2: float


def build_interface(export):
    if not isinstance(export, dict) or type(export.get('schema_version')) is not int or export['schema_version'] != 1:
        raise ValueError('schema_version must be integer1')
    for key, expected in dict(axes=AXES, length_unit='m', area_unit='m2', reference_state='exported_mesh', patch='wing').items():
        if export.get(key) != expected:
            raise ValueError(f'unsupported {key}; expected {expected}')
    if type(export.get('rank')) is not int or export['rank'] < 0:
        raise ValueError('rank must be a nonnegative integer')
    if _numbers(export.get('time_s'), (), 'time_s') < 0:
        raise ValueError('time_s must be nonnegative')
    if not isinstance(export.get('native_runtime'), str) or not export['native_runtime'].strip():
        raise ValueError('native_runtime must be explicit')
    point_ids = _ids(export.get('point_ids'), 'point_ids')
    points = _numbers(export.get('points_m'), (len(point_ids), 3), 'points_m')
    faces = export.get('faces')
    if not isinstance(faces, list) or not faces or any(not isinstance(f, dict) for f in faces):
        raise ValueError('faces must be a nonempty list of objects')
    face_ids = _ids([f.get('id') for f in faces], 'face IDs')
    vertices, owners, weights, centers, areas = [], [], [], [], []
    max_center, max_area = 0., 0.
    for i, face in enumerate(faces):
        ids = _ids(face.get('point_indices'), 'face point_indices')
        if len(ids) < 3 or max(ids) >= len(points):
            raise ValueError('face requires >=3 valid point indices')
        x = points[list(ids)]
        center = _numbers(face.get('center_m'), (3,), 'center_m')
        area = _numbers(face.get('area_vector_m2'), (3,), 'area_vector_m2')
        fan = x.mean(axis=0)
        triangle_vectors = .5*np.cross(x-fan, np.roll(x, -1, axis=0)-fan)
        triangle_areas = np.linalg.norm(triangle_vectors, axis=1)
        total = triangle_areas.sum()
        if not np.isfinite(total) or np.any(triangle_areas <= 0) or np.linalg.norm(triangle_vectors.sum(axis=0)) == 0:
            raise ValueError(f'degenerate face {face_ids[i]}')
        # Triangle endpoint contributions plus the fan-center contribution to ALL vertices.
        w = (triangle_areas + np.roll(triangle_areas, 1))/(3*total) + 1/(3*len(ids))
        center_error = float(np.linalg.norm(w@x-center))
        area_error = float(np.linalg.norm(triangle_vectors.sum(axis=0)-area))
        if abs(w.sum()-1) > 1e-12 or center_error > 1e-10:
            raise ValueError(f'native centroid mismatch on face {face_ids[i]}: {center_error}m')
        if area_error > 1e-12 + 1e-10*np.linalg.norm(area):
            raise ValueError(f'native area-vector mismatch on face {face_ids[i]}: {area_error}m2')
        vertices.extend(ids); owners.extend([i]*len(ids)); weights.extend(w)
        centers.append(center); areas.append(area)
        max_center=max(max_center,center_error); max_area=max(max_area,area_error)
    arrays = [points, np.array(centers), np.array(areas), np.array(vertices, dtype=int),
              np.array(owners, dtype=int), np.array(weights)]
    for a in arrays:
        a.flags.writeable = False
    return Interface(point_ids, face_ids, *arrays, _hash(export), max_center, max_area)


def face_displacements(mapping, point_displacements):
    u = _numbers(point_displacements, (len(mapping.point_ids), 3), 'point_displacements')
    result = np.zeros((len(mapping.face_ids), 3))
    np.add.at(result, mapping.owners, mapping.weights[:, None]*u[mapping.vertices])
    return result.tolist()


def point_forces(mapping, face_forces):
    f = _numbers(face_forces, (len(mapping.face_ids), 3), 'face_forces')
    result = np.zeros((len(mapping.point_ids), 3))
    np.add.at(result, mapping.vertices, mapping.weights[:, None]*f[mapping.owners])
    return result.tolist()


def _check(actual, expected, atol, scale):
    error = float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))
    tolerance = float(atol + 1e-12*scale)
    return dict(max_absolute_error=error, tolerance=tolerance, passed=error <= tolerance)


def verify_interface(export, face_forces=None, modes=None):
    m = build_interface(export)
    x, c = m.points, m.centers
    synthetic_loads = face_forces is None
    if synthetic_loads:
        face_forces = (1e-4*np.column_stack((1+np.sin(c[:,0]+c[:,1]), np.cos(c[:,1]), .5+c[:,2]))).tolist()
    f = _numbers(face_forces, (len(m.face_ids), 3), 'face_forces')
    fp = np.array(point_forces(m, face_forces))
    checks = {'force_N': _check(fp.sum(axis=0), f.sum(axis=0), 1e-10, np.abs(f).sum())}
    moments=[]
    for origin in (np.zeros(3), np.array([.0254, -.37, .11])):
        expected = np.cross(c-origin, f).sum(axis=0)
        actual = np.cross(x-origin, fp).sum(axis=0)
        check = _check(actual, expected, 1e-10, np.abs(np.cross(c-origin,f)).sum())
        moments.append(dict(origin_m=origin.tolist(), face_moment_N_m=expected.tolist(), point_moment_N_m=actual.tolist(), **check))
    u = 1e-4*np.column_stack((np.sin(x[:,0]+2*x[:,1]), np.cos(x[:,1]-x[:,2]), x[:,0]*x[:,1]+.1))
    uf = np.array(face_displacements(m, u.tolist()))
    point_work, face_work = float(np.sum(fp*u)), float(np.sum(f*uf))
    checks['virtual_work_J'] = _check(point_work, face_work, 1e-12, np.abs(f*uf).sum())
    shift=np.array([.001,-.002,.003]); angle=np.array([.003,-.001,.002])
    checks['rigid_translation_m'] = _check(face_displacements(m, np.tile(shift,(len(x),1)).tolist()), shift, 1e-12, np.abs(shift).max())
    checks['rigid_rotation_m'] = _check(face_displacements(m, np.cross(angle,x).tolist()), np.cross(angle,c), 1e-12, np.abs(np.cross(angle,c)).max())
    synthetic_modes=modes is None
    if synthetic_modes:
        modes=[np.column_stack((x[:,1], .2*x[:,0], .5+x[:,1]**2)).tolist(),
               np.column_stack((-.3+x[:,2], x[:,0], x[:,0]*x[:,1])).tolist()]
    if not isinstance(modes, list) or not modes:
        raise ValueError('modes must be a nonempty list')
    _numbers(modes,(len(modes),len(x),3),'modes')
    q=[1e-5*(-1)**i/(i+1) for i in range(len(modes))]
    um=displacements(modes,q)
    Q=generalized_forces(modes,fp.tolist())
    face_modal_work=float(np.sum(f*np.array(face_displacements(m,um))))
    modal_work=float(np.dot(Q,q))
    checks['modal_work_J']=_check(modal_work,face_modal_work,1e-12,np.abs(f*np.array(face_displacements(m,um))).sum())
    report=dict(schema_version=1,scope='Fixed-geometry numerical interface verification only; no flow, damping, flutter or coupled FSI qualification.',
                native_export={k:export[k] for k in ('native_runtime','rank','time_s','reference_state','patch')},
                reference_bounds_m=[x.min(axis=0).tolist(),x.max(axis=0).tolist()],
                geometry_sha256=m.geometry_hash, point_count=len(x),face_count=len(c),nonzero_weights=len(m.weights),
                units=dict(length='m',force='N',moment='N m',work='J',modal_basis='dimensionless',modal_coordinate='m'),axes=AXES,
                loads_source='synthetic diagnostic forces' if synthetic_loads else 'supplied integrated point forces; provenance owned by caller',
                modes_source='synthetic diagnostic shapes' if synthetic_modes else 'supplied point shapes; normalization owned by caller',
                force_sha256=_hash(face_forces),modes_sha256=_hash(modes),
                geometry_checks=dict(max_centroid_error_m=m.centroid_error_m,centroid_tolerance_m=1e-10,max_area_vector_error_m2=m.area_error_m2,area_absolute_tolerance_m2=1e-12,area_relative_tolerance=1e-10),
                checks=checks,moments=moments,face_total_force_N=f.sum(axis=0).tolist(),point_total_force_N=fp.sum(axis=0).tolist(),
                point_work_J=point_work,face_work_J=face_work,generalized_forces_N=Q,modal_work_J=modal_work,face_modal_work_J=face_modal_work,
                remaining_gates=['native shell-to-CFD point projection and its transpose','actual movingWallVelocity/mesh-flux work','native load provenance','moving-mesh quality','periodic and timestep convergence','implicit checkpoint/feedback verification'])
    report['passed']=all(v['passed'] for v in checks.values()) and all(v['passed'] for v in moments)
    json.dumps(report,allow_nan=False)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export');parser.add_argument('--output',required=True)
    parser.add_argument('--loads');parser.add_argument('--modes');args=parser.parse_args()
    try:
        raw=Path(args.export).read_bytes();export=json.loads(raw)
        loads,modes=None,None;hashes={'export':hashlib.sha256(raw).hexdigest()}
        for kind,path in [('loads',args.loads),('modes',args.modes)]:
            if path is None:continue
            raw_input=Path(path).read_bytes();value=json.loads(raw_input);hashes[kind]=hashlib.sha256(raw_input).hexdigest()
            if not isinstance(value,dict):raise ValueError(f'{kind} must be an object')
            if kind=='loads':
                if value.get('quantity')!='integrated_point_force' or value.get('force_unit')!='N':raise ValueError('require integrated point forces in N')
                ids=_ids(value.get('face_ids'),'load face_ids')
                if ids!=tuple(f['id'] for f in export['faces']):raise ValueError('load face order mismatch')
                loads=value['forces_N']
            else:
                if value.get('basis_units')!='dimensionless' or value.get('coordinate_units')!='m':raise ValueError('unsupported modal units')
                if _ids(value.get('point_ids'),'mode point_ids')!=tuple(export['point_ids']):raise ValueError('mode point order mismatch')
                modes=value['shapes']
        result=verify_interface(export,loads,modes);result['input_file_sha256']=hashes
        encoded=json.dumps(result,indent=2,allow_nan=False)
        output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(encoded+'\n')
        return 0 if result['passed'] else 2
    except (ValueError,TypeError,KeyError,OSError,OverflowError) as error:
        print(f'Error: {error}',file=sys.stderr);return 1


if __name__=='__main__':
    sys.exit(main())
