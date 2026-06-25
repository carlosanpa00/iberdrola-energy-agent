import json
import os
from datetime import datetime
from pathlib import Path


def generate_dashboard(
    invoice_data: dict,
    analysis: dict,
    source: str,
    output_path: str = None,
) -> str:
    if output_path is None:
        output_path = os.getenv("DASHBOARD_OUTPUT", "dashboard.html")

    invoices = invoice_data.get("invoices", [])
    cups = invoice_data.get("cups", "N/D")
    is_demo = "Demo" in source

    # Chart data
    labels = [inv.get("fecha", "")[-7:] for inv in invoices]  # YYYY-MM
    importes = [inv.get("importe", 0) for inv in invoices]
    consumos = [inv.get("consumo_kwh", 0) for inv in invoices]

    ac = analysis.get("analisis_costes", {})
    alerts_html = _render_alerts(analysis.get("alertas", []))
    recs_short = _render_recs(analysis.get("recomendaciones_corto_plazo", []), "Corto plazo", "#22c55e")
    recs_mid = _render_recs(analysis.get("recomendaciones_mediano_plazo", []), "Mediano plazo", "#f59e0b")
    recs_long = _render_recs(analysis.get("recomendaciones_largo_plazo", []), "Largo plazo", "#3b82f6")

    demo_banner = """<div class="demo-banner">
        ⚠️ MODO DEMO — Datos simulados. Configure sus credenciales en <code>.env</code> para datos reales.
    </div>""" if is_demo else ""

    invoice_rows = "\n".join(
        f"""<tr>
            <td>{inv.get('fecha','')}</td>
            <td>{inv.get('periodo_desde','')} → {inv.get('periodo_hasta','')}</td>
            <td class="amount">{inv.get('importe',0):.2f} €</td>
            <td>{inv.get('consumo_kwh',0):.1f} kWh</td>
            <td>{(inv['importe']/inv['consumo_kwh']):.4f} €/kWh" if inv.get('consumo_kwh') else "—"</td>
        </tr>"""
        for inv in invoices
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel Facturas Iberdrola</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0f172a; --card:#1e293b; --border:#334155;
    --text:#f1f5f9; --muted:#94a3b8; --accent:#3b82f6;
    --peak:#ef4444; --valley:#22c55e; --warn:#f59e0b;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;padding:1.5rem}}
  h1{{font-size:1.5rem;font-weight:700;margin-bottom:.25rem}}
  h2{{font-size:1.05rem;font-weight:600;color:var(--accent);margin-bottom:.75rem;border-bottom:1px solid var(--border);padding-bottom:.4rem}}
  .subtitle{{color:var(--muted);font-size:.875rem;margin-bottom:1.5rem}}
  .demo-banner{{background:#7c2d12;border:1px solid var(--warn);border-radius:8px;padding:.75rem 1rem;margin-bottom:1.5rem;font-size:.875rem;color:#fef3c7}}
  .grid-4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:1.5rem}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.25rem}}
  .metric-label{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.35rem}}
  .metric-value{{font-size:1.6rem;font-weight:700}}
  .metric-sub{{font-size:.78rem;color:var(--muted);margin-top:.2rem}}
  .accent{{color:var(--accent)}} .peak{{color:var(--peak)}} .valley{{color:var(--valley)}}
  .chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem}}
  @media(max-width:768px){{.chart-row{{grid-template-columns:1fr}}}}
  .chart-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.25rem}}
  canvas{{max-height:260px}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  th{{text-align:left;padding:.6rem .75rem;color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;border-bottom:1px solid var(--border)}}
  td{{padding:.6rem .75rem;border-bottom:1px solid #1e293b}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:rgba(255,255,255,.03)}}
  td.amount{{font-weight:700;color:var(--accent)}}
  .analysis-text{{line-height:1.7;font-size:.9rem;white-space:pre-wrap}}
  .alert{{display:flex;gap:.6rem;padding:.7rem 1rem;border-radius:8px;margin-bottom:.5rem;font-size:.875rem}}
  .alert-critica{{background:#450a0a;border-left:3px solid var(--peak)}}
  .alert-advertencia{{background:#451a03;border-left:3px solid var(--warn)}}
  .alert-info{{background:#0c1a3a;border-left:3px solid var(--accent)}}
  .rec-group{{margin-bottom:1rem}}
  .rec-header{{font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem}}
  .rec-item{{padding:.55rem .85rem;background:rgba(255,255,255,.04);border-radius:6px;margin-bottom:.3rem;font-size:.875rem;line-height:1.5;border-left:3px solid transparent}}
  .badge{{display:inline-block;font-size:.65rem;font-weight:700;padding:.15rem .5rem;border-radius:4px;text-transform:uppercase;letter-spacing:.05em;vertical-align:middle;margin-left:.4rem}}
  .badge-real{{background:#14532d;color:#86efac}} .badge-demo{{background:#451a03;color:#fcd34d}}
  footer{{text-align:center;color:var(--muted);font-size:.75rem;margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border)}}
</style>
</head>
<body>

<h1>⚡ Histórico de Facturas Iberdrola
  <span class="badge {'badge-demo' if is_demo else 'badge-real'}">{'Demo' if is_demo else 'Real'}</span>
</h1>
<p class="subtitle">CUPS: <code>{cups}</code> &nbsp;|&nbsp; Fuente: {source} &nbsp;|&nbsp; {len(invoices)} facturas analizadas</p>

{demo_banner}

<!-- KPI CARDS -->
<div class="grid-4">
  <div class="card">
    <div class="metric-label">Gasto total período</div>
    <div class="metric-value accent">{ac.get('gasto_total_periodo', 0):.2f} €</div>
    <div class="metric-sub">{len(invoices)} facturas</div>
  </div>
  <div class="card">
    <div class="metric-label">Media mensual</div>
    <div class="metric-value">{ac.get('media_mensual', 0):.2f} €</div>
    <div class="metric-sub">por factura</div>
  </div>
  <div class="card">
    <div class="metric-label">Factura más cara</div>
    <div class="metric-value peak">{ac.get('mes_mas_caro', {}).get('importe', 0):.2f} €</div>
    <div class="metric-sub">{ac.get('mes_mas_caro', {}).get('fecha', '')}</div>
  </div>
  <div class="card">
    <div class="metric-label">Precio medio</div>
    <div class="metric-value valley">{ac.get('precio_medio_kwh', 0):.4f} €/kWh</div>
    <div class="metric-sub">promedio período</div>
  </div>
</div>

<!-- CHARTS -->
<div class="chart-row">
  <div class="chart-card">
    <h2>Importe por factura (€)</h2>
    <canvas id="chartImportes"></canvas>
  </div>
  <div class="chart-card">
    <h2>Consumo por factura (kWh)</h2>
    <canvas id="chartConsumos"></canvas>
  </div>
</div>

<!-- INVOICE TABLE -->
<div class="card" style="margin-bottom:1.5rem;overflow-x:auto">
  <h2>Detalle de Facturas</h2>
  <table>
    <thead><tr><th>Fecha</th><th>Período</th><th>Importe</th><th>Consumo</th><th>€/kWh</th></tr></thead>
    <tbody>{invoice_rows}</tbody>
  </table>
</div>

<!-- AI ANALYSIS -->
<div class="card" style="margin-bottom:1.5rem">
  <h2>Análisis del Asesor Energético (Gemma)</h2>
  <p class="analysis-text">{analysis.get('resumen_ejecutivo','')}</p>
  {f'<br><p class="analysis-text">{ac.get("detalle","")}</p>' if ac.get('detalle') else ''}
  {f'<br><p class="analysis-text" style="color:var(--muted)">{analysis.get("tendencia","")}</p>' if analysis.get('tendencia') else ''}
</div>

{f'<div class="card" style="margin-bottom:1.5rem"><h2>Alertas</h2>{alerts_html}</div>' if alerts_html else ''}

<div class="card" style="margin-bottom:1.5rem">
  <h2>Recomendaciones</h2>
  {recs_short}{recs_mid}{recs_long}
</div>

{f'<div class="card" style="margin-bottom:1.5rem"><h2>Comparación de Tarifas</h2><p class="analysis-text">{analysis.get("comparacion_tarifas","")}</p></div>' if analysis.get('comparacion_tarifas') else ''}

{f'<div class="card" style="margin-bottom:1.5rem;background:#1a1f2e"><p class="analysis-text" style="color:var(--muted);font-size:.8rem">⚠️ {analysis.get("disclaimer","")}</p></div>' if analysis.get('disclaimer') else ''}

<footer>Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; Agente: asesor-energia-espana &nbsp;|&nbsp; Modelo: {os.getenv('OLLAMA_MODEL','gemma4')}</footer>

<script>
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

const labels = {json.dumps(labels)};
const importes = {json.dumps(importes)};
const consumos = {json.dumps(consumos)};
const maxIdx = importes.indexOf(Math.max(...importes));

new Chart(document.getElementById('chartImportes'), {{
  type: 'bar',
  data: {{
    labels,
    datasets: [{{
      label: 'Importe (€)',
      data: importes,
      backgroundColor: importes.map((_, i) => i === maxIdx ? 'rgba(239,68,68,.7)' : 'rgba(59,130,246,.6)'),
      borderRadius: 5,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ grid: {{ color: '#334155' }}, ticks: {{ callback: v => v + ' €' }} }},
      x: {{ grid: {{ color: '#1e293b' }} }}
    }}
  }}
}});

new Chart(document.getElementById('chartConsumos'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [{{
      label: 'Consumo (kWh)',
      data: consumos,
      borderColor: '#22c55e',
      backgroundColor: 'rgba(34,197,94,.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 5,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ grid: {{ color: '#334155' }}, ticks: {{ callback: v => v + ' kWh' }} }},
      x: {{ grid: {{ color: '#1e293b' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def _render_alerts(alerts: list) -> str:
    icons = {"critica": "🔴", "advertencia": "🟡", "info": "🔵"}
    return "\n".join(
        f'<div class="alert alert-{a.get("nivel","info")}">{icons.get(a.get("nivel","info"),"ℹ️")} {a.get("mensaje","")}</div>'
        for a in alerts
    )


def _render_recs(recs: list, title: str, color: str) -> str:
    if not recs:
        return ""
    items = "\n".join(
        f'<div class="rec-item" style="border-left-color:{color}">• {r}</div>' for r in recs
    )
    return f'<div class="rec-group"><div class="rec-header" style="color:{color}">{title}</div>{items}</div>'
