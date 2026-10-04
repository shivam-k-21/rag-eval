"""Local, read-only RAG report visualizer. No API keys or provider calls."""
import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent


def _evidence(report, root):
    spec = report.get('config', {}).get('inputs', {}).get('corpus', {})
    if not spec.get('path') or not spec.get('sha256'):
        return {}, 'Corpus fingerprint unavailable in this report.'
    path = Path(spec['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        return {}, 'Corpus is outside this project; evidence was not loaded.'
    try:
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != spec['sha256']:
            return {}, 'Corpus changed since this run; evidence was not loaded.'
        docs = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
        return {d['id']: d for d in docs}, 'Evidence verified against the saved corpus fingerprint.'
    except (OSError, ValueError, KeyError, TypeError):
        return {}, 'Corpus could not be loaded.'


def build_bundle(root=ROOT):
    root = Path(root).resolve()
    results = root / 'results'
    reports, audits, warnings = [], {}, []
    for path in sorted(results.rglob('audit.json')):
        if path.resolve().is_relative_to(root):
            try:
                audit = json.loads(path.read_text())
                if audit.get('review_type') == 'assistant_manual_source_audit':
                    audits[audit['original_report_sha256']] = audit
            except (OSError, ValueError, KeyError):
                warnings.append(f'Could not load audit: {path.relative_to(root)}')
    for path in sorted(results.rglob('report*.json')):
        if not path.resolve().is_relative_to(root) or any(p.startswith('.') for p in path.relative_to(root).parts):
            continue
        try:
            raw = path.read_bytes(); report = json.loads(raw)
            if not isinstance(report.get('cases'), list) or not isinstance(report.get('config'), dict):
                continue
            digest = hashlib.sha256(raw).hexdigest()
            evidence, status = _evidence(report, root)
            reports.append({'id': str(path.relative_to(root)), 'path': str(path.relative_to(root)),
                            'sha256': digest, 'report': report, 'evidence': evidence,
                            'evidence_status': status, 'audit': audits.get(digest)})
        except (OSError, ValueError, KeyError, TypeError):
            warnings.append(f'Could not load report: {path.relative_to(root)}')
    validation_path = results / 'judge-validation' / 'validation.json'
    try:
        validation = json.loads(validation_path.read_text())
    except (OSError, ValueError):
        validation = None
    return {'reports': reports, 'validation': validation, 'warnings': warnings}


def handler_for(root=ROOT):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/data':
                payload = json.dumps(build_bundle(root), allow_nan=False).encode()
                content_type = 'application/json; charset=utf-8'
            elif path in {'/', '/index.html', '/app.js', '/styles.css'}:
                name = 'index.html' if path == '/' else path[1:]
                payload = (ASSETS / name).read_bytes()
                content_type = {'html':'text/html', 'js':'text/javascript', 'css':'text/css'}[name.rsplit('.',1)[1]] + '; charset=utf-8'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(payload)
    return Handler


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port',type=int,default=8765)
    a=ap.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),handler_for())
    print(f'RAG report visualizer: http://127.0.0.1:{server.server_port}',flush=True)
    print('Reads saved reports only. Press Ctrl+C to stop.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
