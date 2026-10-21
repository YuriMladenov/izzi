"""Test replay HTML changes without real archive or browser sessions."""
import sys
from pathlib import Path
from unittest.mock import patch
import unittest
import re
import json
import shutil
import subprocess

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class ReplayHTML(unittest.TestCase):
    def render(self,text,media=None,path='/DOS/1408736/1408788.html'):
        with patch.object(server,'lesson_media',return_value=media or []):
            return server.inject_media_map(text.encode(),path).decode()

    @unittest.skipUnless(shutil.which('node'),'Node.js required for loader runtime test')
    def test_short_capture_loader(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_capture_loader.js'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_listen_button_pauses_and_resumes_resolved_audio_url(self):
        # Original alt-audio method: assigning src resets playback to zero.
        method='''function(){var t=this.altAudio;1==dosData.isExport&&(t=this.altAudio.substring(1)),this.$player.duration>0&&!this.$player.paused&&this.$player.src.indexOf(t)>-1?(this.$player.pause(),this.isPlaying=!1):this.$player.duration>0&&this.$player.paused&&this.$player.src.indexOf(t)>-1?(this.$player.play(),this.isPlaying=!0,Ct.$emit("pause-others",{active:this._uid})):(this.$player.src=this.altAudio,this.$player.play(),this.isPlaying=!0,Ct.$emit("pause-others",{active:this._uid}))}'''
        script='const component={name:"alt-audio",playerId:"global-audio-player",play:'+method+'};'
        rewritten=server.rewrite(script.encode(),html_document=False).decode()
        self.assertNotEqual(script,rewritten)
        self.assertEqual(rewritten,server.rewrite(rewritten.encode(),html_document=False).decode())
        if not shutil.which('node'):self.skipTest('Node required for audio toggle regression')
        harness=r'''
const assert=require('assert');
const document={baseURI:'http://127.0.0.1:8765/DOS/42888/42929.html'};
const dosData={isExport:false},Ct={$emit(){}};
REWRITTEN
let assignments=0;
const audio={paused:true,duration:0,currentTime:0,_src:'',
 get src(){return this._src},set src(value){this._src=new URL(value,document.baseURI).href;this.currentTime=0;assignments++},
 play(){this.paused=false},pause(){this.paused=true}};
const vm={$player:audio,altAudio:'./datastore/15/publication/42888/audio/песен.mp3?v=1',_uid:1};
component.play.call(vm);assert.equal(audio.paused,false);assert.equal(assignments,1);
audio.currentTime=7;
component.play.call(vm);assert.equal(audio.paused,true);assert.equal(audio.currentTime,7);assert.equal(vm.isPlaying,false);
component.play.call(vm);assert.equal(audio.paused,false);assert.equal(audio.currentTime,7);assert.equal(assignments,1);
// An absolute, already encoded alias still identifies the same song.
vm.altAudio=audio.src;audio.duration=30;component.play.call(vm);assert.equal(audio.paused,true);assert.equal(assignments,1);
vm.altAudio='./datastore/other.mp3';component.play.call(vm);assert.equal(assignments,2);assert.equal(audio.currentTime,0);assert.equal(audio.paused,false);
'''.replace('REWRITTEN',rewritten)
        result=subprocess.run(['node','-e',harness],capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_placeholder_removed_before_media_parsing(self):
        t=self.render('<html><head></head><body><video src="#"><source src="1408788.html#"></video></body></html>',
                      [{'url':'https://bg.izzi.digital/video.mp4','strict':True}])
        self.assertNotIn('src="#"',t)
        self.assertNotIn('src="1408788.html#"',t)
        self.assertLess(t.index('new MutationObserver'),t.index('<video'))
        self.assertIn('attributeFilter:["src"]',t)

    def test_preserves_valid_sources_and_unrelated_attributes(self):
        tag='<video data-src="#" poster="lesson.html"><source src="/real.mp4" type="video/mp4"></video>'
        self.assertIn(tag,self.render(tag))

    def test_no_mapping_never_invents_source(self):
        t=self.render('<video src="lesson.html?v=1#"><source src=\'#\'></video>')
        self.assertIn('<video><source></video>',t)
        self.assertIn('"media": []',t)

    def test_script_contents_untouched(self):
        script='<script>const t=\'<video src="#">\';</script>'
        self.assertIn(script,self.render(script))

    def test_attribute_value_containing_src_untouched(self):
        t=self.render('<video data-info=" example src=\'#\' " src="#"></video>')
        self.assertIn('<video data-info=" example src=\'#\' "></video>',t)
        self.assertIn('<video></video>',self.render('<video src></video>'))

    def test_nonlesson_unchanged(self):
        html='<video src="#"></video>'
        self.assertEqual(html,self.render(html,path='/index.html'))

    def test_export_reader_uses_local_content_without_archived_profile(self):
        data={'isExport':True,'bookshelfBase':'/','id':42917,'title':'</script>','isVisible':1}
        html='<head></head><script>var dosData = '+json.dumps(data)+';</script><main>Lesson</main>'
        rendered=self.render(html)
        match=re.search(r'var dosData\s*=\s*(.*?);</script>',rendered)
        parsed=json.loads(match[1])
        self.assertEqual({**data,'isExport':False},parsed)
        self.assertIn(r'\u003c/script>',match[1])
        self.assertIn("window.baseUrl='/'",rendered)
        self.assertIn('<main>Lesson</main>',rendered)
        self.assertIn('izzi-offline-user-name',rendered)

    def test_youtube_templates_in_javascript_remain_valid(self):
        template="'<youtube-player video-id=\"abcdefghijk\" title=\"Тест\"></youtube-player>'"
        script='const template='+template+';'
        self.assertEqual(script,server.rewrite(script.encode(),html_document=False).decode())
        inline='<script>'+script+'</script>'
        self.assertIn(inline,server.rewrite(('<head></head>'+inline).encode(),html_document=True).decode())
        bound='<youtube-player :video-id="fields.youtube.videoId" :video-url="fields.youtube.videoUrl"></youtube-player>'
        self.assertEqual(bound,server.rewrite(bound.encode(),html_document=True).decode())
        literal='<youtube-player video-url="https://www.youtube.com/watch?v=abcdefghijk"></youtube-player>'
        self.assertIn('data-youtube-id="abcdefghijk"',server.rewrite(literal.encode(),html_document=True).decode())

    @unittest.skipUnless(shutil.which('node'),'Node.js required for dynamic YouTube player runtime test')
    def test_dynamic_youtube_player(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_offline_youtube.js'))],
                              text=True,capture_output=True,timeout=10,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_corrects_mp4_source_type(self):
        t=self.render('<video><source type="text/html" src="/movie.mp4?v=1"></video>')
        self.assertIn('type="video/mp4"',t)

    def test_external_api_and_embed_stay_local(self):
        for u in ('https://www.youtube.com/iframe_api','//www.youtube.com/iframe_api',r'https:\/\/www.youtube.com\/iframe_api'):
            self.assertEqual('/__offline__/youtube-api.js',server.rewrite(u.encode()).decode())
        self.assertIn('/__offline__/external-media/abc',server.rewrite(b'<iframe src="https://www.youtube-nocookie.com/embed/abc"></iframe>').decode())
        self.assertEqual('/__offline__/youtube-api.js',server.rewrite(b'https://www.youtube.com/s/player/57bae81f/www-widgetapi.vflset/www-widgetapi.js').decode())

    def test_payload_safe_for_inline_script(self):
        t=self.render('<head></head><video></video>',[{'url':'https://bg.izzi.digital/video.mp4?x=</script>'}])
        self.assertIn(r'\u003c',t)
        self.assertEqual(1,t.count('</script>'))

    @unittest.skipUnless(shutil.which('node'),'Node.js required for media shim runtime test')
    def test_media_shim_runtime(self):
        t=self.render('<head></head>',[
            {'url':'https://bg.izzi.digital/valid.mp4','blocks':['999']},
            {'url':'https://bg.izzi.digital/mapped.mp4','blocks':['123']},
        ])
        shim=re.search(r'<script>(.*?)</script>',t,re.S).group(1)
        result=subprocess.run(['node',str(Path(__file__).with_name('test_media_shim.js'))],
                              input=shim,text=True,capture_output=True,timeout=10,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    @unittest.skipUnless(shutil.which('node'),'Node.js required for bookmarklet runtime test')
    def test_bookmarklet_selection(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_bookmarklet.js'))],
                              text=True,capture_output=True,timeout=10,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    @unittest.skipUnless(shutil.which('node'),'Node.js required for strict capture runtime test')
    def test_strict_capture_runtime(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_capture_strict.js'))],
                              text=True,capture_output=True,timeout=10,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    @unittest.skipUnless(shutil.which('node'),'Node.js required for bulk download runtime test')
    def test_missing_download_runtime(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_missing_download.js'))],
                              text=True,capture_output=True,timeout=10,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    @unittest.skipUnless(shutil.which('node'),'Node.js required for WebUI search runtime test')
    def test_webui_search_runtime(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_webui.js'))],
                              text=True,capture_output=True,timeout=10,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
