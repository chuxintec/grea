"""Explicit missing-provider install from chuxintec/monkey's latest stable Release.

Never runs a downloaded installer, modifies system Python, or upgrades an existing
provider. Download identities and failed attempts are retained for inspection.
"""
import email,hashlib,json,os,re,shutil,ssl,subprocess,sys,time,urllib.request,urllib.error,zipfile
from pathlib import Path
from urllib.parse import urlsplit
from grea.common import write_new,hash_file

LATEST='https://api.github.com/repos/chuxintec/monkey/releases/latest'
HOSTS={'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}


class GitHubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def validate_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError('Only official GitHub HTTPS release endpoints are accepted')


def download(url,path,limit):
    validate_url(url);path=Path(path)
    if path.exists():raise ValueError('Download destination already exists')
    try:
        import truststore
        context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:context=ssl.create_default_context()
    request=urllib.request.Request(url,headers={'User-Agent':'grea-monkey-provider','Accept':'application/vnd.github+json' if url==LATEST else 'application/octet-stream'})
    opener=urllib.request.build_opener(GitHubRedirect(),urllib.request.HTTPSHandler(context=context))
    for attempt in range(3):
        temporary=path.with_name(path.name+'.attempt-'+str(attempt))
        try:
            with opener.open(request,timeout=30) as response,temporary.open('xb') as output:
                validate_url(response.geturl());count=0;final_url=response.geturl()
                while True:
                    chunk=response.read(min(1024**2,limit-count+1))
                    if not chunk:break
                    count+=len(chunk)
                    if count>limit:raise ValueError('Release download exceeds bounded size')
                    output.write(chunk)
            temporary.rename(path)
            return dict(hash_file(path),final_url=final_url)
        except urllib.error.HTTPError:
            raise  # API throttling has a separate official-release fallback.
        except (urllib.error.URLError,TimeoutError,ConnectionError) as error:
            if isinstance(getattr(error,'reason',None),ssl.SSLCertVerificationError) or attempt==2:raise
            time.sleep(0.25*(attempt+1))
    raise ValueError('Download did not complete')


def select_assets(release):
    version=release.get('tag_name','').removeprefix('v')
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('Expected a stable semantic release from /releases/latest')
    wanted=[f'monkey_native-{version}-py3-none-any.whl','SHA256SUMS'];chosen={}
    for name in wanted:
        matches=[a for a in release.get('assets',[]) if a.get('name')==name]
        if len(matches)!=1:raise ValueError('Missing/ambiguous required release asset: '+name)
        row=matches[0];url=row['browser_download_url'];validate_url(url)
        if not url.startswith('https://github.com/chuxintec/monkey/releases/download/'+release['tag_name']+'/'):
            raise ValueError('Asset is not attached to the expected repository release')
        chosen[name]=row
    return version,chosen


def wheel_digest(checksums,name):
    found=[]
    for line in checksums.splitlines():
        match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(.+)',line.strip())
        if match and match[2]==name:found.append(match[1].lower())
    if len(found)!=1:raise ValueError('Missing/ambiguous wheel checksum')
    return found[0]


def verify_wheel(wheel,digest,version):
    if hash_file(wheel)['sha256']!=digest:raise ValueError('Release checksum mismatch')
    with zipfile.ZipFile(wheel) as archive:
        metadata=[n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        if len(metadata)!=1:raise ValueError('Expected one wheel distribution')
        if archive.getinfo(metadata[0]).file_size>1024**2:raise ValueError('Oversized wheel metadata')
        meta=email.message_from_bytes(archive.read(metadata[0]))
    if meta['Name']!='monkey-native' or meta['Version']!=version:raise ValueError('Wheel identity does not match Release')
    # Dependencies must be exact; no unbounded dependency or direct URL is installed.
    for requirement in meta.get_all('Requires-Dist',[]):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\s*(?:\(==[^() ;]+\)|==[^ ;]+)(?:\s*;.*)?',requirement):
            raise ValueError('Wheel dependency is not exactly versioned: '+requirement)
    return dict(name=meta['Name'],version=meta['Version'],dependencies=meta.get_all('Requires-Dist',[]))


def stable_python(state):
    base=Path(sys.base_prefix)
    if base.name!='runtime':return sys.executable
    # Portable plugin runtimes may be removed on upgrade. Keep an independent
    # copy before creating a provider venv whose stdlib depends on that prefix.
    identity=hash_file(Path(sys.executable).resolve())['sha256'];root=state/'python'/identity
    if not root.exists():
        root.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(base,root)
    executable=root/'bin/python3'
    if hash_file(executable)['sha256']!=identity:raise ValueError('Persistent provider Python identity mismatch')
    return str(executable)


def install_latest(state,output):
    state=Path(state);out=Path(output);out.mkdir();state.mkdir(parents=True,exist_ok=True)
    if os.name!='posix':raise ValueError('Automatic Release installation currently supports POSIX; configure a verified provider on other hosts')
    guard=state/'.install.lock';fd=os.open(guard,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    try:
        release=latest_release(out);version,assets=select_assets(release)
        name=f'monkey_native-{version}-py3-none-any.whl'
        download(assets['SHA256SUMS']['browser_download_url'],out/'SHA256SUMS',1024**2)
        expected=wheel_digest((out/'SHA256SUMS').read_text(),name)
        actual=download(assets[name]['browser_download_url'],out/name,128*1024**2)
        if assets[name].get('size') is not None and assets[name]['size']!=actual['bytes']:raise ValueError('GitHub asset size mismatch')
        api_digest=assets[name].get('digest')
        if api_digest and api_digest!='sha256:'+expected:raise ValueError('GitHub and SHA256SUMS disagree')
        metadata=verify_wheel(out/name,expected,version)
        release_dir=state/'releases'/version
        if release_dir.exists():raise ValueError('Existing installation directory retained; inspect it before retrying')
        release_dir.parent.mkdir(parents=True,exist_ok=True)
        with (out/'installation.log').open('xb') as log:
            python=stable_python(state)
            subprocess.run([python,'-I','-m','venv','--copies',str(release_dir)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
            executable=release_dir/'bin/python'
            subprocess.run([str(executable),'-I','-m','pip','--isolated','install','--disable-pip-version-check','--no-input','--only-binary=:all:','--index-url','https://pypi.org/simple',str(out/name)+'[astc]'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            subprocess.run([str(executable),'-I','-m','pip','--isolated','check'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
        command=release_dir/'bin/monkey'
        from .local import probe_installation
        info=probe_installation([str(command)])
        if info['version']!=version:raise ValueError('Installed version differs from downloaded release')
        receipt=dict(schema_version=1,version=version,command=str(command),wheel_sha256=expected,release_id=release.get('id'),release_tag=release['tag_name'],release_url=release.get('html_url'),metadata=metadata,python=python)
        write_new(release_dir/'grea-install.json',receipt)
        # Remember an installed but adapter-incompatible newer version without
        # hiding it or installing it again on the next readiness attempt.
        write_new(state/'installed.json',receipt)
        write_new(out/'result.json',receipt);return receipt
    finally:guard.unlink()


def latest_release(out):
    """Official HTML fallback for public API rate limiting, without credentials."""
    try:
        download(LATEST,out/'release.json',4*1024**2)
        return json.loads((out/'release.json').read_text())
    except urllib.error.HTTPError as error:
        if error.code not in (403,429,500,502,503,504):raise
        fallback_reason='github_api_http_'+str(error.code)
    page=download('https://github.com/chuxintec/monkey/releases/latest',out/'latest.html',8*1024**2)
    prefix='https://github.com/chuxintec/monkey/releases/tag/'
    if not page['final_url'].startswith(prefix):raise ValueError('Latest Release did not resolve to an official version tag')
    tag=page['final_url'][len(prefix):]
    if not re.fullmatch(r'v?\d+\.\d+\.\d+',tag):raise ValueError('Latest Release is not stable')
    download('https://github.com/chuxintec/monkey/releases/expanded_assets/'+tag,out/'assets.html',4*1024**2)
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            href=dict(attrs).get('href','')
            if tag=='a' and href.startswith('/chuxintec/monkey/releases/download/'):
                self.paths.append(href)
    parser=Links();parser.feed((out/'assets.html').read_text())
    value=dict(tag_name=tag,draft=False,prerelease=False,html_url=page['final_url'],discovery='official-release-html',fallback_reason=fallback_reason,assets=[dict(name=p.rsplit('/',1)[-1],browser_download_url='https://github.com'+p)for p in parser.paths])
    write_new(out/'release-fallback.json',value);return value
