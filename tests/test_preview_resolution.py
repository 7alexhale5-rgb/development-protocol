import os
import subprocess
import tempfile
import shutil
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'skills/audit-setup/references/lighthouse-ci.yml.tmpl'
HELPER = ROOT / 'skills/audit-setup/scripts/lh_baseline.py'
cases=[
 ('manual-valid','workflow_dispatch','https://preview-123.vercel.app','',True,'https://preview-123.vercel.app'),
 ('manual-slash','workflow_dispatch','https://preview-123.vercel.app/','',True,'https://preview-123.vercel.app'),
 ('deploy-select','deployment_status','https://bad.test','https://deploy-abc.vercel.app/',True,'https://deploy-abc.vercel.app'),
 ('manual-select','workflow_dispatch','https://manual-abc.vercel.app','https://bad.test',True,'https://manual-abc.vercel.app'),
 ('lookalike','workflow_dispatch','https://preview.vercel.app.evil.test','',False,None),
 ('newline-injection','workflow_dispatch','https://preview.vercel.app\npwn=1','',False,None),
 ('carriage-return','workflow_dispatch','https://preview.vercel.app\rpwn=1','',False,None),
 ('tab-control','workflow_dispatch','https://preview.vercel.app\tpwn=1','',False,None),
 ('userinfo','workflow_dispatch','https://user@preview.vercel.app','',False,None),
 ('empty-userinfo','workflow_dispatch','https://@preview.vercel.app','',False,None),
 ('query','workflow_dispatch','https://preview.vercel.app?x=1','',False,None),
 ('empty-query','workflow_dispatch','https://preview.vercel.app?','',False,None),
 ('fragment','workflow_dispatch','https://preview.vercel.app#x','',False,None),
 ('nonroot-path','workflow_dispatch','https://preview.vercel.app/login','',False,None),
 ('dot-path','workflow_dispatch','https://preview.vercel.app/./','',False,None),
 ('explicit-port','workflow_dispatch','https://preview.vercel.app:443','',False,None),
 ('http','workflow_dispatch','http://preview.vercel.app','',False,None),
 ('bare-host','workflow_dispatch','https://vercel.app','',False,None),
 ('wrong-host','workflow_dispatch','https://bad.test','',False,None),
 ('manual-uppercase','workflow_dispatch','HTTPS://PREVIEW-123.VERCEL.APP/','',True,'https://preview-123.vercel.app'),
 ('valid-multilevel','workflow_dispatch','https://branch.team.vercel.app','',True,'https://branch.team.vercel.app'),
 ('leading-hyphen','workflow_dispatch','https://-bad.vercel.app','',False,None),
 ('trailing-hyphen','workflow_dispatch','https://bad-.vercel.app','',False,None),
 ('overlong-label','workflow_dispatch','https://'+'a'*64+'.vercel.app','',False,None),
 ('trailing-host-dot','workflow_dispatch','https://preview.vercel.app.','',False,None),
 ('missing','workflow_dispatch','','',False,None),
 ('empty-fragment','workflow_dispatch','https://preview.vercel.app#','',False,None),
 ('empty-label','workflow_dispatch','https://bad..vercel.app','',False,None),
]

class PreviewURLTests(unittest.TestCase):
    def test_actual_workflow_url_block(self):
        lines = TEMPLATE.read_text().splitlines()
        start = lines.index('      - name: Resolve preview URL')
        run = next(i for i in range(start + 1, len(lines)) if lines[i] == '        run: |')
        end = next(i for i in range(run + 1, len(lines)) if lines[i].startswith('      - name: '))
        body = '\n'.join(line[10:] for line in lines[run + 1:end]) + '\n'
        self.assertNotIn('{{', body)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            helper = root / 'ops/lighthouse/lh_baseline.py'
            helper.parent.mkdir(parents=True)
            shutil.copy2(HELPER, helper)
            for label, event, dispatch, deploy, valid, expected in cases:
                with self.subTest(case=label):
                    output = root / (label + '.out')
                    env = dict(os.environ, DISPATCH_URL=dispatch, DEPLOY_URL=deploy,
                               EVENT_NAME=event, GITHUB_OUTPUT=str(output),
                               ALLOWED_HOSTS_JSON=json.dumps(['*.vercel.app']))
                    proc = subprocess.run(['bash', '-e', '-c', body], env=env, cwd=root,
                                          capture_output=True, text=True, timeout=5)
                    contents = output.read_text() if output.exists() else ''
                    self.assertEqual(proc.returncode == 0, valid, proc.stderr)
                    self.assertEqual(contents, f'url={expected}\n' if valid else '')


if __name__ == '__main__':
    unittest.main()
