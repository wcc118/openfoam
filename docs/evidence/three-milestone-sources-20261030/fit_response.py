"""Estimate a late single-mode release envelope; keep the fitted centre explicit."""
import numpy as np
from scipy import optimize,signal

def fit(t,q,start):
 t=np.asarray(t);q=np.asarray(q);mask=t>=start;t=t[mask];q=q[mask];tau=t-t[0]
 if len(t)<20 or t[-1]-t[0]<.25:return dict(status='insufficient_history')
 scale=max(float(np.ptp(q)),1e-12)
 def evaluate(x):
  growth,freq=x;e=np.exp(growth*tau);design=np.column_stack([np.ones(len(t)),e*np.cos(2*np.pi*freq*tau),e*np.sin(2*np.pi*freq*tau)]);coef=np.linalg.lstsq(design,q,rcond=None)[0];return design@coef,coef
 sol=optimize.least_squares(lambda x:(evaluate(x)[0]-q)/scale,[-5.,8.81],bounds=([-50.,5.],[20.,15.]),xtol=1e-12,ftol=1e-12,gtol=1e-12)
 predicted,coef=evaluate(sol.x);center=float(coef[0]);rms=float(np.sqrt(np.mean((q-predicted)**2)));normalized_rms=rms/max(float(np.std(q)),1e-12)
 ix,_=signal.find_peaks(q,distance=max(1,int(.04/np.median(np.diff(t)))))
 ix=ix[q[ix]-center>1e-7];peaks=None
 if len(ix)>=4:
  slope,intercept=np.polyfit(t[ix],np.log(q[ix]-center),1);res=np.log(q[ix]-center)-(slope*t[ix]+intercept)
  peaks=dict(count=len(ix),times_s=t[ix].tolist(),amplitudes_m=(q[ix]-center).tolist(),growth_per_s=float(slope),frequency_hz=float(1/np.mean(np.diff(t[ix]))),log_amplitude_rms=float(np.sqrt(np.mean(res**2))))
 acceptable=bool(sol.success and peaks and normalized_rms<.1)
 return dict(status='fit_available' if acceptable else 'indeterminate',requested_start_s=start,fit_start_s=float(t[0]),fit_end_s=float(t[-1]),growth_per_s=float(sol.x[0]),frequency_hz=float(sol.x[1]),fitted_center_m=center,rms_residual_m=rms,residual_over_signal_std=normalized_rms,positive_peak_fit=peaks,criterion='At least four positive peaks >0.1 micrometre about the fitted centre; damped-sinusoid RMS residual <10% of signal standard deviation. Estimating criterion, not physical validation.')

if __name__=='__main__':
 import argparse,json,hashlib
 from pathlib import Path
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--audit',type=Path,required=True);a=p.parse_args();h=json.loads(a.input.read_text());rows=h['rows'];t=np.r_[0.,[r['time_s'] for r in rows]];q=np.r_[h['settings']['initial_q_m'],[r['q_m'] for r in rows]]
 audit=json.loads(a.audit.read_text());run_checks=bool(h['completed'] and audit['completed'] and not audit['mesh_failed'] and audit['mesh_ok_count']>=2 and audit['execution']['exit_code']==0 and audit['max_native_force_difference_N']<1e-8)
 fits=[fit(t,q,start) for start in (.05,.15)]
 rates=[r[key]['growth_per_s'] if key else r['growth_per_s'] for r in fits if r['status']=='fit_available' for key in ('','positive_peak_fit')]
 classification='indeterminate'
 if run_checks and len(rates)==4:
  if max(rates)<0:classification='observed_decay'
  elif min(rates)>0:classification='observed_growth'
 result=dict(history_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),audit_sha256=hashlib.sha256(a.audit.read_bytes()).hexdigest(),completed=h['completed'],run_checks_passed=run_checks,classification=classification,fits=fits,scope='Single first-bending-mode CFD release. Fitted late-response centre is distinct from the steady SIMPLE loaded pose; no actual-wing flutter conclusion.')
 with a.output.open('x') as stream:json.dump(result,stream,indent=2)
 print(json.dumps(result,indent=2))
