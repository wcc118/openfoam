"""Build an offline wing-behavior viewer from retained issue45 evidence."""
import argparse
import json
from pathlib import Path
from behavior_viewer.data import load_evidence


def build(original, latest, output):
    data=load_evidence(Path(original).resolve(),Path(latest).resolve())
    assets=Path(__file__).parent/'behavior_viewer'
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    payload=json.dumps(data,allow_nan=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(assets/'viewer.html').read_text()
    if template.count('__BEHAVIOR_DATA__')!=1 or template.count('__BEHAVIOR_SCRIPT__')!=1:raise ValueError('Invalid template placeholders')
    document=template.replace('__BEHAVIOR_DATA__',payload).replace('__BEHAVIOR_SCRIPT__',(assets/'viewer.js').read_text())
    (output/'index.html').write_text(document)
    (output/'data.json').write_text(json.dumps(data,allow_nan=False,separators=(',',':')))
    (output/'provenance.json').write_text(json.dumps({'native_sha256':data['native_sha256'],'sources':data['sources'],'scope':data['limits']},indent=2))
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',required=True,type=Path);p.add_argument('--latest',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    data=build(a.original,a.latest,a.output)
    print(json.dumps({'speeds':len(data['speeds']),'cfd_cases':sum(len(s['cfd']) for s in data['speeds']),'viewer':str(a.output/'index.html')}))
