"""Self-contained audit report. Transcript content is escaped, never executable."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path


def _value(value):
    return "unknown" if value is None else escape(str(value))


def _table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return '<p class="empty">No records.</p>'
    header = "".join(f"<th>{escape(c.replace('_', ' '))}</th>" for c in columns)
    content = "".join("<tr>" + "".join(f"<td>{_value(row.get(c))}</td>" for c in columns) + "</tr>" for row in rows)
    return f'<div class="scroll"><table><thead><tr>{header}</tr></thead><tbody>{content}</tbody></table></div>'


def render_report(bundle: dict, path: str | Path) -> None:
    transcript = bundle.get("transcript", {})
    synthetic = transcript.get("kind") == "synthetic"
    signals = bundle.get("signals", [])
    replay = bundle.get("replay", {})
    summary = replay.get("summary", {})
    banner = "SYNTHETIC SCENARIO · MECHANICAL TEST ONLY" if synthetic else "RESEARCH REPLAY · NO PROFITABILITY VALIDATION"
    cards = []
    for signal in signals:
        evidence = "".join(f'<blockquote>{escape(e["quote"])}<footer>Segment {escape(e["segment_id"])}</footer></blockquote>' for e in signal["evidence"])
        status = "reviewed" if signal["reviewed"] else "unreviewed"
        details = {key: signal.get(key) for key in ("trigger", "level", "stop", "target", "timeframe_minutes", "horizon_minutes", "extracted_at", "reviewed_at", "available_at", "expires_at")}
        values = "".join(f'<div><dt>{escape(k.replace("_", " "))}</dt><dd>{_value(v)}</dd></div>' for k, v in details.items())
        issues = ", ".join(signal.get("issues", [])) or "No missing fields detected; review still required before entry."
        cards.append(f'<article class="signal" data-status="{status}"><header><h3>{escape(signal["asset"])} <span>{escape(signal["side"])}</span></h3><span class="tag {status}">{status}</span></header><p class="meta">{escape(signal["statement_type"])} · {escape(signal["id"])} · {escape(signal["extractor"])}</p>{evidence}<dl>{values}</dl><p class="issues">{escape(issues)}</p></article>')
    stats = [("Signals", len(signals)), ("Reviewed", sum(s["reviewed"] for s in signals)), ("Paper entries", summary.get("entries", 0)), ("Completed trades", summary.get("completed_trades", 0))]
    if any(type(value) is not int or value < 0 for _, value in stats):
        raise ValueError("Report statistics must be non-negative integers")
    stat_html = "".join(f'<div class="stat"><strong>{_value(v)}</strong><span>{escape(k)}</span></div>' for k, v in stats)
    assumptions = "".join(f"<li>{escape(str(a))}</li>" for a in replay.get("assumptions", []))
    events = [{**e, "reasons": ", ".join(e.get("reasons", []))} for e in replay.get("events", [])]
    equity = replay.get("equity", [])
    chart_data = json.dumps(equity, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    profit = summary.get("net_pnl", 0)
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Signal Decision Lab · Evidence report</title>
<style>
:root{color-scheme:dark;--bg:#111722;--panel:#1b2433;--text:#e9edf4;--muted:#a3b1c4;--line:#344156;--accent:#82d6c3}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:40px 24px 80px}.eyebrow{color:var(--accent);text-transform:uppercase;letter-spacing:.15em;font-size:12px;font-weight:700}h1{font-size:clamp(30px,6vw,56px);line-height:1.1;max-width:780px;margin:14px 0}h2{font-size:25px;margin:40px 0 15px}h3{margin:0;font-size:19px}.lead{color:var(--muted);max-width:790px}.banner{border-left:4px solid #eac27a;background:#312d26;padding:15px 20px;color:#f5dba9;margin:25px 0}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat{background:var(--panel);padding:20px;border-radius:12px}.stat strong{font-size:35px;display:block}.stat span,.meta{color:var(--muted);font-size:13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.signal{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}.signal header{display:flex;gap:10px;justify-content:space-between;align-items:center}.signal h3 span{font-size:14px;font-weight:400;color:var(--muted)}.tag{font-size:11px;border-radius:20px;background:#384255;padding:4px 10px;white-space:nowrap}.reviewed{background:#1e5148;color:#b4eadc}blockquote{margin:20px 0;border-left:2px solid var(--accent);padding-left:15px;color:#dae7f6}blockquote footer{color:var(--muted);font-size:12px;margin-top:10px}dl{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}dt{font-size:11px;color:var(--muted);text-transform:uppercase}dd{margin:0;font-size:14px;overflow-wrap:anywhere}.issues{font-size:12px;color:#eac27a;overflow-wrap:anywhere}.scroll{overflow:auto;border:1px solid var(--line);border-radius:12px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px 15px;border-bottom:1px solid var(--line);vertical-align:top}th{background:var(--panel);text-transform:capitalize}td{max-width:350px;overflow-wrap:anywhere}.filter{display:flex;gap:10px;margin:16px 0}button{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:20px;padding:8px 16px;cursor:pointer}button[aria-pressed=true]{background:#254d4a;border-color:var(--accent)}svg{background:var(--panel);width:100%;height:220px;border-radius:12px}.footnote{color:var(--muted);font-size:13px}.empty{color:var(--muted)}details{margin-top:20px}pre{overflow:auto;font-size:12px;background:var(--panel);padding:20px;border-radius:10px}a{color:var(--accent)}@media(max-width:700px){main{padding:25px 15px}.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.signal{padding:17px}dl{gap:10px}h2{margin-top:30px}}
</style><main><div class="eyebrow">Signal Decision Lab / Research draft</div><h1>Every decision starts with evidence.</h1><p class="lead">A traceable path from timestamped claims to conditional setups, reviewed rules and conservative paper execution.</p>
__BANNER__<div class="stats">__STATS__</div><h2>01 / Source & availability</h2>__SOURCE__
<h2>02 / Extracted claims</h2><p class="footnote">Missing parameters remain unknown. A review flag is a recorded human action, not a model confidence score.</p><div class="filter"><button aria-pressed="true" data-filter="all">All claims</button><button aria-pressed="false" data-filter="reviewed">Reviewed</button><button aria-pressed="false" data-filter="unreviewed">Needs review</button></div><div class="grid">__SIGNALS__</div>
<h2>03 / Paper equity</h2><p class="footnote">__PROFIT__ Open positions are marked to market. This synthetic or historical replay cannot establish a trading edge.</p><svg id="equity" role="img" aria-label="Marked-to-market paper equity" viewBox="0 0 1000 220"><title>Paper equity across completed bars</title></svg>
<h2>04 / Decision audit</h2>__EVENTS__<h2>05 / Completed trades</h2>__TRADES__
<details><summary>Simulation assumptions and configuration</summary><ul>__ASSUMPTIONS__</ul><pre>__POLICY__</pre></details><p class="footnote">Offline research prototype. Broker order execution is not implemented. Jeff confidence concerns a rule-decision task, not market profitability.</p></main>
<script type="application/json" id="chart-data">__CHART_DATA__</script><script>
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelectorAll('.signal').forEach(card=>{card.hidden=button.dataset.filter!=='all'&&card.dataset.status!==button.dataset.filter})}));
const series=JSON.parse(document.getElementById('chart-data').textContent);const svg=document.getElementById('equity');const values=series.map(p=>Number(p.equity));if(values.length&&values.every(Number.isFinite)){let lo=Math.min(...values),hi=Math.max(...values),range=hi-lo||Math.max(1,Math.abs(lo)*.001);const pts=values.map((v,i)=>`${45+i*910/Math.max(1,values.length-1)},${185-(v-lo)*145/range}`).join(' ');const poly=document.createElementNS('http://www.w3.org/2000/svg','polyline');poly.setAttribute('points',pts);poly.setAttribute('fill','none');poly.setAttribute('stroke','#82d6c3');poly.setAttribute('stroke-width','3');svg.append(poly);for(const [label,y]of[[hi,25],[lo,210]]){const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x','45');t.setAttribute('y',String(y));t.setAttribute('fill','#a3b1c4');t.setAttribute('font-size','13');t.textContent=label.toFixed(2);svg.append(t)}}
</script></html>'''
    replacements = {
        "__BANNER__": f'<div class="banner">{banner}</div>', "__STATS__": stat_html,
        "__SOURCE__": _table([transcript], ["source_id", "channel", "kind", "published_at", "available_at"]),
        "__SIGNALS__": "".join(cards) or '<p class="empty">No supported asset claims found.</p>',
        "__EVENTS__": _table(events, ["time", "type", "signal_id", "reasons"]),
        "__TRADES__": _table(replay.get("trades", []), ["signal_id", "side", "entry_time", "exit_time", "quantity", "net_pnl", "exit_reason"]),
        "__ASSUMPTIONS__": assumptions, "__POLICY__": escape(json.dumps(replay.get("policy", {}), indent=2)),
        "__CHART_DATA__": chart_data, "__PROFIT__": f"Net scenario P&L: {_value(round(profit, 4))} units.",
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
