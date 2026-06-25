#!/usr/bin/env python3
"""
Herramienta de análisis de facturas Iberdrola + Gemma (local).

Uso:
  python main.py
"""
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.iberdrola_client import fetch_invoices
from src.agent_analyzer import analyze_invoices
from src.dashboard_generator import generate_dashboard


def main():
    print(f"\n{'='*55}")
    print("  Asesor Energético Iberdrola — Análisis de Facturas")
    print(f"{'='*55}\n")

    # 1. Obtener facturas (Playwright scraping o demo)
    print("[1/3] Obteniendo histórico de facturas de Iberdrola...")
    invoice_data, source = fetch_invoices()
    print(f"  [✓] {source} — {invoice_data.get('total_facturas', 0)} facturas\n")

    # 2. Analizar con Gemma via Ollama
    print("[2/3] Analizando facturas con Gemma (Ollama)...")
    try:
        analysis = analyze_invoices(invoice_data, source)
        print()
    except RuntimeError as e:
        print(f"\n[!] {e}\n")
        analysis = _basic_analysis(invoice_data)

    # 3. Generar dashboard HTML
    print("[3/3] Generando dashboard HTML...")
    output_path = generate_dashboard(
        invoice_data=invoice_data,
        analysis=analysis,
        source=source,
    )

    abs_path = Path(output_path).resolve()
    print(f"  [✓] Dashboard guardado en: {abs_path}\n")
    print(f"{'='*55}")
    print("  Abriendo en el navegador...")
    print(f"{'='*55}\n")

    webbrowser.open(abs_path.as_uri())


def _basic_analysis(invoice_data: dict) -> dict:
    invoices = invoice_data.get("invoices", [])
    total = sum(i.get("importe", 0) for i in invoices)
    total_kwh = sum(i.get("consumo_kwh", 0) for i in invoices)
    media = total / len(invoices) if invoices else 0
    precio_medio = total / total_kwh if total_kwh else 0
    sorted_inv = sorted(invoices, key=lambda x: x.get("importe", 0))

    return {
        "resumen_ejecutivo": (
            f"Período analizado: {len(invoices)} facturas. "
            f"Gasto total: {total:.2f} €. "
            f"Media mensual: {media:.2f} €. "
            f"Precio medio: {precio_medio:.4f} €/kWh."
        ),
        "analisis_costes": {
            "gasto_total_periodo": round(total, 2),
            "media_mensual": round(media, 2),
            "mes_mas_caro": {"fecha": sorted_inv[-1].get("fecha", "") if sorted_inv else "", "importe": sorted_inv[-1].get("importe", 0) if sorted_inv else 0},
            "mes_mas_barato": {"fecha": sorted_inv[0].get("fecha", "") if sorted_inv else "", "importe": sorted_inv[0].get("importe", 0) if sorted_inv else 0},
            "precio_medio_kwh": round(precio_medio, 4),
            "detalle": "Análisis básico (Ollama no disponible).",
        },
        "tendencia": "",
        "alertas": [{"nivel": "advertencia", "mensaje": "Análisis de IA no disponible. Verifica que Ollama está activo y gemma4 descargado."}],
        "recomendaciones_corto_plazo": ["Desplace el consumo intensivo a horas valle (00:00–08:00)."],
        "recomendaciones_mediano_plazo": ["Revise si su tarifa actual sigue siendo competitiva."],
        "recomendaciones_largo_plazo": ["Considere instalar paneles solares si su consumo supera 300 kWh/mes."],
        "comparacion_tarifas": "",
        "disclaimer": "Este análisis es orientativo. Consulte con su comercializadora para cambios contractuales.",
    }


if __name__ == "__main__":
    main()
