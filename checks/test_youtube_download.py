"""YouTube publication and failures without network or browser credentials."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import youtube_download as youtube

class YouTube(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.identifier='pJRmW-qSank';self.body=b'\x00\x00\x00\x18ftypmp42'+b'complete audio/video'*10
        self.patches=[patch.multiple(youtube,ARCHIVE_DIR=self.root/'archive',STATE_DIR=self.root/'state',JOBS={})]
        for item in self.patches:item.start()
        self.setup={'ejs':True,'runtimes':{'deno':{'supported':True,'path':'/fake/deno'},'node':{'supported':False,'path':None},'ffmpeg':{'supported':True,'path':'/fake/ffmpeg'}}}
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.tmp.cleanup()
    def sdk(self,fail=False):
        test=self
        class Client:
            def __init__(self,options):test.options=options
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def extract_info(self,url,download):
                test.assertEqual('https://www.youtube.com/watch?v='+test.identifier,url)
                test.assertTrue(download)
                output=Path(test.options['outtmpl'].replace('%(ext)s','mp4'))
                output.write_bytes(test.body)
                # The merger writes to staging; public replay must not see this
                # file until extraction/merge completes successfully.
                if not fail:test.assertFalse((youtube.ARCHIVE_DIR/'youtube'/(test.identifier+'.mp4')).exists())
                if fail:raise OSError('merger interrupted')
                return {'title':'Клип'}
        return SimpleNamespace(YoutubeDL=Client)
    def outcome(self):return json.loads((youtube.STATE_DIR/'youtube'/(self.identifier+'.json')).read_text(encoding='utf8'))
    def test_publish_complete_merge_and_reuse_without_another_worker(self):
        with patch.dict(sys.modules,{'yt_dlp':self.sdk()}),patch.object(youtube,'diagnose',return_value=self.setup):
            self.assertEqual(0,youtube.download(self.identifier))
        self.assertEqual(self.body,youtube.local_file(self.identifier).read_bytes())
        self.assertEqual('ready',self.outcome()['state'])
        self.assertIn('bestaudio',self.options['format'])
        self.assertEqual({'deno':{'path':'/fake/deno'}},self.options['js_runtimes'])
        self.assertEqual([self.identifier+'.mp4'],[p.name for p in (youtube.ARCHIVE_DIR/'youtube').iterdir()])
        with patch.object(youtube,'worker') as worker:
            self.assertTrue(youtube.status(self.identifier,start=True)['available']);worker.assert_not_called()
    def test_interrupted_merge_does_not_publish_partial_video_or_delete_existing(self):
        folder=youtube.ARCHIVE_DIR/'youtube';folder.mkdir(parents=True)
        prior=folder/(self.identifier+'.mp4');prior.write_bytes(self.body+b'old')
        with patch.dict(sys.modules,{'yt_dlp':self.sdk(fail=True)}),patch.object(youtube,'diagnose',return_value=self.setup):
            self.assertEqual(1,youtube.download(self.identifier))
        self.assertEqual(self.body+b'old',prior.read_bytes())
        self.assertEqual('failed',self.outcome()['state'])
        self.assertEqual([prior.name],[p.name for p in folder.iterdir()])
    def test_actionable_dependency_failures_survive_restart(self):
        for missing in ('ejs','runtime'):
            setup={**self.setup,'runtimes':{k:dict(v) for k,v in self.setup['runtimes'].items()}}
            if missing=='ejs':setup['ejs']=False
            else:setup['runtimes']['deno']['supported']=False
            with patch.dict(sys.modules,{'yt_dlp':self.sdk()}),patch.object(youtube,'diagnose',return_value=setup):
                self.assertEqual(1,youtube.download(self.identifier))
            status=youtube.status(self.identifier)
            self.assertEqual('failed',status['state']);self.assertIn('install_youtube.bat',status['error'])
            self.assertFalse(status['available'])
    def test_diagnostic_reports_supported_runtime_versions(self):
        versions={'deno':b'deno 2.4.1\n','node':b'v20.10.0\n','ffmpeg':b'ffmpeg version 7.1 Copyright\n'}
        def run(args,**kwargs):return SimpleNamespace(returncode=0,stdout=versions[args[0]])
        with patch.object(youtube.shutil,'which',side_effect=lambda name:name),patch.object(youtube.subprocess,'run',side_effect=run):
            info=youtube.diagnose()
        self.assertTrue(info['runtimes']['deno']['supported'])
        self.assertFalse(info['runtimes']['node']['supported'])
        self.assertTrue(info['runtimes']['ffmpeg']['supported'])
        self.assertEqual(sys.executable,info['python'])

if __name__=='__main__':unittest.main()
