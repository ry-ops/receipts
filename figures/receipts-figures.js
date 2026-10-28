/* receipts figures: animated, interactive figures drawn from receipts.json.
   Nothing is hand-typed into a figure, so a figure can't claim more than the ledger.

   Usage:
     <link rel="stylesheet" href="receipts-figures.css">
     <script src="receipts-figures.js" defer></script>
     <div class="rcpt" data-rcpt="matrix" data-src="receipts.json"><p>fallback text</p></div>
     <div class="rcpt" data-rcpt="replay" data-src="receipts.json"><p>fallback text</p></div>

   data-src can also be "#some-id" to read a <script type="application/json" id="some-id">.
   Honors prefers-reduced-motion. No dependencies, no network calls beyond data-src. */
(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const COL = { tested: "#34d399", documented: "#60a5fa", "not-found": "#737db0", gap: "#fb7185", ink: "#f4f6ff" };

  function attrs(n, a) {
    for (const [k, v] of Object.entries(a || {})) {
      if (v == null || v === false) continue;
      if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v;
      else if (k === "style" && typeof v === "object") for (const [sk, sv] of Object.entries(v)) n.style.setProperty(sk.replace(/[A-Z]/g, m => "-" + m.toLowerCase()), String(sv));
      else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    return n;
  }
  const S = (t, a, ...k) => { const n = attrs(document.createElementNS(NS, t), a); k.flat().forEach(c => c != null && n.append(typeof c === "string" ? document.createTextNode(c) : c)); return n; };
  const H = (t, a, ...k) => { const n = attrs(document.createElement(t), a); k.flat().forEach(c => c != null && n.append(c)); return n; };
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const head = (title, chip) => H("div", { class: "rcpt-head" }, H("span", { class: "rcpt-title", text: title }), chip ? H("span", { class: "rcpt-chip", text: chip }) : null);

  async function load(src) {
    if (src.startsWith("#")) return JSON.parse(document.querySelector(src).textContent);
    const r = await fetch(src, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`${src}: HTTP ${r.status}`);
    return r.json();
  }

  /* ------------------------------------------------------------- matrix */
  function matrix(el, d) {
    const subs = d.subjects, caps = d.capabilities;
    const W = 820, rh = 34, top = 50, labelW = Math.max(300, W - subs.length * 105 - 20);
    const cx = subs.map((_, i) => labelW + 40 + i * 105);
    const Hh = top + caps.length * rh + 14;
    const g = S("g");
    subs.forEach((s, i) => g.append(S("text", { x: cx[i], y: 30, "text-anchor": "middle", "font-size": 15, "font-weight": 800, fill: s.color || COL.ink }, s.name)));
    const first = caps.findIndex(c => c.gap);
    if (first >= 0) g.append(S("rect", { x: 6, y: top + first * rh - 4, width: W - 12, height: (caps.length - first) * rh + 8, rx: 12, fill: "rgba(251,113,133,.07)", stroke: COL.gap, "stroke-width": 1.5, class: "rcpt-ghost" }));
    const panel = H("div", { class: "rcpt-panel", html: "Select a dot to see what backs it." });
    caps.forEach((c, i) => {
      const y = top + i * rh;
      const row = S("g", { class: "rcpt-rise", style: { "--d": `${i * 0.08}s` } });
      if (i % 2 === 0 && !c.gap) row.append(S("rect", { x: 6, y: y - 2, width: W - 12, height: rh - 2, rx: 6, fill: "rgba(255,255,255,.025)" }));
      row.append(S("text", { x: 16, y: y + 20, "font-size": 14.5, "font-weight": c.gap ? 700 : 500, fill: c.gap ? "#fecdd3" : COL.ink }, c.label));
      subs.forEach((s, k) => {
        const cell = c.cells[s.id] || { status: "not-found" };
        const x = cx[k], cy = y + 15, col = COL[cell.status] || COL["not-found"];
        const mark = cell.status === "tested" ? S("circle", { cx: x, cy, r: 8, fill: col })
          : cell.status === "documented" ? S("g", {}, S("circle", { cx: x, cy, r: 7.5, fill: "none", stroke: col, "stroke-width": 2 }), S("path", { d: `M${x},${cy - 7.5} A7.5,7.5 0 0 1 ${x},${cy + 7.5} Z`, fill: col }))
          : S("circle", { cx: x, cy, r: 7, fill: "none", stroke: c.gap ? COL.gap : col, "stroke-width": 2, "stroke-dasharray": "3 3" });
        const evs = (cell.evidence || []).map(id => { const e = (d.evidence || {})[id]; return e ? `${id} (${e.kind_label})` : id; });
        const why = [cell.note, evs.length && `Evidence: ${evs.join(", ")}`, cell.source && `Source: ${cell.source}`].filter(Boolean).join(" · ");
        const dot = S("g", { tabindex: 0, role: "button", "aria-label": `${s.name}, ${c.label}: ${d.legend[cell.status]}. ${why}`, style: { cursor: "pointer" } }, S("circle", { cx: x, cy, r: 14, fill: "transparent" }), mark);
        const show = () => { panel.innerHTML = `<b>${esc(s.name)} · ${esc(c.label)}</b> <span class="rcpt-st rcpt-${esc(cell.status)}">${esc(d.legend[cell.status])}</span><br>${esc(why)}`; };
        dot.addEventListener("click", show); dot.addEventListener("mouseenter", show);
        dot.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(); } });
        row.append(dot);
      });
      g.append(row);
    });
    const legend = H("div", { class: "rcpt-legend" },
      ...[["tested", COL.tested, "solid"], ["documented", COL.documented, "half"], ["not-found", COL["not-found"], "dash"]].map(([k, c, sty]) =>
        H("span", {}, H("i", { class: `rcpt-key ${sty}`, style: { "--c": c } }), d.legend[k])),
      first >= 0 ? H("span", {}, H("i", { class: "rcpt-key dash", style: { "--c": COL.gap } }), "Gap: none of them") : null);
    el.replaceChildren(head("The capability map", `as of ${d.study.date}`),
      S("svg", { viewBox: `0 0 ${W} ${Hh}`, role: "img", "aria-label": "Capability map: " + caps.map(c => c.label).join("; ") }, g),
      legend, panel);
  }

  /* ------------------------------------------------------------- replay */
  function replay(el, d) {
    const steps = d.steps;
    if (!steps.length) { el.replaceChildren(head("Replay"), H("p", { class: "rcpt-panel", text: "This study has no replay steps." })); return; }
    let i = 0, timer = null;
    const rail = H("div", { class: "rcpt-rail", style: { "--n": steps.length } });
    const title = H("div", { class: "rcpt-step" });
    const term = H("pre", { class: "rcpt-term", "aria-live": "polite" });
    const shot = H("img", { class: "rcpt-shot", alt: "", hidden: true });
    const base = el.dataset.src && !el.dataset.src.startsWith("#") ? el.dataset.src.replace(/[^/]*$/, "") : "";
    const what = H("p", { class: "rcpt-what" });
    const meta = H("span", { class: "rcpt-count" });
    const btn = H("button", { class: "rcpt-btn", text: "Play", onclick: () => (timer ? stop() : start()) });
    const show = k => {
      i = k;
      [...rail.children].forEach((b, j) => { b.classList.toggle("done", j < k); if (j === k) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current"); });
      const s = steps[k];
      title.innerHTML = `${k + 1}. ${esc(s.title)}${s.sub ? `<small>${esc(s.sub)}</small>` : ""}`;
      term.textContent = s.text || "";
      if (s.image) { shot.src = base + s.image; shot.alt = s.represents || s.title; shot.hidden = false; term.hidden = !s.text; }
      else { shot.hidden = true; term.hidden = false; }
      what.innerHTML = s.represents ? `<b>Shows:</b> ${esc(s.represents)}` : "";
      const labels = [...new Set(s.evidence.map(id => ((d.evidence || {})[id] || {}).kind_label).filter(Boolean))];
      meta.textContent = `Evidence ${s.evidence.join(", ")} · ${labels.join(", ") || s.kind}`;
    };
    const stop = () => { clearInterval(timer); timer = null; btn.textContent = "Play"; };
    const start = () => { if (i === steps.length - 1) show(0); btn.textContent = "Pause"; timer = setInterval(() => (i >= steps.length - 1 ? stop() : show(i + 1)), 4200); };
    steps.forEach((s, k) => rail.append(H("button", { "aria-label": `Step ${k + 1}: ${s.title}`, text: String(k + 1), onclick: () => { stop(); show(k); } })));
    show(0);
    el.replaceChildren(head("Replay", `recorded ${d.study.date}`), rail, title, what, term, shot, H("div", { class: "rcpt-row" }, meta, btn));
    el._play = () => { if (!RM) start(); };
  }

  const FIG = { matrix, replay };
  const boot = () => document.querySelectorAll(".rcpt[data-rcpt]").forEach(async el => {
    if (el.dataset.ready) return;
    el.dataset.ready = "1";
    const f = FIG[el.dataset.rcpt];
    if (!f) return;
    try { f(el, await load(el.dataset.src || "receipts.json")); }
    catch (e) { console.error("[receipts figure]", el.dataset.rcpt, e); return; }
    const on = () => { el.classList.add("on"); el._play && el._play(); };
    if (RM || !("IntersectionObserver" in window)) return on();
    const io = new IntersectionObserver(es => { if (es.some(x => x.isIntersecting)) { io.disconnect(); on(); } }, { threshold: 0.25 });
    io.observe(el);
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
  document.addEventListener("astro:page-load", boot);
})();
