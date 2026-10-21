"""Generate the finite Go six-role, MySQL/Redis development example; never deploy."""
import argparse,json
from grea.host.paths import Path
from .project_templates import publish,receipt

def generate(output):
    root=publish('server-go',output,{'__REDIS_IMAGE__':'public.ecr.aws/docker/library/redis@sha256:4fa24486b8bcca8eec45ee0eb166edc674795e53a2b53d1a9ef263eecebaac85'})
    (root/'.gitignore').write_text('.local/\ncompose.json\nbin/\n')
    return receipt(root,'server-go',dict(roles=['gateway','chat','server','login','world','billing'],mode='development',internal='gRPC/Protobuf',database='MySQL',cache='Redis',deployment='Docker',payment='Unavailable',actual_runtime='not_run'))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:r=generate(a.output);print(json.dumps(dict(status=r['status'],files=len(r['files']))));return 0
    except (ValueError,OSError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())
