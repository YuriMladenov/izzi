"""Maintenance uses isolated Git repositories; never updates the user's checkout."""
import importlib.util,json,os,subprocess,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import project_maintenance as maintenance

class Updates(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.remote=self.base/'remote.git';self.source=self.base/'source';self.local=self.base/'local'
        self.run_git(self.base,'init','--bare',str(self.remote))
        self.run_git(self.base,'clone',str(self.remote),str(self.source))
        self.run_git(self.source,'checkout','-b','WebUI')
        self.run_git(self.source,'config','user.name','Maintenance test');self.run_git(self.source,'config','user.email','test@example.invalid')
        (self.source/'.gitignore').write_text('archive/\nstate/\ncaptures/\n')
        self.commit('server.py','print("old")\n')
        self.run_git(self.base,'clone','--branch','WebUI',str(self.remote),str(self.local))
        self.remote_patch=patch.object(maintenance,'REMOTE',str(self.remote));self.remote_patch.start()
    def tearDown(self):self.remote_patch.stop();self.tmp.cleanup()
    def run_git(self,root,*args):
        return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=True).stdout.strip()
    def commit(self,name,text):
        file=self.source/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text,encoding='utf8')
        self.run_git(self.source,'add','--',name,'.gitignore');self.run_git(self.source,'commit','-m','fixture')
        self.run_git(self.source,'push','origin','WebUI')
    def update(self):return maintenance.update(self.local,idle=lambda:None)
    def test_fast_forward_preserves_archive_and_reports_noop(self):
        data=self.local/'state';data.mkdir();(data/'private').write_text('unchanged')
        self.commit('server.py','print("new")\n');result=self.update()
        self.assertTrue(result['changed']);self.assertEqual('print("new")\n',(self.local/'server.py').read_text())
        self.assertEqual('unchanged',(data/'private').read_text());self.assertFalse(self.update()['changed'])
    def test_local_changes_and_untracked_files_block_update(self):
        self.commit('server.py','print("new")\n');(self.local/'personal.txt').write_text('mine')
        with self.assertRaisesRegex(ValueError,'локални промени'):self.update()
        (self.local/'personal.txt').unlink();(self.local/'server.py').write_text('my edit')
        with self.assertRaisesRegex(ValueError,'локални промени'):self.update()
    def test_changed_dependencies_and_invalid_python_do_not_change_head(self):
        before=self.run_git(self.local,'rev-parse','HEAD')
        self.commit('requirements-capture.txt','new-package\n')
        with self.assertRaisesRegex(ValueError,'зависимости'):self.update()
        self.assertEqual(before,self.run_git(self.local,'rev-parse','HEAD'))
    def test_invalid_python_blocks_application(self):
        self.commit('broken.py','def broken(:\n')
        with self.assertRaises(SyntaxError):self.update()
        self.assertFalse((self.local/'broken.py').exists())
    def test_unknown_remote_is_rejected_without_fetch(self):
        with patch.object(maintenance,'REMOTE','https://example.invalid/repo.git'):
            with self.assertRaisesRegex(ValueError,'GitHub'):self.update()
    def test_busy_guard_precedes_git_and_runs_again_before_apply(self):
        self.commit('server.py','print("new")\n')
        with self.assertRaisesRegex(ValueError,'busy'):
            maintenance.update(self.local,idle=lambda:(_ for _ in ()).throw(ValueError('busy')))
        calls=[]
        def guard():
            calls.append(1)
            if len(calls)==2:raise ValueError('busy')
        with self.assertRaisesRegex(ValueError,'busy'):maintenance.update(self.local,idle=guard)
        self.assertIn('old',(self.local/'server.py').read_text())
    def test_protected_upstream_paths_cannot_be_written(self):
        path=self.source/'state/private';path.parent.mkdir();path.write_text('upstream')
        self.run_git(self.source,'add','-f','state/private');self.run_git(self.source,'commit','-m','bad fixture');self.run_git(self.source,'push','origin','WebUI')
        with self.assertRaisesRegex(ValueError,'защитена'):self.update()
    def test_startup_script_password_stays_in_native_prompt(self):
        script=(maintenance.ROOT/'tools/register_startup.ps1').read_text()
        self.assertIn('Get-Credential',script);self.assertIn('-AtStartup',script)
        self.assertIn('-ExecutionTimeLimit ([TimeSpan]::Zero)',script)
        self.assertIn('SecurityIdentifier',script)
        self.assertEqual("'O''Brien'",maintenance.psquote("O'Brien"))

@unittest.skipIf(os.name=='nt','Container data links require Linux symlink semantics')
class ContainerSeed(unittest.TestCase):
    def test_code_and_data_survive_second_start(self):
        spec=importlib.util.spec_from_file_location('entrypoint',maintenance.ROOT/'docker/entrypoint.py');entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);seed=base/'image';seed.mkdir();(seed/'.git/info').mkdir(parents=True)
            (seed/'project_launcher.py').write_text('seed');(seed/'state').mkdir();(seed/'state/data').write_text('private')
            root=entry.prepare(seed,base/'volume');(root/'project_launcher.py').write_text('updated')
            self.assertEqual(root,entry.prepare(seed,base/'volume'))
            self.assertEqual('updated',(root/'project_launcher.py').read_text())
            self.assertEqual('private',(root/'state/data').read_text())

class Launcher(unittest.TestCase):
    def test_restart_starts_library_only_even_with_legacy_capture_settings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);shutil.copyfile(maintenance.ROOT/'project_launcher.py',root/'project_launcher.py')
            (root/'server.py').write_text("import os,sys\nfrom pathlib import Path\np=Path('runs')\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nassert os.environ['IZZI_MANAGED_LAUNCH']=='1'\nassert 'IZZI_START_CAPTURE' not in os.environ\nsys.exit(75 if n==1 else 0)\n")
            result=subprocess.run([sys.executable,str(root/'project_launcher.py'),'--capture'],cwd=root,capture_output=True,timeout=15,env={**os.environ,'IZZI_START_CAPTURE':'1'})
            self.assertEqual(0,result.returncode,result.stderr);self.assertEqual('2',(root/'runs').read_text())

if __name__=='__main__':unittest.main()
