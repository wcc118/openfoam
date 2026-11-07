"""Issue 50 evidence adapter. No solver execution or inferred CFD deformation."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import numpy as np

NATIVE_SHA = '8f5870bafb5f77b48f423102b5ab4451d710054e4f89bb15da76317da6cb0236'
INCH = .0254
LBF = 4.4482216152605

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def load_evidence(original, latest):
    original, latest = Path(original), Path(latest)
    sources = {}
    def read(path):
        sources[str(path.relative_to(original) if path.is_relative_to(original) else path.relative_to(latest))] = digest(path)
        return json.loads(path.read_text())
    native_path = original/'native-modal.npz'
    if digest(native_path) != NATIVE_SHA:
        raise ValueError('Native modal source does not match the pinned model')
    native = np.load(native_path, allow_pickle=False)
    xyz = native['xyz'].reshape(49,64,3)
    basis = native['phi'][:20].reshape(20,49,64,3)/math.sqrt(2)
    if not np.isfinite(xyz).all() or not np.isfinite(basis).all():
        raise ValueError('Nonfinite geometry/basis')
    if not np.all(np.diff(xyz[:,0,1]) > 0):
        raise ValueError('Expected increasing half-span station order')
    # Native shell stations are preserved; perimeter is sampled for display only.
    half = xyz[::2,::2].copy()
    hb = basis[:,::2,::2].copy()
    negative = half[1:][::-1].copy(); negative[:,:,1] *= -1
    nb = hb[:,1:][:,::-1].copy(); nb[:,:,:,1] *= -1
    points = np.concatenate([negative,half]).reshape(-1,3)
    modes = np.concatenate([nb,hb],axis=1).reshape(20,-1,3)
    triangles=[]
    for j in range(48):
        for k in range(32):
            a=j*32+k;b=j*32+(k+1)%32;c=(j+1)*32+(k+1)%32;d=(j+1)*32+k
            triangles.extend([[a,b,c],[a,c,d]])
    le=int(np.argmin(xyz[-1,:,0]));te=int(np.argmax(xyz[-1,:,0]))
    chord=xyz[: ,te]-xyz[:,le]
    baseline_rotation=np.arctan2(chord[:,2],chord[:,0])
    def metrics(q):
        q=np.asarray(q,dtype=float)
        if q.shape!=(20,) or not np.isfinite(q).all():raise ValueError('Expected 20 finite generalized coordinates')
        displacement=np.einsum('m,mskc->skc',q,basis)
        dc=displacement[:,te]-displacement[:,le]
        twist=np.rad2deg(np.arctan2(chord[:,2]+dc[:,2],chord[:,0]+dc[:,0])-baseline_rotation)
        span_z=displacement[:,:,2].mean(axis=1)/INCH
        return {'tip_in':float(span_z[-1]),'twist_deg':float(twist[-1]),
                'span_profile':[[float(xyz[i,0,1]/INCH),float(span_z[i]),float(twist[i])] for i in range(49)]}
    contract=read(original/'operating-contract.json')
    equilibria=[r for r in read(original/'constant-lift-screen-v2/summary.json') if r['modes']==20]
    if [r['speed_kn'] for r in equilibria]!=list(range(60,251,10)):raise ValueError('Missing or duplicate UVLM speeds')
    comparison=read(latest/'preview/comparison.json')
    pole_rows={r['speed_kn']:r for r in comparison['rows']}
    speeds=[]
    for row in equilibria:
        if row['native_sha256']!=NATIVE_SHA or row['stiffness_factor']!=1:raise ValueError('Changed structural reference')
        mm=metrics(row['equilibrium_q'])
        if abs(mm['tip_in']*INCH-row['tip_z_m'])>1e-10:raise ValueError('Native normalization/tip audit failed')
        p=pole_rows[row['speed_kn']]
        if abs(p['alpha_deg']-row['alpha_deg'])>1e-10:raise ValueError('Equilibrium and comparison disagree')
        lift=(-math.sin(math.radians(row['alpha_deg']))*row['force_xyz_N'][0]+math.cos(math.radians(row['alpha_deg']))*row['force_xyz_N'][2])/LBF
        if abs(lift-row['lift_N']/LBF)>1e-9:raise ValueError('UVLM wind-axis lift mismatch')
        speeds.append({'speed_kn':row['speed_kn'],'speed_m_s':row['speed_m_s'],'mach':row['Mach'],
          'uvlm':{'q':row['equilibrium_q'],'alpha_deg':row['alpha_deg'],'lift_lbf':lift,**mm,
          'elapsed_s':row['elapsed_s'],'timing_scope':'Equilibrium solve only; excludes aerodynamic-model assembly and pole/transient calculations',
          'status':'Equilibrium screened; physical accuracy unvalidated','pole_status':p['UVLM_status'],
          'weakest_growth_per_s':p['weakest_UVLM_growth_per_s'],'weakest_frequency_hz':p['weakest_UVLM_frequency_hz'],
          'bending_growth_per_s':p['bending_growth_per_s'],'bending_frequency_hz':p['bending_frequency_hz']},'cfd':[], 'transient':None})
    by_speed={r['speed_kn']:r for r in speeds}
    for a in comparison['CFD_fixed_pose_diagnostics']:
        folder=latest/a['case'];op=read(folder/'operating-point.json');execution=read(folder/'execution.json')
        assessment=read(folder/'static-assessment.json')
        if op['native_sha256']!=NATIVE_SHA or op['stiffness_factor']!=1:raise ValueError('CFD structural reference mismatch')
        q=op['equilibrium_q'];alpha=op['alpha_deg'];angle=math.radians(alpha)
        if not np.allclose(q,assessment['reference_q'],rtol=0,atol=1e-14) or abs(alpha-assessment['alpha_deg'])>1e-10:raise ValueError('CFD pose does not match force assessment')
        path=folder/'processor0/native-interface-work.csv';sources[str(path.relative_to(latest))]=digest(path)
        history=[]
        with path.open() as f:
            for row in csv.reader(f):
                if not row:continue
                values=[float(x) for x in row]
                if not all(math.isfinite(x) for x in values):raise ValueError('Nonfinite CFD history')
                history.append([values[0],(-math.sin(angle)*values[1]+math.cos(angle)*values[3])/LBF])
        if not history or abs(history[-1][1]-assessment['lift_lbf'])>1e-8:raise ValueError('CFD lift history mismatch')
        last=np.asarray(history[-100:])[:,1]
        observed_range=float(np.ptp(last)/np.mean(last))
        if abs(observed_range-assessment['last100_relative_lift_range'])>1e-10:raise ValueError('CFD force stationarity mismatch')
        if np.any(np.diff(np.asarray(history)[:,0])<=0):raise ValueError('Non-increasing CFD iterations')
        u=by_speed[a['speed_kn']]['uvlm']
        pose_diff=float(np.max(np.abs(np.asarray(q)-u['q'])))
        matched=abs(alpha-u['alpha_deg'])<1e-9 and pose_diff<1e-12
        status=[]
        if not a['force_history_stationary_gate_passed']:status.append('Force history not stationary')
        if not a['loaded_state_gate_passed']:status.append('Loaded-reference gates failed')
        status.append('Numerical settings sensitivity unresolved')
        by_speed[a['speed_kn']]['cfd'].append({'id':a['case'],
          'label':a['case'].replace('issue45-static-','').replace('-resume-20261106','').replace('-20261106','').replace('-',' '),
          'q_pose':q,'alpha_deg':alpha,'lift_lbf':assessment['lift_lbf'],**metrics(q),
          'lift_error_pct':100*(assessment['lift_lbf']/30-1),'balance_correction_in':assessment['maximum_force_balance_correction_m']/INCH,
          'stationary':a['force_history_stationary_gate_passed'],'loaded_gate':a['loaded_state_gate_passed'],
          'status':status,'solver':a['actual_solver'],'elapsed_s':execution['elapsed_s'],
          'timing_scope':'Bounded CFD execution including startup and final processing; concurrent jobs; not a scaling benchmark',
          'iterations':history[-1][0],'history':history,'history_axis':'Steady solver iteration (not physical time)',
          'matched_uvlm_inputs':matched,'alpha_difference_deg':alpha-u['alpha_deg'],'q_max_difference':pose_diff,
          'lift_difference_lbf':assessment['lift_lbf']-u['lift_lbf'],
          'comparison_label':'Same candidate pose and angle; different aerodynamic models' if matched else 'Different poses/angles: not a matched aerodynamic comparison',
          'shape_label':'Held CFD candidate pose; not CFD-predicted equilibrium deformation',
          'source':str(folder.name)})
    # Historical balanced reference remains visible, but new mesh/settings uncertainty applies.
    old=read(latest/'coarse-reference-evidence.json');a=old['static-assessment.json'];op=read(original/'state-60kn-v5.json')
    q=op['equilibrium_q'];u=by_speed[60]['uvlm']
    by_speed[60]['cfd'].insert(0,{'id':old['case'],'label':'60 kn historical coarse reference','q_pose':q,
      'alpha_deg':a['alpha_deg'],'lift_lbf':a['lift_lbf'],**metrics(q),'lift_error_pct':100*(a['lift_lbf']/30-1),
      'balance_correction_in':a['maximum_force_balance_correction_m']/INCH,'stationary':True,'loaded_gate':True,
      'status':['Historical balance passed','New numerical sensitivity prevents qualification'],'solver':'simpleFoam',
      'elapsed_s':old.get('execution.json',{}).get('elapsed_s'),'timing_scope':'Historical execution; not a controlled timing comparison',
      'iterations':500,'history':[],'history_axis':'History not included for this historical reference',
      'matched_uvlm_inputs':False,'alpha_difference_deg':a['alpha_deg']-u['alpha_deg'],
      'q_max_difference':float(np.max(np.abs(np.asarray(q)-u['q']))),'lift_difference_lbf':a['lift_lbf']-u['lift_lbf'],
      'comparison_label':'Separate constant-lift references, different poses and angles; CFD numerical qualification unresolved',
      'shape_label':'Historical CFD reference pose; numerical uncertainty remains','source':old['case']})
    # Recorded perturbation coordinates, not synthesized sinusoidal motion. Keep every sample.
    trans_summary=read(original/'constant-lift-transients/summary.json')
    for speed in (60,150,250):
        path=original/f'constant-lift-transients/{speed}kn.npz';sources[str(path.relative_to(original))]=digest(path)
        with np.load(path,allow_pickle=False) as z:
            time=z['time_s'];qd=z['q'][:,:,0]
            if str(z['names'][0])!='first_bending' or not np.isfinite(qd).all():raise ValueError('Unexpected transient channel')
            if not np.all(np.diff(time)>0):raise ValueError('Non-increasing transient times')
        model_path=original/f'constant-lift-dynamics/n20-{speed}kn/model.npz'
        sources[str(model_path.relative_to(original))]=digest(model_path)
        with np.load(model_path,allow_pickle=False) as z:
            eq=z['qeq']
        if not np.allclose(eq,by_speed[speed]['uvlm']['q'],rtol=0,atol=1e-14):raise ValueError('Transient reference does not match static equilibrium')
        tip_delta=qd@basis[:,-1,:,2].mean(axis=1)/INCH
        dchord=qd@(basis[:,-1,te]-basis[:,-1,le])
        loaded_chord=chord[-1]+eq@(basis[:,-1,te]-basis[:,-1,le])
        twist_delta=np.rad2deg(np.arctan2(loaded_chord[2]+dchord[:,2],loaded_chord[0]+dchord[:,0])-math.atan2(loaded_chord[2],loaded_chord[0]))
        summary=next(s for s in trans_summary if s['speed_kn']==speed)
        by_speed[speed]['transient']={'label':'Recorded UVLM small first-bending release about loaded equilibrium',
          'time_s':time.tolist(),'q_delta':qd.tolist(),'tip_delta_in':tip_delta.tolist(),'twist_delta_deg':twist_delta.tolist(),
          'initial_grid_displacement_in':summary['initial_grid_displacement_in'],
          'scope':'Original 20-mode surrogate; first-bending initial perturbation; zero assumed structural damping. No CFD motion or physical validation.',
          'seconds':float(time[-1]),'sample_dt_s':float(time[1]-time[0])}
    return {'schema_version':1,'title':'How the wing behaves across speed','speeds':speeds,
      'geometry':{'points_m':points.tolist(),'basis_xyz_per_q':modes.tolist(),'triangles':triangles,
        'note':'Sampled native structural surface; symmetric full-wing mirror. Display geometry is not the CFD volume mesh.'},
      'contract':contract,'native_sha256':NATIVE_SHA,'sources':sources,
      'conventions':{'axes':'x downstream, y spanwise, z up','moment_origin_m':[.0254,0,0],
        'twist':'Tip chord rotation relative to undeformed chord; positive when trailing edge rotates upward',
        'tip':'Mean vertical displacement of native tip perimeter nodes, relative to undeformed surface',
        'normalization':'Full-wing generalized coordinates use native half-wing phi/sqrt(2); mirrored y displacement changes sign'},
      'limits':['Clamped original linear unprestressed shell; symmetric modes only; not whole-aircraft trim',
        'UVLM is incompressible with aligned fixed straight wake; no separation model or viscous boundary layer',
        'CFD fixed-pose results remain diagnostic; long coupled dynamics held pending numerical qualification',
        'No modal-test or wind-tunnel validation linked here; agreement is not experimental accuracy',
        'No pressure-field colors or invented flow trajectories; surface colors identify methods'],
      'source_issue':'https://github.com/wcc118/openfoam/issues/45'}
