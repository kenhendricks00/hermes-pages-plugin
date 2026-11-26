// Hermes Pages for Hermes Desktop: a "Pages" row in the left sidebar and a
// library page at /pages that lists the pages in a Hermes Pages workspace.
//
// Plain ESM, loaded uncompiled by the Desktop plugin loader. Imports only the
// plugin SDK and React. Files are read through ctx.files (a folder the user
// grants once); nothing is written, uploaded or fetched by this file.
import * as sdk from '@hermes/plugin-sdk'
import { useEffect, useMemo, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const {
  host, atom, useValue, useQuery, useQueryClient,
  Button, Badge, Codicon, EmptyState, Input, SearchField,
  ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA
} = sdk

const ID = 'hermes-pages'
const ROUTE = '/pages'
const KEY = [ID, 'library']
const RECENT_COUNT = 4
const MAX_INLINE_IMAGES = 24

// Disk plugins are not scanned by Tailwind, so the layout lives here. Theme
// variables only: every color follows the active Hermes theme.
const CSS = `
.hp-root{display:flex;flex-direction:column;height:100%;min-height:0;color:var(--ui-text-primary)}
.hp-head{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:18px 24px 10px}
.hp-title{display:flex;align-items:baseline;gap:8px;min-width:0;flex:1 1 auto}
.hp-title h1{margin:0;font-size:1.25rem;font-weight:600;letter-spacing:-.01em}
.hp-count{font-size:.75rem;color:var(--ui-text-tertiary);font-variant-numeric:tabular-nums}
.hp-actions{display:flex;align-items:center;gap:4px;flex:none}
.hp-search{padding:0 24px 8px;max-width:44rem}
.hp-settings{margin:0 24px 12px;padding:12px;border:1px solid var(--ui-stroke-secondary);border-radius:10px;display:grid;gap:10px;max-width:44rem}
.hp-settings-row{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.hp-settings-label{font-size:.75rem;color:var(--ui-text-secondary);min-width:7rem}
.hp-settings-value{font-size:.75rem;color:var(--ui-text-tertiary);overflow-wrap:anywhere;flex:1 1 12rem}
.hp-settings-input{flex:1 1 14rem;min-width:0}
.hp-body{flex:1 1 auto;min-height:0;overflow:auto;padding:4px 24px 32px}
.hp-group{margin:14px 0 8px;font-size:.75rem;font-weight:500;color:var(--ui-text-tertiary)}
.hp-group:first-child{margin-top:4px}
.hp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,15.5rem),1fr));gap:10px}
.hp-card{all:unset;box-sizing:border-box;display:flex;flex-direction:column;gap:6px;min-width:0;min-height:7.5rem;padding:14px;border-radius:12px;cursor:pointer;
  border:1px solid color-mix(in srgb,var(--ui-stroke-secondary) 70%,transparent);background:var(--ui-bg-quaternary);
  transition:background-color .12s ease,border-color .12s ease,transform .12s ease}
.hp-card:hover{background:var(--chrome-action-hover);border-color:var(--ui-stroke-secondary)}
.hp-card:active{transform:scale(.99)}
.hp-card:focus-visible{outline:2px solid var(--ui-accent);outline-offset:2px}
.hp-card-title{font-size:.875rem;font-weight:600;line-height:1.3;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow-wrap:anywhere}
.hp-card-summary{font-size:.75rem;line-height:1.45;color:var(--ui-text-tertiary);overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow-wrap:anywhere}
.hp-card-meta{margin-top:auto;display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;padding-top:4px}
.hp-date{font-size:.6875rem;color:var(--ui-text-tertiary);font-variant-numeric:tabular-nums;margin-right:2px}
.hp-empty{display:grid;justify-items:center;gap:12px;padding:48px 24px}
.hp-note{font-size:.75rem;color:var(--ui-text-tertiary);text-align:center;max-width:30rem;line-height:1.5}
.hp-error{font-size:.75rem;color:var(--ui-text-secondary);text-align:center;max-width:32rem;overflow-wrap:anywhere}
.hp-viewer{display:flex;flex-direction:column;height:100%;min-height:0}
.hp-bar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;padding:8px 12px;border-bottom:1px solid var(--ui-stroke-secondary)}
.hp-bar-title{flex:1 1 10rem;min-width:0;font-size:.8125rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hp-bar-actions{display:flex;flex-wrap:wrap;align-items:center;gap:4px}
.hp-seg{display:inline-flex;gap:2px;padding:2px;border-radius:6px;background:var(--ui-bg-quaternary)}
.hp-seg button{all:unset;cursor:pointer;font-size:.6875rem;padding:2px 8px;border-radius:4px;color:var(--ui-text-secondary)}
.hp-seg button[aria-pressed="true"]{background:var(--chrome-action-hover);color:var(--ui-text-primary)}
.hp-frame-wrap{flex:1 1 auto;min-height:0;position:relative}
.hp-frame{position:absolute;inset:0;width:100%;height:100%;border:0}
.hp-skel{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,15.5rem),1fr));gap:10px}
.hp-skel div{height:7.5rem;border-radius:12px;background:var(--ui-bg-quaternary);opacity:.6}
`

// ── plugin-scoped state (reset on unload) ───────────────────────────────────
let CTX = null
const $openSlug = atom(null)
const $settingsOpen = atom(false)

const storageGet = (k, d) => { try { return CTX ? CTX.storage.get(k, d) : d } catch { return d } }
const storageSet = (k, v) => { try { CTX && CTX.storage.set(k, v) } catch { /* storage unavailable */ } }

// ── data ─────────────────────────────────────────────────────────────────────
const SAFE_SLUG = /^[A-Za-z0-9][\w.-]{0,200}$/

function safeRelative(path) {
  if (typeof path !== 'string') return null
  const p = path.replace(/\\/g, '/').replace(/^\.\//, '')
  if (!p || p.startsWith('/') || /^[a-zA-Z]:/.test(p) || p.split('/').some(s => s === '..' || s === '')) return null
  return p
}

function asText(v, max = 400) {
  return typeof v === 'string' ? v.trim().slice(0, max) : ''
}

function parseDate(s) {
  if (!s) return null
  const t = Date.parse(s)
  return Number.isNaN(t) ? null : t
}

function normalize(raw) {
  const list = Array.isArray(raw) ? raw : Array.isArray(raw?.pages) ? raw.pages : []
  const out = []
  const seen = new Set()
  list.forEach((e, index) => {
    if (!e || typeof e !== 'object') return
    const slug = asText(e.slug, 200)
    if (!SAFE_SLUG.test(slug) || seen.has(slug)) return
    seen.add(slug)
    const date = asText(e.date, 40) || asText(e.created, 40)
    const tags = Array.isArray(e.tags) ? e.tags.filter(t => typeof t === 'string' && t.trim()).map(t => t.trim().slice(0, 40)).slice(0, 12) : []
    out.push({
      slug,
      title: asText(e.title, 300) || slug,
      summary: asText(e.summary, 600),
      date,
      time: parseDate(date),
      tags,
      path: safeRelative(e.path),
      index
    })
  })
  // Newest first; undated pages fall back to their position in the file
  // (later entries are newer), after every dated page.
  out.sort((a, b) => {
    if (a.time != null && b.time != null && a.time !== b.time) return b.time - a.time
    if ((a.time == null) !== (b.time == null)) return a.time == null ? 1 : -1
    return b.index - a.index
  })
  return out
}

async function currentFolder() {
  if (!CTX?.files) return { error: 'This Hermes Desktop build has no plugin file access. Update Hermes Desktop.' }
  const id = storageGet('folderId', null)
  if (!id) return { folder: null }
  const folders = await CTX.files.folders()
  const folder = (folders || []).find(f => f.id === id) || null
  return { folder }
}

// Supports both workspace layouts, read-only: the plugin's own
// (public/pages.json) and a site that keeps pages.json at its root.
async function loadLibrary() {
  const { folder, error } = await currentFolder()
  if (error) return { state: 'error', error }
  if (!folder) return { state: 'no-folder' }
  for (const root of ['public/', '']) {
    const res = await CTX.files.readText(folder.id, `${root}pages.json`)
    if (res?.ok) {
      let parsed
      try { parsed = JSON.parse(res.text) } catch { return { state: 'error', folder, error: `${root}pages.json is not valid JSON.` } }
      return { state: 'ok', folder, root, pages: normalize(parsed) }
    }
    if (res && res.error && res.error !== 'not-found') {
      if (res.error === 'not-granted' || res.error === 'folder-missing' || res.error === 'folder-changed') return { state: 'regrant', folder, error: res.message || res.error }
      return { state: 'error', folder, error: res.message || res.error }
    }
  }
  return { state: 'missing', folder }
}

async function resolvePageFile(lib, page) {
  const candidates = []
  if (page.path) candidates.push(page.path)
  candidates.push(`${lib.root}${page.slug}.html`, `${lib.root}pages/${page.slug}.html`)
  for (const rel of candidates) {
    const st = await CTX.files.stat(lib.folder.id, rel)
    if (st?.ok && st.exists && !st.isDirectory) return rel
  }
  return null
}

function webPath(lib, rel, page) {
  const p = rel || `${lib.root}${page.slug}.html`
  return lib.root && p.startsWith(lib.root) ? p.slice(lib.root.length) : p
}

function publishedUrl(lib, rel, page) {
  const base = asText(storageGet('baseUrl', ''), 500).replace(/\/+$/, '')
  if (!/^https:\/\/[^\s/]+/i.test(base)) return null
  return `${base}/${webPath(lib, rel, page).split('/').map(encodeURIComponent).join('/')}`
}

function joinRel(fromFile, href, root) {
  const clean = href.split(/[?#]/)[0]
  if (!clean || /^[a-z][\w+.-]*:/i.test(clean) || clean.startsWith('//')) return null
  const baseParts = clean.startsWith('/') ? root.split('/').filter(Boolean) : fromFile.split('/').slice(0, -1)
  const parts = [...baseParts]
  for (const seg of clean.replace(/^\/+/, '').split('/')) {
    if (seg === '' || seg === '.') continue
    if (seg === '..') { if (!parts.length) return null; parts.pop() } else parts.push(seg)
  }
  try { return safeRelative(decodeURIComponent(parts.join('/'))) } catch { return null }
}

const STYLESHEET_LINK = /<link\b[^>]*\brel=["']?stylesheet["']?[^>]*>/gi
const HREF_ATTR = /\bhref=["']([^"']+)["']/i
const IMG_SRC = /(<img\b[^>]*\bsrc=)(["'])([^"']+)\2/gi
const SCRIPT_BLOCK = /<script\b[\s\S]*?<\/script\s*>/gi
const SCRIPT_OPEN = /<script\b[^>]*\/?>/gi

// Builds a self-contained document for the in-app viewer: local stylesheets
// and images are inlined from the granted folder and scripts are dropped, so
// the page renders offline inside a sandboxed frame with an opaque origin.
async function buildLocalDocument(folderId, rel, root) {
  const res = await CTX.files.readText(folderId, rel)
  if (!res?.ok) throw new Error(res?.message || res?.error || 'Could not read the page file.')
  let html = res.text.replace(SCRIPT_BLOCK, '').replace(SCRIPT_OPEN, '')
  const links = html.match(STYLESHEET_LINK) || []
  for (const tag of links) {
    const href = (tag.match(HREF_ATTR) || [])[1]
    const target = href && joinRel(rel, href, root)
    if (!target) continue
    const css = await CTX.files.readText(folderId, target)
    if (css?.ok) html = html.replace(tag, () => `<style>${css.text.replace(/<\/style/gi, '<\\/style')}</style>`)
  }
  const images = [...html.matchAll(IMG_SRC)].slice(0, MAX_INLINE_IMAGES)
  for (const m of images) {
    const target = joinRel(rel, m[3], root)
    if (!target) continue
    const img = await CTX.files.readDataUrl(folderId, target)
    if (img?.ok && typeof img.url === 'string') html = html.replace(m[0], () => `${m[1]}${m[2]}${img.url}${m[2]}`)
  }
  // Static local reading only. This policy also blocks event handlers,
  // external images/styles, CSS fetches and document-initiated connections.
  const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; script-src 'none'; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">`
  html = /<head\b[^>]*>/i.test(html)
    ? html.replace(/<head\b[^>]*>/i, tag => tag + policy)
    : policy + html
  return toDataUrl(html)
}

function toDataUrl(html) {
  const bytes = new TextEncoder().encode(html)
  let bin = ''
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000))
  return `data:text/html;charset=utf-8;base64,${btoa(bin)}`
}

async function chooseFolder(queryClient) {
  if (!CTX?.files?.requestFolder) {
    host.notify({ kind: 'error', message: 'This Hermes Desktop build cannot grant folders to plugins.' })
    return
  }
  const picked = await CTX.files.requestFolder()
  if (!picked?.ok || !picked.folder) return
  storageSet('folderId', picked.folder.id)
  $openSlug.set(null)
  queryClient?.invalidateQueries({ queryKey: KEY })
}

function fmtDate(page) {
  if (page.time == null) return page.date || ''
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(page.date)
  const d = new Date(page.time)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', ...(dateOnly ? { timeZone: 'UTC' } : {}) })
}

function monthLabel(page) {
  if (page.time == null) return 'Undated'
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(page.date)
  return new Date(page.time).toLocaleDateString(undefined, { year: 'numeric', month: 'long', ...(dateOnly ? { timeZone: 'UTC' } : {}) })
}

function groupPages(pages) {
  const groups = []
  const recent = pages.slice(0, RECENT_COUNT)
  if (recent.length) groups.push({ label: 'Recent', pages: recent })
  let current = null
  for (const page of pages.slice(RECENT_COUNT)) {
    const label = monthLabel(page)
    if (!current || current.label !== label) { current = { label, pages: [] }; groups.push(current) }
    current.pages.push(page)
  }
  return groups
}

function matches(page, q) {
  if (!q) return true
  const hay = `${page.title}\n${page.summary}\n${page.tags.join('\n')}\n${page.slug}`.toLowerCase()
  return q.toLowerCase().split(/\s+/).filter(Boolean).every(term => hay.includes(term))
}

// ── components ──────────────────────────────────────────────────────────────
function useLibrary() {
  return useQuery({
    queryKey: KEY,
    queryFn: loadLibrary,
    staleTime: 30_000,
    refetchOnWindowFocus: true
  })
}

function IconButton({ icon, label, onClick, disabled }) {
  return jsxs(Button, {
    variant: 'ghost', size: 'sm', onClick, disabled, title: label, 'aria-label': label,
    children: [jsx(Codicon, { name: icon, size: '0.875rem' }), jsx('span', { children: label })]
  })
}

function PageCard({ page, onOpen }) {
  const tags = page.tags.slice(0, 3)
  const extra = page.tags.length - tags.length
  return jsxs('button', {
    type: 'button', className: 'hp-card', onClick: () => onOpen(page.slug),
    title: page.title,
    children: [
      jsx('div', { className: 'hp-card-title', children: page.title }),
      page.summary ? jsx('div', { className: 'hp-card-summary', children: page.summary }) : null,
      jsxs('div', {
        className: 'hp-card-meta',
        children: [
          page.date ? jsx('time', { className: 'hp-date', dateTime: page.date, children: fmtDate(page) }) : null,
          ...tags.map(t => jsx(Badge, { variant: 'muted', children: t }, t)),
          extra > 0 ? jsx(Badge, { variant: 'outline', children: `+${extra}` }, '+more') : null
        ]
      })
    ]
  })
}

function SettingsPanel({ lib }) {
  const queryClient = useQueryClient()
  const [base, setBase] = useState(() => storageGet('baseUrl', ''))
  const valid = !base || /^https:\/\/[^\s/]+/i.test(base.trim())
  const save = () => {
    if (!valid) return
    storageSet('baseUrl', base.trim().replace(/\/+$/, ''))
    host.notify({ kind: 'success', message: base.trim() ? 'Published site address saved.' : 'Published site address cleared.' })
    queryClient.invalidateQueries({ queryKey: [ID] })
  }
  return jsxs('div', {
    className: 'hp-settings',
    children: [
      jsxs('div', {
        className: 'hp-settings-row',
        children: [
          jsx('span', { className: 'hp-settings-label', children: 'Workspace folder' }),
          jsx('span', { className: 'hp-settings-value', children: lib?.folder ? lib.folder.path || lib.folder.name : 'None chosen' }),
          jsx(Button, { variant: 'outline', size: 'sm', onClick: () => chooseFolder(queryClient), children: lib?.folder ? 'Change' : 'Choose' })
        ]
      }),
      jsxs('div', {
        className: 'hp-settings-row',
        children: [
          jsx('span', { className: 'hp-settings-label', children: 'Published site' }),
          jsx(Input, {
            className: 'hp-settings-input', value: base, placeholder: 'https://my-pages.pages.dev',
            onChange: e => setBase(e.target.value), 'aria-invalid': !valid || undefined,
            onKeyDown: e => { if (e.key === 'Enter') save() }
          }),
          jsx(Button, { variant: 'secondary', size: 'sm', onClick: save, disabled: !valid, children: 'Save' })
        ]
      }),
      jsx('div', { className: 'hp-note', style: { textAlign: 'left', maxWidth: 'none' }, children: 'Optional. Used for "Open in browser" and the Published view. Pages are read from the folder above; nothing is uploaded from here.' })
    ]
  })
}

function FirstRun() {
  const queryClient = useQueryClient()
  return jsxs('div', {
    className: 'hp-empty',
    children: [
      jsx(EmptyState, {
        title: 'Choose your Hermes Pages workspace',
        description: 'Pick the folder that holds pages.json (or public/pages.json). Hermes only reads it.'
      }),
      jsx(Button, { onClick: () => chooseFolder(queryClient), children: 'Choose folder' })
    ]
  })
}

function Library() {
  const queryClient = useQueryClient()
  const { data: lib, isLoading, isFetching, refetch, error } = useLibrary()
  const settingsOpen = useValue($settingsOpen)
  const [query, setQuery] = useState('')
  const pages = lib?.state === 'ok' ? lib.pages : []
  const filtered = useMemo(() => pages.filter(p => matches(p, query.trim())), [pages, query])
  const open = slug => $openSlug.set(slug)

  let body
  if (isLoading) {
    body = jsx('div', { className: 'hp-skel', children: [0, 1, 2, 3, 4, 5].map(i => jsx('div', {}, i)) })
  } else if (error) {
    body = jsx('div', { className: 'hp-empty', children: jsx('div', { className: 'hp-error', children: String(error.message || error) }) })
  } else if (!lib || lib.state === 'no-folder') {
    body = jsx(FirstRun, {})
  } else if (lib.state === 'regrant') {
    body = jsxs('div', {
      className: 'hp-empty',
      children: [
        jsx(EmptyState, { title: 'Folder access needs a refresh', description: 'The workspace folder was moved, removed or its access was revoked.' }),
        jsx(Button, { onClick: () => chooseFolder(queryClient), children: 'Choose folder again' })
      ]
    })
  } else if (lib.state === 'missing') {
    body = jsxs('div', {
      className: 'hp-empty',
      children: [
        jsx(EmptyState, { title: 'No pages.json here', description: `${lib.folder.name} has neither public/pages.json nor pages.json. Render a page with Hermes Pages, or choose another folder.` }),
        jsx(Button, { variant: 'outline', onClick: () => chooseFolder(queryClient), children: 'Choose another folder' })
      ]
    })
  } else if (lib.state === 'error') {
    body = jsxs('div', {
      className: 'hp-empty',
      children: [
        jsx(EmptyState, { title: 'Could not read the library', description: lib.error }),
        jsx(Button, { variant: 'outline', onClick: () => refetch(), children: 'Try again' })
      ]
    })
  } else if (!pages.length) {
    body = jsx(EmptyState, { title: 'No pages yet', description: 'Ask Hermes to turn an answer into a page and it shows up here.' })
  } else if (!filtered.length) {
    body = jsx(EmptyState, { title: 'No matches', description: `Nothing matches "${query.trim()}".` })
  } else {
    const groups = query.trim() ? [{ label: `${filtered.length} result${filtered.length === 1 ? '' : 's'}`, pages: filtered }] : groupPages(filtered)
    body = groups.map(g => jsxs('section', {
      children: [
        jsx('h2', { className: 'hp-group', children: g.label }),
        jsx('div', { className: 'hp-grid', children: g.pages.map(p => jsx(PageCard, { page: p, onOpen: open }, p.slug)) })
      ]
    }, g.label))
  }

  return jsxs('div', {
    className: 'hp-root',
    children: [
      jsxs('header', {
        className: 'hp-head',
        children: [
          jsxs('div', {
            className: 'hp-title',
            children: [
              jsx('h1', { children: 'Pages' }),
              lib?.state === 'ok' ? jsx('span', { className: 'hp-count', children: `${pages.length} page${pages.length === 1 ? '' : 's'}` }) : null
            ]
          }),
          jsxs('div', {
            className: 'hp-actions',
            children: [
              jsx(IconButton, { icon: 'refresh', label: 'Refresh', onClick: () => refetch(), disabled: isFetching }),
              jsx(IconButton, { icon: 'settings-gear', label: 'Settings', onClick: () => $settingsOpen.set(!$settingsOpen.get()) })
            ]
          })
        ]
      }),
      settingsOpen ? jsx(SettingsPanel, { lib }) : null,
      lib?.state === 'ok' && pages.length
        ? jsx('div', { className: 'hp-search', children: jsx(SearchField, { value: query, onChange: setQuery, placeholder: 'Search titles, summaries and tags', 'aria-label': 'Search pages', variant: 'box' }) })
        : null,
      jsx('div', { className: 'hp-body', children: body })
    ]
  })
}

function Viewer({ slug }) {
  const { data: lib } = useLibrary()
  const page = lib?.state === 'ok' ? lib.pages.find(p => p.slug === slug) : null
  const fileQuery = useQuery({
    queryKey: [ID, 'file', lib?.folder?.id, lib?.root, slug, page?.path],
    queryFn: () => resolvePageFile(lib, page),
    enabled: !!page
  })
  const rel = fileQuery.data || null
  const url = page ? publishedUrl(lib, rel, page) : null
  const [mode, setMode] = useState(null)
  const effective = mode || (rel ? 'local' : url ? 'published' : 'local')
  const docQuery = useQuery({
    queryKey: [ID, 'doc', lib?.folder?.id, rel],
    queryFn: () => buildLocalDocument(lib.folder.id, rel, lib.root),
    enabled: !!rel && effective === 'local',
    staleTime: 15_000,
    refetchOnWindowFocus: true
  })

  useEffect(() => { setMode(null) }, [slug])

  if (!lib) return null
  if (!page) {
    return jsxs('div', { className: 'hp-empty', children: [jsx(EmptyState, { title: 'Page not found', description: 'It may have been removed from pages.json.' }), jsx(Button, { onClick: () => $openSlug.set(null), children: 'Back to Pages' })] })
  }

  const Frame = sdk.SandboxedFrame
  const absolute = rel && lib.folder.path ? `${lib.folder.path.replace(/[\\/]+$/, '')}/${rel}` : null
  const src = effective === 'published' ? url : docQuery.data

  let content
  if (!Frame) {
    content = jsx('div', { className: 'hp-empty', children: jsx('div', { className: 'hp-note', children: 'This Hermes Desktop build cannot show pages inline. Use "Open in browser".' }) })
  } else if (fileQuery.isLoading || (effective === 'local' && docQuery.isLoading)) {
    content = jsx('div', { className: 'hp-empty', children: jsx('div', { className: 'hp-note', children: 'Loading page...' }) })
  } else if (effective === 'local' && !rel) {
    content = jsx('div', { className: 'hp-empty', children: jsx(EmptyState, { title: 'Page file not found', description: url ? 'Switch to Published, or open it in your browser.' : `Looked for ${page.slug}.html in the workspace. Add a published site address in Settings to open the live page.` }) })
  } else if (effective === 'local' && docQuery.error) {
    content = jsx('div', { className: 'hp-empty', children: jsx('div', { className: 'hp-error', children: String(docQuery.error.message || docQuery.error) }) })
  } else if (src) {
    content = jsx(Frame, { className: 'hp-frame', src, title: page.title })
  }

  return jsxs('div', {
    className: 'hp-viewer',
    children: [
      jsxs('div', {
        className: 'hp-bar',
        children: [
          jsx(IconButton, { icon: 'arrow-left', label: 'Pages', onClick: () => $openSlug.set(null) }),
          jsx('div', { className: 'hp-bar-title', title: page.title, children: page.title }),
          jsxs('div', {
            className: 'hp-bar-actions',
            children: [
              rel && url
                ? jsxs('div', {
                    className: 'hp-seg', role: 'group', 'aria-label': 'Page source',
                    children: [
                      jsx('button', { type: 'button', 'aria-pressed': effective === 'local', onClick: () => setMode('local'), children: 'Local' }),
                      jsx('button', { type: 'button', 'aria-pressed': effective === 'published', onClick: () => setMode('published'), children: 'Published' })
                    ]
                  })
                : null,
              effective === 'local' && rel ? jsx(IconButton, { icon: 'refresh', label: 'Reload', onClick: () => docQuery.refetch() }) : null,
              url ? jsx(IconButton, { icon: 'link-external', label: 'Open in browser', onClick: () => CTX?.os.openExternal(url) }) : null,
              url ? jsx(IconButton, { icon: 'copy', label: 'Copy link', onClick: async () => { if (await CTX?.os.writeClipboard(url)) host.notify({ kind: 'success', message: 'Link copied.' }) } }) : null,
              absolute ? jsx(IconButton, { icon: 'folder-opened', label: 'Show file', onClick: async () => { if (!(await CTX?.os.revealPath(absolute))) host.notify({ kind: 'info', message: 'Could not reveal the file here.' }) } }) : null
            ]
          })
        ]
      }),
      jsx('div', { className: 'hp-frame-wrap', children: content })
    ]
  })
}

function DesktopSettings() {
  const { data: lib } = useLibrary()
  return jsxs('div', {
    className: 'hp-root', style: { height: 'auto', paddingTop: '12px' },
    children: [
      jsx('div', { style: { padding: '0 24px 16px' }, children: jsx(Button, {
        variant: 'secondary', onClick: () => { $openSlug.set(null); host.navigate(ROUTE) }, children: 'Open Pages'
      }) }),
      jsx(SettingsPanel, { lib })
    ]
  })
}

function PagesRoute() {
  const slug = useValue($openSlug)
  // Leaving the route returns to the library next time.
  useEffect(() => () => $openSlug.set(null), [])
  return slug ? jsx(Viewer, { slug }) : jsx(Library, {})
}

export default {
  id: ID,
  name: 'Hermes Pages',
  description: 'Your Hermes Pages library in the sidebar: browse, search and read pages from your workspace folder.',
  // No preview script capability. Unified-package copies are opt-in by the
  // host's package marker; a deliberate standalone copy uses the SDK default.
  capabilities: [],
  register(ctx) {
    CTX = ctx
    ctx.onDispose(() => { CTX = null; $openSlug.set(null); $settingsOpen.set(false) })

    const style = document.createElement('style')
    style.textContent = CSS
    document.head.append(style)
    ctx.onDispose(() => style.remove())
    ctx.registerSettingsPage?.({ id: 'settings', title: 'Hermes Pages', render: () => jsx(DesktopSettings, {}) })

    const openLibrary = () => { $openSlug.set(null); host.navigate(ROUTE) }

    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => jsx(PagesRoute, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, order: 60, data: { path: ROUTE, label: 'Pages', codicon: 'book' } },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: { id: 'hermesPages.open', label: 'Open Pages', keywords: ['pages', 'library', 'hermes pages', 'published'], run: openLibrary }
      },
      {
        id: 'choose-folder',
        area: PALETTE_AREA,
        data: {
          id: 'hermesPages.chooseFolder', label: 'Hermes Pages: Choose workspace folder', keywords: ['pages', 'folder', 'workspace'],
          run: async () => { openLibrary(); await chooseFolder(sdk.queryClient) }
        }
      }
    ])
    console.info('[hermes-pages] registered /pages route, Pages sidebar row and Open Pages command')
  }
}
