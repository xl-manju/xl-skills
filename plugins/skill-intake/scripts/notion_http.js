#!/usr/bin/env node
// notion_http.js — Notion REST API v1 への薄い wrapper。
// Notion-Version / Authorization を1箇所に閉じ込め、403/404 を意味付きエラーに変換する。

'use strict';

const { getSecret } = require('./keychain_get_secret');

const NOTION_VERSION = '2022-06-28';
const BASE = 'https://api.notion.com/v1';

async function notionFetch(path, { method = 'GET', body, token } = {}) {
  const t = token || getSecret();
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Authorization': `Bearer ${t}`,
      'Notion-Version': NOTION_VERSION,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json;
  try { json = text ? JSON.parse(text) : {}; } catch { json = { raw: text }; }
  if (!res.ok) {
    const err = new Error(
      `Notion ${method} ${path} -> HTTP ${res.status} ${json.code || ''} ${json.message || ''}`.trim()
    );
    err.status = res.status;
    err.body = json;
    throw err;
  }
  return json;
}

async function getDatabase(databaseId, opts) {
  return notionFetch(`/databases/${databaseId}`, opts);
}

async function getMe(opts) {
  return notionFetch('/users/me', opts);
}

module.exports = { notionFetch, getDatabase, getMe, NOTION_VERSION, BASE };
