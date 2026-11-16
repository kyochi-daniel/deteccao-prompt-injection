import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { classify, tokenize } from '../space/inference.js';

const model = JSON.parse(await readFile(new URL('../space/model.json', import.meta.url)));
const fixtures = JSON.parse(await readFile(new URL('./parity-fixtures.json', import.meta.url)));
for (const fixture of fixtures) {
  const result = classify(fixture.text, model);
  assert.ok(Math.abs(result.probability - fixture.probability) < 1e-12, fixture.text);
  assert.ok(Math.abs(result.score - fixture.score) < 1e-12, fixture.text);
  assert.equal(result.label, fixture.label);
  assert.equal(result.knownTerms, fixture.knownTerms);
  assert.equal(result.tokenCount, fixture.tokenCount);
  assert.equal(result.knownTokens, fixture.knownTokens);
  assert.deepEqual(result.signals.map(({ term }) => term), fixture.signals.map(({ term }) => term));
  result.signals.forEach(({ contribution }, index) => {
    assert.ok(Math.abs(contribution - fixture.signals[index].contribution) < 1e-12, fixture.text);
  });
}
assert.deepEqual(tokenize('AÇÃO cafe\u0301 1 API_TOKEN'), ['acao', 'cafe', 'api_token']);
for (const text of [null, 2, '', '  ', 'a'.repeat(12001)]) assert.throws(() => classify(text, model));
assert.equal(classify('漢字 🙂', model).knownTerms, 0);
assert.ok(Number.isFinite(classify('constructor __proto__ toString', model).probability));
assert.doesNotThrow(() => classify('🙂'.repeat(12000), model));
assert.throws(() => classify('🙂'.repeat(12001), model));
console.log(`${fixtures.length} casos: paridade Python/JS < 1e-12; validação e Unicode passaram.`);
