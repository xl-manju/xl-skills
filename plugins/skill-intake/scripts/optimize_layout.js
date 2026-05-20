#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function parseEdges(src) {
  const edges = [];
  const re = /^\s*([A-Za-z0-9_]+)(?:\[[^\]]*\])?\s*-->\s*(?:\|[^|]*\|\s*)?([A-Za-z0-9_]+)/gm;
  let m;
  while ((m = re.exec(src))) edges.push([m[1], m[2]]);
  return edges;
}

function topoOrder(edges) {
  const nodes = new Set();
  const incoming = new Map();
  const outgoing = new Map();
  for (const [a, b] of edges) {
    nodes.add(a); nodes.add(b);
    incoming.set(b, (incoming.get(b) || 0) + 1);
    if (!outgoing.has(a)) outgoing.set(a, []);
    outgoing.get(a).push(b);
  }
  const order = [];
  const queue = [...nodes].filter((n) => !incoming.get(n));
  const inDeg = new Map([...nodes].map((n) => [n, incoming.get(n) || 0]));
  while (queue.length) {
    const n = queue.shift();
    order.push(n);
    for (const next of outgoing.get(n) || []) {
      inDeg.set(next, inDeg.get(next) - 1);
      if (inDeg.get(next) === 0) queue.push(next);
    }
  }
  return order.length === nodes.size ? order : [...nodes];
}

function optimize(src) {
  const edges = parseEdges(src);
  const order = topoOrder(edges);
  return { order, edge_count: edges.length, suggestion: order.join(' -> ') };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: optimize_layout.js <diagram.mmd>\n'); return 2; }
  let src;
  try { src = fs.readFileSync(path.resolve(file), 'utf8'); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = optimize(src);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return 0;
}

module.exports = { optimize, topoOrder };

if (require.main === module) {
  process.exit(main(process.argv));
}
