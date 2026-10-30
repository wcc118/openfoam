"""Analyze recorded prescribed-wall CFD work; never classify it as flutter."""
from pathlib import Path
import json, hashlib, re, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_case(folder):
    manifest=json.loads((folder/'cycle-manifest.json').read_text())
    files=[folder/'processor0/wall-work-cycle.csv']+sorted((folder/'processor0').glob('wall-work-cycle-resume*.csv'))
    merged={};overlaps=[];hashes={}
    for f in files:
        a=np.loadtxt(f,delimiter=',',ndmin=2)
        assert a.shape[1]==6 and np.isfinite(a).all()
        assert np.all(np.diff(a[:,0])>0)
        hashes[str(f.relative_to(folder))]=hashlib.sha256(f.read_bytes()).hexdigest()
        for row in a:
            k=round(float(row[0]),12)
            if k in merged:overlaps.append(dict(time_s=k,max_force_difference_N=float(max(abs(row[1:4]-merged[k][1:4]))),power_difference_W=float(abs(row[4]-merged[k][4]))))
            merged[k]=row
    data=np.array([merged[k] for k in sorted(merged)])
    force={}
    for f in sorted((folder/'postProcessing/forces').glob('*/force.dat'),key=lambda f:float(f.parent.name)):
        for line in f.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            row=np.array([float(v) for v in line.split()]);assert np.isfinite(row).all() and len(row)==10
            force[round(float(row[0]),12)]=row[1:4]
    error=max(float(max(abs(row[1:4]-force[round(float(row[0]),12)]))) for row in data)
    assert error<1e-8,error
    dt=manifest['dt_s'];assert np.max(abs(np.diff(data[:,0])-dt))<1e-10
    log='\n'.join(f.read_text() for f in sorted(folder.glob('log.pimpleFoam*')) if f.is_file())
    co=re.findall(r'Courant Number mean: [^\n]+? max: ([\deE.+-]+)',log)
    report=dict(scope=manifest['scope'],samples=len(data),first_time_s=float(data[0,0]),last_time_s=float(data[-1,0]),observed_dt_s=float(np.median(np.diff(data[:,0]))),native_force_max_error_N=error,wing_faces=sorted(set(data[:,5].tolist())),restart_overlap=overlaps,source_sha256=hashes,max_reported_Courant=float(max(map(float,co))) if co else None,execution=json.loads((folder/'cycle-execution.json').read_text()))
    report['all_observed_lift_N'] = dict(min=float(data[:,3].min()), max=float(data[:,3].max()), peak_to_peak=float(np.ptp(data[:,3])), standard_deviation=float(np.std(data[:,3])))
    report['terminal_verification'] = json.loads((folder/'cycle-verification-execution.json').read_text()) if (folder/'cycle-verification-execution.json').exists() else None
    report['saved_position_verification'] = json.loads((folder/'cycle-position-verification.json').read_text()) if (folder/'cycle-position-verification.json').exists() else None
    report['retained_original_execution'] = json.loads((folder/'cycle-execution.attempt1.json').read_text()) if (folder/'cycle-execution.attempt1.json').exists() else None
    report['verification_note'] = 'Original timeout manifest may reflect a prior pilot mesh check; only cycle-verification-execution and cycle-position-verification qualify the completed cycle. Lift variation includes startup and restart; common-time differences omit half-step-only extrema.'
    return data,manifest,report


def integral_window(a,start,end):
    assert a[0,0]<=start+1e-12 and a[-1,0]>=end-1e-12
    times=np.r_[start,a[(a[:,0]>start+1e-12)&(a[:,0]<end-1e-12),0],end]
    p=np.interp(times,a[:,0],a[:,4]);steps=np.diff(times)
    return dict(start_s=start,end_s=end,trapezoidal_work_J=float(np.sum(.5*(p[:-1]+p[1:])*steps)),right_endpoint_work_J=float(np.sum(p[1:]*steps)),quadrature_difference_J=float(np.sum(.5*(p[1:]-p[:-1])*steps)))


