# Web UI Module

## Scope

The Web UI module is a static single-page management console served by FastAPI. It provides task operations, subscription management, published subscription exports, proxy pool and chain configuration, gateway endpoint controls, backend route management, and proxy node filtering/actions.

## Key Files

- `proxypool/webui/index.html` contains the Vue template, Element Plus controls, page sections, and static asset imports.
- `proxypool/webui/js/app.js` contains Vue state, computed values, methods, API calls, task polling, local UI preferences, and mounted lifecycle loading.
- `proxypool/webui/css/main.css` contains the console styling.
- `proxypool/api/app.py` mounts `/static` and serves `index.html` at `/`.

## Implementation Notes

The UI uses CDN-loaded Vue 3, Element Plus, Tailwind, and local CSS/JS assets. `app.js` stores all page state in one Vue application object. Navigation is controlled by `activePage`, with main pages for task center, subscriptions, published subscriptions, multi-hop proxy pools, and proxy nodes.

Most actions call JSON API endpoints with `fetch()`. Long-running operations start task endpoints such as `/api/tasks/tester/start`, `/api/tasks/speed-test/start`, `/api/tasks/geoip/start`, `/api/tasks/ip-purity/start`, and `/api/tasks/subscriptions-refresh/start`; the UI then polls `/api/tasks?limit=80` for progress. Synchronous operations include proxy listing, subscription CRUD, published subscription CRUD, pool/gateway/backend configuration, and selected proxy deletion/copy actions.

The UI keeps some preferences in browser storage, including table columns, filters, route defaults, tester fallback configuration, task concurrency, and selected display options. It also uses a proxy-key datalist and serial map so users can refer to nodes by visible sequence numbers.

## Tests

Template and UI/API integration assumptions are covered by `tests/test_webui_template.py` and `tests/test_webui_tasks.py`.
