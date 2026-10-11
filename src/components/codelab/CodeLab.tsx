import { useEffect, useRef, useState } from 'react';
import '../lab/lab.css';
import './codelab.css';
import type { CodeLabDef } from '../../lib/codelabs';
import { AGENTKIT } from '../../lib/agentkit';

interface Props { lab: CodeLabDef; lessonSlug: string; lessonTitle: string; nextUrl?: string; nextTitle?: string; base: string; children?: React.ReactNode }

const PYODIDE_VERSION = '0.27.2';
// Pyodide is served from this site (scripts/copy-pyodide.mjs copies it into public/pyodide/ on npm install),
// so code labs work offline. jsDelivr is only a fallback for copies built without it.
// PUBLIC_PYODIDE_URL overrides the location (tests use it).
const BASE_URL = import.meta.env.BASE_URL.replace(/\/?$/, '/');
const PYODIDE_URLS: string[] = import.meta.env.PUBLIC_PYODIDE_URL
  ? [import.meta.env.PUBLIC_PYODIDE_URL]
  : [`${BASE_URL}pyodide/`, `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`];

declare global {
  interface Window { loadPyodide?: (opts: { indexURL: string }) => Promise<any>; __fahPyodide?: Promise<any> }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => { s.remove(); reject(new Error(src)); };
    document.head.appendChild(s);
  });
}

async function loadPyodideFromFirstAvailable(): Promise<any> {
  for (const url of PYODIDE_URLS) {
    try { await loadScript(`${url}pyodide.js`); } catch { continue; }
    return window.loadPyodide!({ indexURL: url });
  }
  throw new Error('Could not load Python (Pyodide). Run `npm install` to copy it into public/pyodide/, or check your connection.');
}

function getPyodide(): Promise<any> {
  if (window.__fahPyodide) return window.__fahPyodide;
  window.__fahPyodide = loadPyodideFromFirstAvailable().then((py) => {
    py.FS.mkdirTree('/home/pyodide/agentkit_mini');
    for (const [path, src] of Object.entries(AGENTKIT)) {
      py.FS.writeFile(`/home/pyodide/agentkit_mini/${path.split('/').pop()}`, src);
    }
    py.runPython('import sys; sys.path.insert(0, "/home/pyodide")');
    return py;
  });
  window.__fahPyodide.catch(() => { window.__fahPyodide = undefined; });
  return window.__fahPyodide;
}

const RUNNER = `
import sys, io, json, traceback, os
_results = []
def check(label, cond, hint=""):
    _results.append({"label": label, "ok": bool(cond), "hint": hint})
def _run(code, check_code, real, key):
    os.environ["FAH_REAL_MODEL"] = "1" if real else "0"
    if key: os.environ["ANTHROPIC_API_KEY"] = key
    for m in [m for m in sys.modules if m.startswith("agentkit_mini")]:
        del sys.modules[m]
    _results.clear()
    ns = {"__name__": "__main__", "check": check}
    out = io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = out
    err = None
    try:
        exec(compile(code, "lab.py", "exec"), ns)
        if check_code:
            exec(compile(check_code, "check.py", "exec"), ns)
    except Exception:
        err = traceback.format_exc(limit=4)
    finally:
        sys.stdout, sys.stderr = old
    return json.dumps({"out": out.getvalue(), "err": err, "checks": list(_results)})
`;

function store(kind: 'local' | 'session', key: string, value?: string | null) {
  try {
    const s = kind === 'local' ? localStorage : sessionStorage;
    if (value === undefined) return s.getItem(key);
    if (value === null) s.removeItem(key); else s.setItem(key, value);
  } catch { /* storage may be unavailable */ }
  return null;
}

