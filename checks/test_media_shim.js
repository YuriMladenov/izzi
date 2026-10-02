// Run the actual injected script with controlled DOM fixtures and event timing.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const shim = fs.readFileSync(0, 'utf8');
function source(attrs = {}) {
  return {attrs: {...attrs}, getAttribute(k) {return this.attrs[k] ?? null;},
    setAttribute(k,v) {this.attrs[k] = v;}, removeAttribute(k) {delete this.attrs[k];}};
}
function media(tag, block, attrs, sources) {
  return Object.assign(source(attrs), {tagName: tag, sources, loads: 0,
    querySelectorAll() {return this.sources;}, load() {this.loads++;},
    closest() {return block ? {id: 'block-' + block, getAttribute() {return block;}} : null;}});
}
const audio = media('AUDIO', null, {}, [source()]);
const mapped = media('VIDEO', '123', {}, [source({type: 'text/html'})]);
const valid = media('VIDEO', '999', {}, [source({src: '/valid.mp4', type: 'video/mp4'})]);
const unknown = media('VIDEO', '456', {}, [source()]);
const nodes = [audio, mapped, valid, unknown];
const listeners = {};
let observer;
const document = {baseURI: 'http://127.0.0.1:8765/DOS/1408736/1408788.html',
  readyState: 'loading', documentElement: {}, querySelectorAll() {return nodes;},
  addEventListener(name, fn) {listeners[name] = fn;}};
vm.runInNewContext(shim, {document, window: {}, URL, console: {log() {}}, setTimeout() {},
  MutationObserver: class {constructor(fn) {observer = fn;} observe() {}}});
observer();
assert.equal(mapped.loads, 0, 'wait for parsing before choosing a source');
document.readyState = 'interactive';
listeners.DOMContentLoaded();
assert.equal(mapped.sources[0].getAttribute('src'), '/mapped.mp4', 'block ID selects mapping despite reversed list order');
assert.equal(mapped.sources[0].getAttribute('type'), 'video/mp4');
assert.equal(audio.sources[0].getAttribute('src'), null, 'never assign MP4 to global audio');
assert.equal(valid.sources[0].getAttribute('src'), '/valid.mp4');
assert.equal(valid.loads, 0, 'preserve valid source without reload');
assert.equal(unknown.sources[0].getAttribute('src'), null, 'no mapping from another block');
observer();
assert.equal(mapped.loads, 1, 'no repeated load or observer feedback loop');
mapped.setAttribute('src', '#');
mapped.sources[0].setAttribute('src', '1408788.html#');
observer();
assert.equal(mapped.getAttribute('src'), null);
assert.equal(mapped.sources[0].getAttribute('src'), '/mapped.mp4');
assert.equal(mapped.loads, 2, 'repair dynamically restored placeholder');
console.log('PASS: media shim runtime');
