import os
import re
from datetime import datetime


LOGIN_URL = "https://www.iberdrola.es/wclifral/login/loginUnicoForm"
INVOICES_URL = "https://www.iberdrola.es/wclifrmr/mac/gestiones/facturas/historico-facturas"


def fetch_invoices() -> tuple[dict, str]:
    """Scrape invoice history from Iberdrola portal. Returns (data_dict, source_label)."""
    username = os.getenv("IBERDROLA_USERNAME", "")
    password = os.getenv("IBERDROLA_PASSWORD", "")

    if not username or not password:
        print("  [!] Credenciales no configuradas. Usando datos demo.")
        return _demo_invoices(), "Demo"

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                locale="es-ES",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            print("  [→] Abriendo formulario de login de Iberdrola...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

            # Aceptar cookies si aparece el banner
            try:
                page.locator(
                    "#onetrust-accept-btn-handler, button:has-text('Aceptar todo'), button:has-text('Aceptar')"
                ).first.click(timeout=6000)
                page.wait_for_timeout(800)
            except Exception:
                pass

            # Esperar a que el formulario esté listo
            page.wait_for_selector("input[type='text'], input[type='email'], input[name*='user'], input[id*='user']", timeout=15000)

            # Rellenar usuario y contraseña
            print(f"  [→] Iniciando sesión como {username}...")
            page.fill(
                "input[type='text'], input[type='email'], input[name*='user'], input[id*='user'], input[id*='email']",
                username,
            )
            page.fill(
                "input[type='password'], input[name*='pass'], input[id*='pass']",
                password,
            )

            # Enviar formulario
            page.locator("button[type='submit'], input[type='submit'], button:has-text('Entrar'), button:has-text('Acceder')").first.click()

            # Esperar a que complete el login
            page.wait_for_load_state("networkidle", timeout=25000)
            page.wait_for_timeout(2000)

            # Navegar a histórico de facturas
            print("  [→] Navegando a histórico de facturas...")
            page.goto(INVOICES_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            invoices = _extract_invoices(page)
            cups = _extract_cups(page)
            browser.close()

        if not invoices:
            raise ValueError("No se encontraron facturas en la página.")

        print(f"  [✓] {len(invoices)} facturas obtenidas de Iberdrola.")
        return {"cups": cups, "invoices": invoices, "total_facturas": len(invoices)}, "Iberdrola"

    except ImportError:
        print("  [!] Playwright no instalado. Ejecuta:")
        print("      pip install playwright && playwright install chromium")
        return _demo_invoices(), "Demo"
    except Exception as e:
        print(f"  [!] Error scraping Iberdrola: {e}. Usando datos demo.")
        return _demo_invoices(), "Demo"


def _extract_invoices(page) -> list[dict]:
    """Extract invoice rows from the historico-facturas page."""
    try:
        page.wait_for_selector(
            "table tr, .factura, [class*='factura'], [class*='invoice']",
            timeout=10000,
        )
    except Exception:
        pass

    raw = page.evaluate("""() => {
        const results = [];
        const rows = document.querySelectorAll('table tbody tr');
        rows.forEach(row => {
            const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
            if (cells.length >= 2) results.push({type: 'row', cells});
        });
        const cards = document.querySelectorAll('[class*="factura"],[class*="invoice"],[class*="bill"]');
        cards.forEach(el => {
            if (!el.querySelector('[class*="factura"],[class*="invoice"]')) {
                results.push({type: 'card', text: el.innerText.trim()});
            }
        });
        return results;
    }""")

    invoices = []
    for item in raw:
        parsed = _parse_invoice_item(item)
        if parsed:
            invoices.append(parsed)
    return invoices


def _parse_invoice_item(item: dict) -> dict | None:
    date_pat = re.compile(r"(\d{2})[/-](\d{2})[/-](\d{4})")
    money_pat = re.compile(r"(\d+[.,]\d{2})\s*€?")
    kwh_pat = re.compile(r"(\d+[.,]?\d*)\s*kWh", re.IGNORECASE)

    text = " | ".join(item.get("cells", [])) if item.get("type") == "row" else item.get("text", "")
    if not text.strip():
        return None

    dates = date_pat.findall(text)
    amounts = money_pat.findall(text)
    kwh = kwh_pat.findall(text)

    if not dates and not amounts:
        return None

    def fmt(d, m, y):
        return f"{y}-{m}-{d}"

    return {
        "fecha": fmt(*dates[0]) if dates else "",
        "periodo_hasta": fmt(*dates[0]) if dates else "",
        "periodo_desde": fmt(*dates[1]) if len(dates) > 1 else "",
        "importe": float(amounts[0].replace(",", ".")) if amounts else 0.0,
        "consumo_kwh": float(kwh[0].replace(",", ".")) if kwh else 0.0,
        "texto_raw": text[:200],
    }


def _extract_cups(page) -> str:
    try:
        result = page.evaluate("""() => {
            for (const el of document.querySelectorAll('*')) {
                if (!el.children.length && /ES\\d{16,20}/.test(el.innerText || '')) {
                    return (el.innerText.match(/ES\\d{16,20}/) || [''])[0];
                }
            }
            return '';
        }""")
        return result or os.getenv("IBERDROLA_CUPS", "N/D")
    except Exception:
        return os.getenv("IBERDROLA_CUPS", "N/D")


def _demo_invoices() -> dict:
    return {
        "cups": "ES0021000000000000XX",
        "total_facturas": 6,
        "invoices": [
            {"fecha": "2025-04-15", "periodo_desde": "2025-03-15", "periodo_hasta": "2025-04-15", "importe": 78.42,  "consumo_kwh": 210.5},
            {"fecha": "2025-03-14", "periodo_desde": "2025-02-12", "periodo_hasta": "2025-03-14", "importe": 95.10,  "consumo_kwh": 285.0},
            {"fecha": "2025-02-13", "periodo_desde": "2025-01-14", "periodo_hasta": "2025-02-13", "importe": 112.38, "consumo_kwh": 340.2},
            {"fecha": "2025-01-15", "periodo_desde": "2024-12-13", "periodo_hasta": "2025-01-15", "importe": 124.90, "consumo_kwh": 378.8},
            {"fecha": "2024-12-12", "periodo_desde": "2024-11-13", "periodo_hasta": "2024-12-12", "importe": 105.65, "consumo_kwh": 312.4},
            {"fecha": "2024-11-14", "periodo_desde": "2024-10-15", "periodo_hasta": "2024-11-14", "importe": 82.30,  "consumo_kwh": 228.7},
        ],
    }