export default function CodeLab({ lab, lessonSlug, lessonTitle, nextUrl, nextTitle, base, children }: Props) {
  const codeKey = `fah-code-${lab.id}`;
  const [code, setCode] = useState<string>(() => store('local', codeKey) ?? lab.starter);
  const [status, setStatus] = useState<'idle' | 'loading' | 'running'>('idle');
  const [output, setOutput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [checks, setChecks] = useState<{ label: string; ok: boolean; hint: string }[] | null>(null);
  const [real, setReal] = useState(false);
  const [key, setKey] = useState<string>(() => store('session', 'fah-anthropic-key') ?? '');
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { store('local', codeKey, code); }, [code, codeKey]);
  // Figures in the instructions play their entrance animation when they scroll into view.
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('play'); io.unobserve(e.target); } }), { threshold: 0.3 });
    document.querySelectorAll('.cl-instructions figure.diagram').forEach((f) => io.observe(f));
    return () => io.disconnect();
  }, []);
  useEffect(() => { store('session', 'fah-anthropic-key', key || null); }, [key]);

  const exec = async (withCheck: boolean) => {
    setStatus('loading'); setError(null);
    try {
      const py = await getPyodide();
      setStatus('running');
      await new Promise((r) => setTimeout(r, 10));
      py.runPython(RUNNER);
      const res = JSON.parse(py.globals.get('_run')(code, withCheck ? lab.check : '', real, real ? key : ''));
      setOutput(res.out);
      setError(res.err);
      setChecks(withCheck ? res.checks : null);
      if (withCheck && !res.err && res.checks.length && res.checks.every((c: any) => c.ok)) {
        try {
          const p = JSON.parse(localStorage.getItem('fah-progress') || '{}') || {};
          p[lessonSlug] = p[lessonSlug] || Date.now();
          localStorage.setItem('fah-progress', JSON.stringify(p));
        } catch { /* ignore */ }
      }
    } catch (e: any) {
      setError(String(e?.message ?? e));
    } finally {
      setStatus('idle');
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault();
      const ta = e.currentTarget;
      const { selectionStart: s, selectionEnd: en } = ta;
      const next = code.slice(0, s) + '    ' + code.slice(en);
      setCode(next);
      requestAnimationFrame(() => { ta.selectionStart = ta.selectionEnd = s + 4; });
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); exec(false); }
  };

  const passed = checks && !error && checks.length > 0 && checks.every((c) => c.ok);
  const busy = status !== 'idle';

  return (
    <div className="lab codelab">
      <header className="lab-head">
        <a href={`${base}/c/${lessonSlug}/`} className="back">← {lessonTitle} lesson</a>
        <h1>Build: {lab.title}</h1>
      </header>
      {passed && (
        <div className="passed" role="status">
          <div><strong>All checks pass.</strong> Nice work.</div>
          {nextUrl && <a className="btn small" href={nextUrl}>Next: {nextTitle} →</a>}
        </div>
      )}
      <div className="cl-grid">
        {lab.html
          ? <section className="cl-instructions prose" dangerouslySetInnerHTML={{ __html: lab.html }} />
          : <section className="cl-instructions prose">{children}</section>}
        <section className="cl-work">
          <div className="cl-editor">
            <div className="cl-bar">
              <span className="dots" aria-hidden="true"><i /><i /><i /></span>
              <span className="file">lab.py</span>
              <button type="button" className="linkish" onClick={() => { if (confirm('Replace your code with the starter?')) setCode(lab.starter); }}>Reset</button>
              <button type="button" className="linkish" onClick={() => { if (confirm('Load the reference solution? Try it yourself first.')) setCode(lab.solution); }}>Show solution</button>
            </div>
            <textarea ref={taRef} value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={onKeyDown}
              spellCheck={false} aria-label="Python code editor" rows={Math.max(18, code.split('\n').length + 2)} />
          </div>
          <div className="runbar">
            <button type="button" className="btn" onClick={() => exec(false)} disabled={busy}>{status === 'loading' ? 'Loading Python…' : status === 'running' ? 'Running…' : '▶ Run'}</button>
            <button type="button" className="btn ghost" onClick={() => exec(true)} disabled={busy}>✓ Check</button>
            {lab.realModel && (
              <label className="real-toggle">
                <input type="checkbox" checked={real} onChange={(e) => setReal(e.target.checked)} /> Use a real model
              </label>
            )}
          </div>
          {real && (
            <div className="callout warn keybox">
              <span className="label">Your API key</span>
              <input type="password" placeholder="sk-ant-..." value={key} onChange={(e) => setKey(e.target.value)} aria-label="Anthropic API key" autoComplete="off" />
              <p>Kept in this tab's sessionStorage only and sent straight from your browser to api.anthropic.com. It never touches this site. Real calls cost money; checks are written for the mock model and may not all pass with a real one.</p>
            </div>
          )}
          {status === 'loading' && <p className="cl-note">First run downloads Python (about 10 MB). Later runs are instant.</p>}
          {(output || error) && (
            <pre className="cl-output" aria-live="polite">{output}{error && <span className="err">{error}</span>}</pre>
          )}
          {checks && (
            <ul className="cl-checks">
              {checks.map((c, i) => <li key={i} className={c.ok ? 'ok' : 'no'}><span aria-hidden="true">{c.ok ? '✓' : '✗'}</span> {c.label}{!c.ok && c.hint && <small> · {c.hint}</small>}</li>)}
              {checks.length === 0 && !error && <li className="no">No checks ran.</li>}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
