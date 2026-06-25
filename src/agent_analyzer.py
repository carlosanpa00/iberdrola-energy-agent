import os
import json
import re
from pathlib import Path
import requests


_AGENT_MD_PATH = Path(__file__).parent.parent / ".claude" / "agents" / "asesor-energia-espana.md"

_JSON_SCHEMA = """
Responde ÚNICAMENTE con un objeto JSON válido (sin markdown, sin texto fuera del JSON) con esta estructura exacta:
{
  "resumen_ejecutivo": "string",
  "analisis_costes": {
    "gasto_total_periodo": number,
    "media_mensual": number,
    "mes_mas_caro": {"fecha": "string", "importe": number},
    "mes_mas_barato": {"fecha": "string", "importe": number},
    "precio_medio_kwh": number,
    "detalle": "string"
  },
  "tendencia": "string — evolución del consumo y gasto en el tiempo",
  "alertas": [
    {"nivel": "critica|advertencia|info", "mensaje": "string"}
  ],
  "recomendaciones_corto_plazo": ["string"],
  "recomendaciones_mediano_plazo": ["string"],
  "recomendaciones_largo_plazo": ["string"],
  "comparacion_tarifas": "string",
  "disclaimer": "string"
}
"""


def _load_system_prompt() -> str:
    try:
        content = _AGENT_MD_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "Eres un experto asesor energético del mercado español."

    parts = content.split("---")
    body = "---".join(parts[2:]) if len(parts) >= 3 else content

    marker = "# Persistent Agent Memory"
    if marker in body:
        body = body[: body.index(marker)]

    return body.strip()


def analyze_invoices(invoice_data: dict, source: str) -> dict:
    """Send invoice history to local Gemma via Ollama for analysis."""
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "gemma4")

    system_prompt = _load_system_prompt()
    invoices = invoice_data.get("invoices", [])
    cups = invoice_data.get("cups", "N/D")

    # Build invoice table for the prompt
    lines = []
    for inv in invoices:
        lines.append(
            f"  {inv.get('fecha','')} | "
            f"{inv.get('periodo_desde','')} → {inv.get('periodo_hasta','')} | "
            f"{inv.get('importe', 0):.2f} € | "
            f"{inv.get('consumo_kwh', 0):.1f} kWh"
        )

    total = sum(i.get("importe", 0) for i in invoices)
    total_kwh = sum(i.get("consumo_kwh", 0) for i in invoices)
    media = total / len(invoices) if invoices else 0
    precio_medio = total / total_kwh if total_kwh else 0

    user_message = f"""Analiza el histórico de facturas de electricidad de este hogar español:

Fuente de datos: {source}
CUPS: {cups}
Número de facturas: {len(invoices)}
Gasto total del período: {total:.2f} €
Consumo total del período: {total_kwh:.1f} kWh
Media mensual: {media:.2f} €
Precio medio €/kWh: {precio_medio:.4f}

Detalle de facturas (fecha | período | importe | consumo):
{chr(10).join(lines)}

{_JSON_SCHEMA}
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 4096},
    }

    url = f"{ollama_host.rstrip('/')}/v1/chat/completions"
    print(f"  [→] Enviando facturas a {model} via Ollama...")

    try:
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        full_text = resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"No se puede conectar con Ollama en {ollama_host}. "
            f"Asegúrate de que está corriendo (`ollama serve`) "
            f"y que el modelo está descargado (`ollama pull {model}`)."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Error de Ollama: {e}")

    print("  [✓] Análisis completado.")
    return _extract_json(full_text, invoices, total, media, precio_medio)


def _extract_json(text: str, invoices: list, total: float, media: float, precio_medio: float) -> dict:
    clean = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", clean)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback estructurado
    sorted_inv = sorted(invoices, key=lambda x: x.get("importe", 0))
    return {
        "resumen_ejecutivo": text[:800],
        "analisis_costes": {
            "gasto_total_periodo": round(total, 2),
            "media_mensual": round(media, 2),
            "mes_mas_caro": {"fecha": sorted_inv[-1].get("fecha", "") if sorted_inv else "", "importe": sorted_inv[-1].get("importe", 0) if sorted_inv else 0},
            "mes_mas_barato": {"fecha": sorted_inv[0].get("fecha", "") if sorted_inv else "", "importe": sorted_inv[0].get("importe", 0) if sorted_inv else 0},
            "precio_medio_kwh": round(precio_medio, 4),
            "detalle": "Ver resumen ejecutivo.",
        },
        "tendencia": "",
        "alertas": [],
        "recomendaciones_corto_plazo": [],
        "recomendaciones_mediano_plazo": [],
        "recomendaciones_largo_plazo": [],
        "comparacion_tarifas": "",
        "disclaimer": "Este análisis es orientativo. Consulte con su comercializadora para cambios contractuales.",
    }
