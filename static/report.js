/* Human-readable report renderer for scan results.
   Turns the JSON payload into an overall verdict, per-section panels and
   a collapsible raw dump. All data is preserved; this is presentation only. */
(function () {
  'use strict';

  const KNOWN_SECTIONS = {
    dns_records: 'DNS records',
    dns_security: 'DNS security',
    spf: 'SPF, DKIM and DMARC',
    email_security: 'Email security',
    security_headers: 'Security headers',
    server_headers: 'Server headers',
    http: 'HTTP',
    tls: 'TLS certificate',
    certificate: 'Certificate',
    technology: 'Technology fingerprint',
    technology_fingerprint: 'Technology fingerprint',
    tech_fingerprint: 'Technology fingerprint',
    certificate_transparency: 'Certificate transparency',
    crtsh: 'Certificate transparency',
    subdomains: 'Subdomains',
    notes: 'Notes',
    findings: 'Findings',
    coverage: 'Coverage',
    deep_scan_sections: 'Deep scan',
    sections: 'Detailed sections',
    resolved_addresses: 'Resolved addresses'
  };

  const POSITIVE_KEYS = ['present', 'supported', 'enabled', 'secure', 'valid', 'resolves', 'found'];
  const NEGATIVE_KEYS = ['missing', 'unavailable', 'error', 'failed', 'leaked', 'exposed', 'insecure'];
  const COUNT_KEYS = ['score', 'count', 'total', 'checked', 'potential_duplicates', 'lookalike_candidates_checked', 'unique_signatures'];
  const MAX_VALUE_CHARS = 180;
  const MAX_ROWS = 60;
  const MAX_LIST_ITEMS = 12;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function titleCase(key) {
    return String(key)
      .replace(/[_-]+/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .trim()
      .replace(/\w\S*/g, function (w) { return w.charAt(0).toUpperCase() + w.slice(1); });
  }

  function isPlainObject(v) {
    return v != null && typeof v === 'object' && !Array.isArray(v);
  }

  function isEmpty(v) {
    if (v == null || v === '') return true;
    if (Array.isArray(v)) return v.length === 0;
    if (isPlainObject(v)) return Object.keys(v).length === 0;
    return false;
  }

  /* Small helper that classifies a row as ok / warning / fail / info. */
  function classify(key, value) {
    const k = String(key || '').toLowerCase();
    if (typeof value === 'boolean') return value ? 'ok' : 'warning';
    if (typeof value === 'number') return Number.isFinite(value) && value > 0 ? 'ok' : 'info';
    if (value == null || value === '') return 'warning';
    const text = String(value).toLowerCase();
    for (const n of NEGATIVE_KEYS) if (k.indexOf(n) !== -1) return 'fail';
    for (const p of POSITIVE_KEYS) if (k.indexOf(p) !== -1) {
      return /(^(no|not|missing|unavailable|failed|absent|none)\b|\bnot found\b)/.test(text) ? 'warning' : 'ok';
    }
    if (/\b(failed|unavailable|error|missing|leaked|exposed|insecure|timeout)\b/.test(text)) return 'fail';
    if (/\b(present|found|verified|enabled|supported|ok|pass|good|secure)\b/.test(text)) return 'ok';
    return 'info';
  }

  function summarizeValue(v) {
    if (v == null) return 'Not present';
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    if (typeof v === 'string') {
      const t = v.trim();
      return t.length > MAX_VALUE_CHARS ? t.slice(0, MAX_VALUE_CHARS) + '…' : (t || 'Not present');
    }
    if (typeof v === 'number') return String(v);
    if (Array.isArray(v)) {
      const items = v.slice(0, MAX_LIST_ITEMS).map(function (x) {
        return isPlainObject(x) || Array.isArray(x) ? JSON.stringify(x) : String(x);
      });
      let out = items.join(', ');
      if (v.length > MAX_LIST_ITEMS) out += '  (+' + (v.length - MAX_LIST_ITEMS) + ' more)';
      return out;
    }
    if (isPlainObject(v)) {
      const keys = Object.keys(v);
      if (keys.length === 0) return 'Not present';
      if (Object.prototype.hasOwnProperty.call(v, 'value') || Object.prototype.hasOwnProperty.call(v, 'present')) {
        const parts = [];
        if (v.present === true) parts.push('Present');
        else if (v.present === false) parts.push('Missing');
        if (v.value != null && v.value !== '') parts.push(summarizeValue(v.value));
        return parts.join(' — ') || 'Not present';
      }
      return keys.slice(0, 6).map(function (kk) { return titleCase(kk); }).join(', ') +
        (keys.length > 6 ? ' (+' + (keys.length - 6) + ' more)' : '');
    }
    return String(v);
  }

  function rowsFromObject(obj, depth, out) {
    if (out.length >= MAX_ROWS) return;
    const keys = Object.keys(obj);
    for (const key of keys) {
      if (out.length >= MAX_ROWS) break;
      const value = obj[key];
      if (isEmpty(value)) {
        out.push({ label: titleCase(key), value: 'Not present', level: 'warning' });
      } else if (isPlainObject(value) && !(Object.prototype.hasOwnProperty.call(value, 'value') || Object.prototype.hasOwnProperty.call(value, 'present')) && depth === 0) {
        const sub = [];
        rowsFromObject(value, depth + 1, sub);
        if (sub.length && sub.length <= 8) {
          for (const row of sub) out.push({ label: titleCase(key) + ': ' + row.label, value: row.value, level: row.level });
        } else {
          out.push({ label: titleCase(key), value: summarizeValue(value), level: classify(key, value) });
        }
      } else {
        out.push({ label: titleCase(key), value: summarizeValue(value), level: classify(key, value) });
      }
    }
  }

  /* Split a payload into readable sections: named sections first, then the
     remaining top-level fields grouped under "Overview". */
  function splitSections(data) {
    const sections = [];
    const leftover = {};
    if (!isPlainObject(data)) return [{ name: 'Result', rows: [{ label: 'Value', value: summarizeValue(data), level: 'info' }] }];
    const keys = Object.keys(data);
    for (const key of keys) {
      const value = data[key];
      if (isEmpty(value)) continue;
      const name = KNOWN_SECTIONS[key] || KNOWN_SECTIONS[key.toLowerCase()];
      if (name) {
        sections.push({ name, rawKey: key, value });
      } else {
        leftover[key] = value;
      }
    }
    if (Object.keys(leftover).length) sections.unshift({ name: 'Overview', rawKey: null, value: leftover });
    if (sections.length === 0 && keys.length) sections.push({ name: 'Overview', rawKey: null, value: data });
    return sections;
  }

  function sectionRows(sec) {
    const rows = [];
    const value = sec.value;
    if (Array.isArray(value)) {
      value.slice(0, MAX_LIST_ITEMS).forEach(function (item, i) {
        if (isPlainObject(item) && (item.feature || item.title || item.name)) {
          const title = item.feature || item.title || item.name;
          const detail = item.detail || item.value || item.note || item.description || '';
          rows.push({
            label: String(title),
            value: summarizeValue(detail) || 'Not present',
            level: (item.status || item.severity || '').toString().toLowerCase() === 'fail' ? 'fail'
              : ((item.status || item.severity || '').toString().toLowerCase() === 'warning' || (item.status || item.severity || '').toString().toLowerCase() === 'low' ? 'warning' : 'ok')
          });
        } else if (isPlainObject(item)) {
          Object.keys(item).slice(0, 4).forEach(function (kk) {
            rows.push({ label: titleCase(kk), value: summarizeValue(item[kk]), level: classify(kk, item[kk]) });
          });
        } else {
          rows.push({ label: titleCase(sec.name) + ' ' + (i + 1), value: summarizeValue(item), level: classify(sec.name, item) });
        }
      });
      if (value.length > MAX_LIST_ITEMS) rows.push({ label: 'More items', value: (value.length - MAX_LIST_ITEMS) + ' additional entries in raw data', level: 'info' });
      return rows;
    }
    if (isPlainObject(value)) {
      if (value.note && Object.keys(value).length <= 3) {
        rows.push({ label: 'Note', value: summarizeValue(value.note), level: 'info' });
      }
      rowsFromObject(value, 0, rows);
      return rows;
    }
    rows.push({ label: titleCase(sec.rawKey || 'Value'), value: summarizeValue(value), level: classify(sec.rawKey, value) });
    return rows;
  }

  function computeVerdict(sections) {
    const counts = { ok: 0, warning: 0, fail: 0, info: 0 };
    const all = [];
    sections.forEach(function (sec) {
      const rows = sectionRows(sec);
      sec.rows = rows;
      rows.forEach(function (r) { counts[r.level] = (counts[r.level] || 0) + 1; all.push({ sec: sec.name, row: r }); });
    });
    let status = 'info';
    let headline = 'Result ready';
    if (counts.fail > 0) { status = 'fail'; headline = counts.fail + (counts.fail === 1 ? ' issue needs' : ' issues need') + ' attention'; }
    else if (counts.warning > 0) { status = 'warning'; headline = counts.warning + (counts.warning === 1 ? ' point to' : ' points to') + ' watch'; }
    else if (counts.ok > 0) { status = 'ok'; headline = 'No issues found'; }
    const notable = all.filter(function (x) { return x.row.level === 'fail' || x.row.level === 'warning'; }).slice(0, 6);
    return { status, headline, counts, notable, totalRows: all.length };
  }

  function badgesHTML(counts) {
    const parts = [];
    if (counts.ok) parts.push('<span class="sev sev-ok">' + counts.ok + ' OK</span>');
    if (counts.warning) parts.push('<span class="sev sev-warning">' + counts.warning + ' Warning</span>');
    if (counts.fail) parts.push('<span class="sev sev-fail">' + counts.fail + ' Fail</span>');
    if (counts.info) parts.push('<span class="sev sev-info">' + counts.info + ' Info</span>');
    return parts.join(' ');
  }

  function renderHTML(data, rawText) {
    const sections = splitSections(data);
    const verdict = computeVerdict(sections);
    const label = verdict.status === 'ok' ? 'All clear' : verdict.status === 'warning' ? 'Needs review' : verdict.status === 'fail' ? 'Action needed' : 'Result';
    let html = '';
    html += '<div class="report-verdict sev-' + verdict.status + '">';
    html += '<span class="sev sev-' + verdict.status + '">' + esc(label) + '</span>';
    html += '<div class="report-verdict-copy"><strong>' + esc(verdict.headline) + '</strong>';
    html += '<span class="muted">' + verdict.totalRows + (verdict.totalRows === 1 ? ' check' : ' checks') + ' across ' + sections.length + (sections.length === 1 ? ' section' : ' sections') + '</span></div>';
    html += '<div class="report-verdict-badges">' + badgesHTML(verdict.counts) + '</div>';
    html += '</div>';

    if (verdict.notable.length) {
      html += '<div class="report-attention"><h3>Needs attention</h3><ul>';
      verdict.notable.forEach(function (x) {
        html += '<li><span class="sev sev-' + x.row.level + '">' + esc(x.row.level) + '</span> <strong>' + esc(x.row.label) + '</strong><span class="muted">' + esc(x.row.value) + '</span></li>';
      });
      html += '</ul></div>';
    }

    sections.forEach(function (sec) {
      if (!sec.rows || !sec.rows.length) return;
      html += '<div class="report-section"><div class="report-section-head"><h3>' + esc(sec.name) + '</h3><span class="muted">' + sec.rows.length + (sec.rows.length === 1 ? ' row' : ' rows') + '</span></div>';
      html += '<div class="report-rows">';
      sec.rows.forEach(function (row) {
        html += '<div class="report-row"><span class="report-row-label">' + esc(row.label) + '</span>' +
          '<span class="report-row-value">' + esc(row.value) + '</span>' +
          '<span class="sev sev-' + row.level + '">' + esc(row.level) + '</span></div>';
      });
      html += '</div></div>';
    });

    html += '<details class="report-raw"><summary>Raw JSON (full data)</summary><pre>' + esc(rawText) + '</pre></details>';
    return html;
  }

  function renderInto(el, data) {
    if (!el || !isPlainObject(data)) return false;
    const rawText = JSON.stringify(data, null, 2);
    el.innerHTML = renderHTML(data, rawText);
    el.classList.add('report-view');
    return true;
  }

  /* Attach to the classic scan result boxes. */
  function initClassic() {
    const boxes = document.querySelectorAll('[data-scan-result], .result.json-raw');
    boxes.forEach(function (box) {
      const raw = (box.textContent || '').trim();
      if (!raw) return;
      let data = null;
      try { data = JSON.parse(raw); } catch (e) { data = null; }
      if (!data || !renderInto(box, data)) {
        box.classList.add('json-raw');
      }
    });
  }

  /* Advanced intelligence: result card + "View readable report" toggle. */
  function initAdvanced() {
    document.querySelectorAll('.advanced-tool-card').forEach(function (card) {
      const pre = card.querySelector('.advanced-result');
      if (!pre || card.querySelector('.report-toggle')) return;
      const wrap = document.createElement('div');
      wrap.className = 'report-view-wrap';
      const view = document.createElement('div');
      view.className = 'report-view';
      view.hidden = true;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn ghost small report-toggle';
      btn.textContent = 'View readable report';
      btn.hidden = true;
      pre.insertAdjacentElement('afterend', wrap);
      wrap.appendChild(btn);
      wrap.appendChild(view);
      let lastText = '';
      const observer = new MutationObserver(function () {
        const text = (pre.textContent || '').trim();
        if (text === lastText) return;
        lastText = text;
        if (!text) { btn.hidden = true; view.hidden = true; view.innerHTML = ''; return; }
        let data = null;
        try { data = JSON.parse(text); } catch (e) { data = null; }
        if (data && isPlainObject(data)) {
          view.innerHTML = renderHTML(data, text);
          btn.hidden = false;
        } else {
          btn.hidden = true;
          view.hidden = true;
          view.innerHTML = '';
        }
      });
      observer.observe(pre, { childList: true, characterData: true, subtree: true });
      btn.addEventListener('click', function () {
        const show = view.hidden;
        view.hidden = !show;
        btn.textContent = show ? 'Hide readable report' : 'View readable report';
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initClassic();
    initAdvanced();
  });

  window.CyberLordReport = { render: renderInto, classify, splitSections, computeVerdict, renderHTML };
})();