def main():
    coarse,half,out=map(Path,sys.argv[1:]);out.mkdir(exist_ok=False)
    a,ma,ra=read_case(coarse);b,mb,rb=read_case(half)
    seed=np.loadtxt(coarse/'processor0/wall-work-pilot.csv',delimiter=',',ndmin=2)[-1]
    assert abs(seed[0]-.004)<1e-12
    a=np.vstack([seed,a]);b=np.vstack([seed,b])
    keys={round(float(row[0]),12):row for row in b};paired=[(r,keys[round(float(r[0]),12)]) for r in a if round(float(r[0]),12) in keys]
    ac=np.array([r[0] for r in paired]);bc=np.array([r[1] for r in paired]);diff=ac[:,1:4]-bc[:,1:4]
    comparison=dict(common_samples=len(paired),start_s=float(ac[0,0]),end_s=float(ac[-1,0]),max_force_vector_difference_N=float(np.max(np.linalg.norm(diff,axis=1))),rms_force_vector_difference_N=float(np.sqrt(np.mean(np.sum(diff**2,axis=1)))),max_lift_difference_N=float(np.max(abs(diff[:,2]))),rms_lift_difference_N=float(np.sqrt(np.mean(diff[:,2]**2))),half_lift_standard_deviation_N=float(np.std(bc[:,3])),rms_power_difference_W=float(np.sqrt(np.mean((ac[:,4]-bc[:,4])**2))))
    comparison['common_window_coarse_work']=integral_window(a,float(ac[0,0]),float(ac[-1,0]))
    comparison['common_window_half_work']=integral_window(b,float(ac[0,0]),float(ac[-1,0]))
    target=.004+1/8.810675
    for data,report in [(a,ra),(b,rb)]:
        report['full_observed_cycle_available']=bool(data[-1,0]>=target-1e-12)
        report['full_cycle_work']=integral_window(data,.004,target) if report['full_observed_cycle_available'] else None
    result=dict(scope='Analytic prescribed parabolic wall-motion control on deliberately coarse no-layer CFD mesh. No native structural feedback, periodic-convergence, damping-validation or flutter claim. Actual native wall power; shared saved0.004s initialization. Timestep comparison includes the mesh-motion discretization.',coarse=ra,half=rb,comparison=comparison,analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    fig,axes=plt.subplots(4,1,figsize=(12,11),sharex=True,layout='constrained')
    fig.suptitle('Prescribed CFD control · timestep comparison\nAnalytic wall motion; no boundary layers; no structural feedback',fontsize=16)
    t=np.linspace(.004,max(a[-1,0],b[-1,0]),1500);axes[0].plot(t,100*np.sin(2*np.pi*8.810675*t),color='#333333');axes[0].set_ylabel('Nominal tip z (µm)')
    for data,label,color in [(a,'100 µs step','#2266aa'),(b,'50 µs step','#dd7722')]:
        axes[1].plot(data[:,0],data[:,3]-seed[3],label=label,color=color);axes[2].plot(data[:,0],data[:,4],color=color)
        work=np.r_[0,np.cumsum(.5*(data[1:,4]+data[:-1,4])*np.diff(data[:,0]))];axes[3].plot(data[:,0],work*1000,color=color)
    axes[1].set_ylabel('Lift change from\nshared start (N)');axes[1].legend();axes[2].set_ylabel('Applied wall power (W)');axes[3].set_ylabel('Accumulated work (mJ)');axes[3].set_xlabel('Physical time (s)')
    for ax in axes:ax.grid(alpha=.25);ax.axhline(0,color='#999999',linewidth=.6)
    if max(a[-1,0],b[-1,0])>=target:
        for ax in axes:ax.axvline(target,color='#888888',linestyle=':',linewidth=1)
    fig.savefig(out/'force-work-comparison.png',dpi=150)
    print(json.dumps(dict(coarse_samples=ra['samples'],half_samples=rb['samples'],coarse_cycle=ra['full_observed_cycle_available'],half_cycle=rb['full_observed_cycle_available'],comparison=comparison),indent=2))

if __name__=='__main__':main()
