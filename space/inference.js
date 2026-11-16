// Inferência local do contrato JSON v1; não envia o texto para servidores.
export function tokenize(text) {
  return text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().match(/[a-z0-9_]{2,}/g) ?? [];
}

export function classify(text, model) {
  if (typeof text !== 'string' || !text.trim()) throw new Error('Informe um texto não vazio.');
  if (Array.from(text).length > 12000) throw new Error('O limite é 12000 caracteres.');
  if (model.schema_version !== 1) throw new Error('Versão de modelo não suportada.');
  const tokens = tokenize(text);
  const terms = [...tokens, ...tokens.slice(1).map((token, index) => `${tokens[index]} ${token}`)];
  const counts = new Map();
  for (const term of terms) counts.set(term, (counts.get(term) ?? 0) + 1);
  const features = [];
  for (const [term, count] of counts) {
    if (Object.hasOwn(model.vocabulary, term)) {
      const index = model.vocabulary[term];
      features.push({ term, index, value: (1 + Math.log(count)) * model.idf[index] });
    }
  }
  const norm = Math.sqrt(features.reduce((total, item) => total + item.value ** 2, 0)) || 1;
  const signals = features.map(({ term, index, value }) => ({ term, contribution: value / norm * model.coefficients[index] }));
  const score = model.intercept + signals.reduce((total, item) => total + item.contribution, 0);
  const probability = score >= 0 ? 1 / (1 + Math.exp(-score)) : Math.exp(score) / (1 + Math.exp(score));
  return {
    probability, score, label: probability >= model.threshold ? 'injecao' : 'benigno',
    signals: signals.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 10),
    knownTerms: features.length, tokenCount: tokens.length,
    knownTokens: tokens.filter(token => Object.hasOwn(model.vocabulary, token)).length,
  };
}
