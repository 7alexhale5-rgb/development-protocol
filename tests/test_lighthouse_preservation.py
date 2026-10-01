"""Public setup composition and preservation controls, without browser/network calls."""
import json
import subprocess
from unittest.mock import patch

from tests.test_audit_setup import Base, audit_kit, report


class LighthousePreservationTest(Base):
    def test_normal_run_rejects_invalid_existing_baseline(self):
        self.pkg(devDependencies={'lighthouse': '^13'}, scripts={})
        base = self.root / 'ops/lighthouse/baseline'
        base.mkdir(parents=True)
        saved = base / 'home.report.json'
        saved.write_text(json.dumps(report('https://example.test/', 0.9)))
        original = saved.read_bytes()
        with patch.object(audit_kit, 'require_node18'), patch.object(audit_kit, 'node_version', return_value=(22, 19)), patch.object(audit_kit, 'ensure_dev') as install:
            code, _ = self.quiet(audit_kit.run_all, self.root, only='lighthouse')
        self.assertEqual(code, 1)
        self.assertEqual(saved.read_bytes(), original)
        install.assert_not_called()

    def test_replacing_helpers_retains_prior_bytes(self):
        out = self.root / 'ops/lighthouse'
        out.mkdir(parents=True)
        prior = {'lh_baseline.py': b'# unique prior helper\n', 'run-baseline.sh': b'# unique prior rerun\n'}
        for name, payload in prior.items():
            (out / name).write_bytes(payload)
        audit_kit.write_baseline_files(self.root, 'https://example.test', '/', 3)
        for name, payload in prior.items():
            retained = [p for p in out.rglob(name) if p != out/name and p.read_bytes() == payload]
            self.assertTrue(retained, name)
        self.assertIn('.audit-setup-backup-*/', (out / '.gitignore').read_text())

    def test_ci_only_helper_backups_are_ignored(self):
        self.pkg(devDependencies={'@lhci/cli': '^0.14'}, scripts={})
        out = self.root / 'ops/lighthouse'
        base = out / 'baseline'
        base.mkdir(parents=True)
        (base / 'home.report.json').write_text(json.dumps(report('https://example.test/', 0.9)))
        old = b'# unique old CI helper\n'
        (out / 'lh_baseline.py').write_bytes(old)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        with patch.object(audit_kit, 'ensure_dev'):
            self.quiet(audit_kit.lighthouse_ci, self.root, force=True)
        copies = [p for p in out.rglob('lh_baseline.py') if p != out/'lh_baseline.py' and p.read_bytes() == old]
        self.assertEqual(len(copies), 1)
        proc = subprocess.run(['git', 'check-ignore', str(copies[0])], cwd=self.root, capture_output=True)
        self.assertEqual(proc.returncode, 0)
