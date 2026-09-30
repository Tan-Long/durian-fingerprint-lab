#!/usr/bin/env python3
"""Build a dependency-free offline viewer for processed durian view banks."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import quote


def build_viewer(root: Path) -> Path:
    source = root / "PROCESSING_RESULTS.csv"
    with source.open(encoding="utf-8-sig") as rows:
        records = list(csv.DictReader(rows))
    for record in records:
        parts = [record["recorded_sample_id"], record["session_id"]]
        base = "samples/" + "/".join(quote(part, safe="-_.") for part in parts)
        record["contact_sheet"] = f"{base}/contact-sheet.jpg"
        record["manifest"] = f"{base}/manifest.json"
    payload = json.dumps(records, ensure_ascii=False, indent=2).replace("</", "<\\/")
    generated = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
    path = root / "groundtruth_viewer.html"
    path.write_text(_html(payload, generated), encoding="utf-8")
    return path


def _html(payload: str, generated: str) -> str:
    return f'''<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Durian Fingerprint · Ground-truth Database</title>
  <style>
    :root {{
      --canvas: #f3f4ef;
      --surface: #ffffff;
      --surface-inset: #eef0e8;
      --text: #20231d;
      --text-2: #555b4e;
      --text-3: #777d70;
      --muted: #9a9f94;
      --border: #d9ddd2;
      --border-strong: #adb5a3;
      --focus: #2f6f48;
      --brand: #416a43;
      --brand-soft: #e4eee2;
      --ready: #287044;
      --ready-soft: #e4f2e8;
      --review: #9a5b16;
      --review-soft: #fff0d9;
      --danger: #9b3b32;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --shadow-overlay: 0 24px 70px rgba(31, 37, 27, .24);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      background: var(--canvas);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    button, input, select {{ font: inherit; }}
    button, select, a {{ -webkit-tap-highlight-color: transparent; }}
    button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible {{
      outline: 3px solid color-mix(in srgb, var(--focus) 35%, transparent);
      outline-offset: 2px;
    }}
    .mono, .metric-value, .sample-id {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-variant-numeric: tabular-nums;
    }}
    .topbar {{
      position: sticky;
      z-index: 10;
      top: 0;
      border-bottom: 1px solid var(--border);
      background: rgba(243, 244, 239, .94);
      backdrop-filter: blur(14px);
    }}
    .shell {{ width: min(1560px, 100%); margin: 0 auto; padding: 0 24px; }}
    .brand-row {{ min-height: 72px; display: flex; align-items: center; gap: 16px; }}
    .brand-mark {{
      width: 38px; height: 38px; display: grid; place-items: center;
      border: 1px solid #2f5634; border-radius: 50%; color: white; background: var(--brand);
      font: 700 11px/1 ui-monospace, monospace; letter-spacing: -.04em;
    }}
    .brand-copy {{ min-width: 0; }}
    .eyebrow {{ margin: 0 0 3px; color: var(--text-3); font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ margin: 0; font-size: clamp(18px, 2vw, 24px); line-height: 1.15; letter-spacing: -.025em; }}
    .generated {{ margin-left: auto; color: var(--text-3); font-size: 12px; white-space: nowrap; }}
    main {{ padding: 24px 0 48px; }}
    .summary {{ display: grid; grid-template-columns: minmax(0, 1fr) repeat(3, minmax(118px, 160px)); gap: 12px; margin-bottom: 16px; }}
    .summary-intro, .summary-stat {{ border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }}
    .summary-intro {{ padding: 18px 20px; }}
    .summary-intro h2 {{ margin: 0 0 6px; font-size: 16px; letter-spacing: -.015em; }}
    .summary-intro p {{ margin: 0; max-width: 68ch; color: var(--text-2); font-size: 13px; line-height: 1.5; }}
    .summary-stat {{ display: flex; flex-direction: column; justify-content: center; padding: 14px 16px; }}
    .summary-stat strong {{ font: 700 25px/1.1 ui-monospace, monospace; font-variant-numeric: tabular-nums; }}
    .summary-stat span {{ margin-top: 5px; color: var(--text-3); font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }}
    .summary-stat.ready strong {{ color: var(--ready); }}
    .summary-stat.review strong {{ color: var(--review); }}
    .toolbar {{
      display: grid; grid-template-columns: minmax(220px, 1fr) auto minmax(170px, auto); gap: 12px; align-items: center;
      margin-bottom: 16px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface);
    }}
    .search-wrap {{ position: relative; }}
    .search-wrap input {{
      width: 100%; min-height: 42px; padding: 0 42px 0 14px; border: 1px solid var(--border); border-radius: var(--radius-sm);
      color: var(--text); background: var(--surface-inset);
    }}
    .search-wrap input::placeholder {{ color: var(--muted); }}
    .search-key {{ position: absolute; top: 10px; right: 10px; padding: 3px 6px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-3); background: white; font-size: 10px; }}
    .segments {{ display: flex; padding: 3px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface-inset); }}
    .segments button {{ min-height: 34px; padding: 0 12px; border: 0; border-radius: 5px; color: var(--text-2); background: transparent; cursor: pointer; font-size: 12px; font-weight: 700; }}
    .segments button:hover {{ color: var(--text); }}
    .segments button[aria-pressed="true"] {{ color: var(--text); background: white; box-shadow: 0 1px 2px rgba(30, 35, 26, .09); }}
    .sort {{ min-height: 42px; padding: 0 36px 0 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); background: var(--surface); }}
    .result-line {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin: 0 2px 10px; color: var(--text-3); font-size: 12px; }}
    .result-line strong {{ color: var(--text-2); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .card {{ min-width: 0; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); transition: border-color 140ms ease, transform 140ms ease; }}
    .card:hover {{ border-color: var(--border-strong); transform: translateY(-1px); }}
    .card.review {{ border-color: #dfbd86; }}
    .card-head {{ display: flex; align-items: flex-start; gap: 12px; padding: 14px 14px 12px; }}
    .card-title {{ min-width: 0; flex: 1; }}
    .sample-id {{ overflow: hidden; margin: 0; font-size: 15px; font-weight: 750; text-overflow: ellipsis; white-space: nowrap; }}
    .session-id {{ overflow: hidden; margin: 4px 0 0; color: var(--text-3); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }}
    .status {{ flex: 0 0 auto; padding: 5px 7px; border-radius: 999px; font-size: 10px; font-weight: 800; letter-spacing: .05em; }}
    .status.ready {{ color: var(--ready); background: var(--ready-soft); }}
    .status.review {{ color: var(--review); background: var(--review-soft); }}
    .sheet-button {{
      position: relative; display: block; width: 100%; padding: 0; border: 0; border-block: 1px solid var(--border); background: #e8eae3; cursor: zoom-in;
    }}
    .sheet-button::after {{ content: "Mở dải 360°"; position: absolute; right: 10px; bottom: 10px; padding: 6px 8px; border-radius: 5px; color: white; background: rgba(25, 29, 23, .78); opacity: 0; transform: translateY(3px); transition: 140ms ease; font-size: 11px; font-weight: 700; }}
    .sheet-button:hover::after, .sheet-button:focus-visible::after {{ opacity: 1; transform: none; }}
    .sheet-button img {{ display: block; width: 100%; aspect-ratio: 8 / 3; object-fit: cover; background: linear-gradient(90deg, #e5e7e0, #f3f4ef, #e5e7e0); }}
    .sheet-button.image-error {{ min-height: 150px; cursor: default; }}
    .sheet-button.image-error::before {{ content: "Không đọc được contact sheet"; position: absolute; inset: 0; display: grid; place-items: center; color: var(--danger); font-size: 12px; }}
    .rotation-axis {{ display: grid; grid-template-columns: repeat(5, 1fr); padding: 6px 10px 0; color: var(--muted); font: 9px/1 ui-monospace, monospace; }}
    .rotation-axis span:not(:first-child):not(:last-child) {{ text-align: center; }}
    .rotation-axis span:last-child {{ text-align: right; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin: 12px 14px; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--border); }}
    .metric {{ min-width: 0; padding: 9px 8px; background: var(--surface-inset); }}
    .metric-label {{ overflow: hidden; color: var(--text-3); font-size: 9px; font-weight: 700; letter-spacing: .04em; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }}
    .metric-value {{ margin-top: 4px; overflow: hidden; color: var(--text); font-size: 12px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }}
    .quality {{ margin: 0 14px 12px; }}
    .quality-line {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; color: var(--text-3); font-size: 10px; }}
    .track {{ height: 4px; overflow: hidden; border-radius: 99px; background: var(--surface-inset); }}
    .track span {{ display: block; width: var(--quality); height: 100%; border-radius: inherit; background: var(--brand); }}
    .review .track span {{ background: var(--review); }}
    .decision {{ margin: 0 14px 12px; padding: 8px 10px; border-radius: var(--radius-sm); font-size: 10px; font-weight: 750; line-height: 1.4; }}
    .decision.review {{ color: var(--review); background: var(--review-soft); }}
    .decision.borderline {{ color: #70591a; background: #f5efcf; }}
    .card-foot {{ display: flex; align-items: center; gap: 10px; padding: 0 14px 14px; }}
    .card-foot a {{ min-height: 34px; display: inline-flex; align-items: center; color: var(--brand); font-size: 11px; font-weight: 750; text-decoration: none; }}
    .card-foot a:hover {{ text-decoration: underline; }}
    .card-note {{ min-width: 0; margin-left: auto; overflow: hidden; color: var(--text-3); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }}
    .empty {{ grid-column: 1 / -1; padding: 64px 24px; border: 1px dashed var(--border-strong); border-radius: var(--radius-md); color: var(--text-2); text-align: center; background: var(--surface); }}
    dialog {{ width: min(1500px, calc(100vw - 32px)); max-height: calc(100vh - 32px); padding: 0; overflow: hidden; border: 1px solid var(--border-strong); border-radius: var(--radius-lg); color: var(--text); background: var(--surface); box-shadow: var(--shadow-overlay); }}
    dialog::backdrop {{ background: rgba(25, 29, 23, .64); backdrop-filter: blur(3px); }}
    .dialog-head {{ display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-bottom: 1px solid var(--border); }}
    .dialog-title {{ min-width: 0; flex: 1; }}
    .dialog-title strong {{ display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .dialog-title span {{ display: block; margin-top: 3px; color: var(--text-3); font-size: 11px; }}
    .icon-button {{ width: 40px; height: 40px; flex: 0 0 auto; border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); background: var(--surface); cursor: pointer; font-size: 18px; }}
    .icon-button:hover {{ border-color: var(--border-strong); background: var(--surface-inset); }}
    .dialog-body {{ max-height: calc(100vh - 126px); overflow: auto; padding: 16px; background: var(--surface-inset); }}
    .dialog-body img {{ display: block; width: 100%; height: auto; border: 1px solid var(--border); background: white; }}
    .dialog-axis {{ display: grid; grid-template-columns: repeat(5, 1fr); padding: 8px 2px 0; color: var(--text-3); font: 11px/1 ui-monospace, monospace; }}
    .dialog-axis span:not(:first-child):not(:last-child) {{ text-align: center; }}
    .dialog-axis span:last-child {{ text-align: right; }}
    @media (max-width: 1080px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .summary {{ grid-template-columns: repeat(3, 1fr); }} .summary-intro {{ grid-column: 1 / -1; }} }}
    @media (max-width: 720px) {{
      .shell {{ padding: 0 14px; }} .brand-row {{ min-height: 64px; }} .generated {{ display: none; }} main {{ padding-top: 14px; }}
      .summary {{ grid-template-columns: repeat(3, 1fr); gap: 8px; }} .summary-stat {{ padding: 12px 10px; }} .summary-stat strong {{ font-size: 20px; }}
      .toolbar {{ grid-template-columns: 1fr; }} .segments {{ display: grid; grid-template-columns: repeat(3, 1fr); }} .sort {{ width: 100%; }}
      .grid {{ grid-template-columns: 1fr; }} .sheet-button::after {{ opacity: 1; transform: none; }}
      dialog {{ width: 100vw; max-height: 100vh; border: 0; border-radius: 0; }} .dialog-body {{ max-height: calc(100vh - 70px); padding: 8px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto !important; transition: none !important; }} }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="shell brand-row">
      <div class="brand-mark" aria-hidden="true">DF</div>
      <div class="brand-copy">
        <p class="eyebrow">Durian Fingerprint Lab</p>
        <h1>Ground-truth Database</h1>
      </div>
      <div class="generated">Tạo lúc {generated}</div>
    </div>
  </header>
  <main class="shell">
    <section class="summary" aria-label="Tổng quan database">
      <div class="summary-intro">
        <h2>Database tham chiếu nhiều góc</h2>
        <p>Mỗi quả gồm hai bank camera, 36 góc mỗi camera. Nhấn contact sheet để kiểm tra tuần tự toàn bộ vòng quay; chỉ bản ghi READY được đưa vào tìm kiếm.</p>
      </div>
      <div class="summary-stat"><strong id="totalCount">—</strong><span>Tổng mẫu</span></div>
      <div class="summary-stat ready"><strong id="readyCount">—</strong><span>Ready</span></div>
      <div class="summary-stat review"><strong id="reviewCount">—</strong><span>Review</span></div>
    </section>
    <section class="toolbar" aria-label="Bộ lọc">
      <label class="search-wrap">
        <span class="visually-hidden" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)">Tìm mã quả</span>
        <input id="search" type="search" placeholder="Tìm mã quả hoặc session…" autocomplete="off">
        <span class="search-key" aria-hidden="true">/</span>
      </label>
      <div class="segments" role="group" aria-label="Lọc trạng thái">
        <button type="button" data-status="ALL" aria-pressed="true">Tất cả</button>
        <button type="button" data-status="READY" aria-pressed="false">Ready</button>
        <button type="button" data-status="REVIEW" aria-pressed="false">Review</button>
      </div>
      <label>
        <span class="visually-hidden" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)">Sắp xếp</span>
        <select id="sort" class="sort">
          <option value="order">Theo thứ tự quay</option>
          <option value="sample">Theo mã quả</option>
          <option value="features">Đặc trưng thấp trước</option>
          <option value="loop">Độ lặp thấp trước</option>
        </select>
      </label>
    </section>
    <div class="result-line"><strong id="resultCount">0 mẫu</strong><span>Enter: mở · ← →: chuyển mẫu · Esc: đóng</span></div>
    <section id="grid" class="grid" aria-live="polite"></section>
  </main>
  <dialog id="viewer" aria-labelledby="dialogSample">
    <div class="dialog-head">
      <button class="icon-button" id="previous" type="button" aria-label="Mẫu trước">←</button>
      <div class="dialog-title"><strong id="dialogSample" class="mono"></strong><span id="dialogMeta"></span></div>
      <button class="icon-button" id="next" type="button" aria-label="Mẫu sau">→</button>
      <button class="icon-button" id="close" type="button" aria-label="Đóng">×</button>
    </div>
    <div class="dialog-body">
      <img id="dialogImage" alt="">
      <div class="dialog-axis" aria-hidden="true"><span>0°</span><span>90°</span><span>180°</span><span>270°</span><span>360°</span></div>
    </div>
  </dialog>
  <script>
    const records = {payload};
    const state = {{ status: 'ALL', query: '', sort: 'order', visible: [], active: -1 }};
    const grid = document.getElementById('grid');
    const viewer = document.getElementById('viewer');
    const number = value => Number.parseFloat(value || '0') || 0;
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[char]));
    const quality = record => Math.max(0, Math.min(100, number(record.minimum_loop_inliers) / 3));
    const formatPeriod = value => number(value).toFixed(3) + ' s';
    const formatAngle = value => number(value).toFixed(2) + '°';
    const formatBank = value => (number(value) / 1024 / 1024).toFixed(2) + ' MB';
    const axis = '<div class="rotation-axis" aria-hidden="true"><span>0°</span><span>90°</span><span>180°</span><span>270°</span><span>360°</span></div>';
    function card(record, index) {{
      const status = record.status.toLowerCase();
      const borderline = record.status === 'READY' && number(record.minimum_source_features) < 800;
      const statusText = record.status === 'REVIEW' ? 'REVIEW' : borderline ? 'READY · BIÊN' : 'READY';
      const decision = record.status === 'REVIEW'
        ? '<div class="decision review">Không đưa vào tìm kiếm · hai vòng không lặp đủ.</div>'
        : borderline ? '<div class="decision borderline">Tín hiệu biên · kiểm tra lại bằng ảnh chụp ngẫu nhiên.</div>' : '';
      return `<article class="card ${{status}}">
        <div class="card-head"><div class="card-title"><h3 class="sample-id">${{escapeHtml(record.recorded_sample_id)}}</h3><p class="session-id mono">${{escapeHtml(record.session_id)}}</p></div><span class="status ${{status}}">${{statusText}}</span></div>
        <button class="sheet-button" type="button" data-open="${{index}}" aria-label="Mở contact sheet 72 góc của ${{escapeHtml(record.recorded_sample_id)}}"><img loading="lazy" decoding="async" src="${{escapeHtml(record.contact_sheet)}}" alt="Contact sheet 72 góc của ${{escapeHtml(record.recorded_sample_id)}}" onerror="this.parentElement.classList.add('image-error');this.remove()"></button>
        ${{axis}}
        <div class="metrics">
          <div class="metric"><div class="metric-label">View</div><div class="metric-value">${{escapeHtml(record.views_per_camera)}} × 2</div></div>
          <div class="metric"><div class="metric-label">Chu kỳ</div><div class="metric-value">${{formatPeriod(record.period_sec)}}</div></div>
          <div class="metric"><div class="metric-label">Sai số góc</div><div class="metric-value">${{formatAngle(record.maximum_angle_error_deg)}}</div></div>
          <div class="metric"><div class="metric-label">Min feature</div><div class="metric-value">${{escapeHtml(record.minimum_source_features)}}</div></div>
          <div class="metric"><div class="metric-label">Loop inlier</div><div class="metric-value">${{number(record.minimum_loop_inliers).toFixed(1)}}</div></div>
          <div class="metric"><div class="metric-label">Dung lượng</div><div class="metric-value">${{formatBank(record.bank_bytes)}}</div></div>
        </div>
        <div class="quality"><div class="quality-line"><span>Độ lặp hai vòng</span><strong class="mono">${{number(record.minimum_loop_inliers).toFixed(1)}}</strong></div><div class="track"><span style="--quality:${{quality(record)}}%"></span></div></div>
        ${{decision}}
        <div class="card-foot"><a href="${{escapeHtml(record.manifest)}}" target="_blank" rel="noopener">Mở manifest</a><span class="card-note" title="${{escapeHtml(record.note)}}">${{escapeHtml(record.note)}}</span></div>
      </article>`;
    }}
    function render() {{
      const query = state.query.trim().toLocaleLowerCase('vi');
      state.visible = records.filter(record => (state.status === 'ALL' || record.status === state.status) && (!query || `${{record.recorded_sample_id}} ${{record.session_id}} ${{record.note}}`.toLocaleLowerCase('vi').includes(query)));
      const sorters = {{
        order: (a,b) => number(a.order) - number(b.order),
        sample: (a,b) => a.recorded_sample_id.localeCompare(b.recorded_sample_id, undefined, {{numeric:true}}),
        features: (a,b) => number(a.minimum_source_features) - number(b.minimum_source_features),
        loop: (a,b) => number(a.minimum_loop_inliers) - number(b.minimum_loop_inliers),
      }};
      state.visible.sort(sorters[state.sort]);
      grid.innerHTML = state.visible.length ? state.visible.map(card).join('') : '<div class="empty"><strong>Không tìm thấy mẫu phù hợp.</strong><br>Thử bỏ bộ lọc hoặc nhập mã quả khác.</div>';
      document.getElementById('resultCount').textContent = `${{state.visible.length}} mẫu`;
    }}
    function openAt(index) {{
      if (!state.visible.length) return;
      state.active = (index + state.visible.length) % state.visible.length;
      const record = state.visible[state.active];
      document.getElementById('dialogSample').textContent = record.recorded_sample_id;
      document.getElementById('dialogMeta').textContent = `${{record.status}} · 72 view · chu kỳ ${{formatPeriod(record.period_sec)}} · loop ${{number(record.minimum_loop_inliers).toFixed(1)}}`;
      const image = document.getElementById('dialogImage');
      image.src = record.contact_sheet; image.alt = `Contact sheet 72 góc của ${{record.recorded_sample_id}}`;
      if (!viewer.open) viewer.showModal();
    }}
    document.getElementById('totalCount').textContent = records.length;
    document.getElementById('readyCount').textContent = records.filter(r => r.status === 'READY').length;
    document.getElementById('reviewCount').textContent = records.filter(r => r.status === 'REVIEW').length;
    document.getElementById('search').addEventListener('input', event => {{ state.query = event.target.value; render(); }});
    document.getElementById('sort').addEventListener('change', event => {{ state.sort = event.target.value; render(); }});
    document.querySelector('.segments').addEventListener('click', event => {{
      const button = event.target.closest('button[data-status]'); if (!button) return;
      state.status = button.dataset.status;
      document.querySelectorAll('.segments button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      render();
    }});
    grid.addEventListener('click', event => {{ const button = event.target.closest('[data-open]'); if (button) openAt(Number(button.dataset.open)); }});
    document.getElementById('previous').addEventListener('click', () => openAt(state.active - 1));
    document.getElementById('next').addEventListener('click', () => openAt(state.active + 1));
    document.getElementById('close').addEventListener('click', () => viewer.close());
    viewer.addEventListener('click', event => {{ if (event.target === viewer) viewer.close(); }});
    document.addEventListener('keydown', event => {{
      if (event.key === '/' && !viewer.open && document.activeElement.tagName !== 'INPUT') {{ event.preventDefault(); document.getElementById('search').focus(); }}
      if (!viewer.open) return;
      if (event.key === 'ArrowLeft') openAt(state.active - 1);
      if (event.key === 'ArrowRight') openAt(state.active + 1);
    }});
    render();
  </script>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(build_viewer(args.root))


if __name__ == "__main__":
    main()
