import os
import requests
from datetime import datetime, timedelta


def fetch_pvpc_prices(date: datetime = None) -> tuple[list[float], str]:
    """Fetch hourly PVPC prices from REE API. Returns (prices_kwh, source_label)."""
    if date is None:
        date = datetime.now()

    start = date.strftime("%Y-%m-%dT00:00")
    end = date.strftime("%Y-%m-%dT23:59")

    url = "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
    params = {
        "start_date": start,
        "end_date": end,
        "time_trunc": "hour",
        "geo_limit": "peninsula",
        "geo_ids": "8",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Navigate to PVPC values in the response structure
        included = data.get("included", [])
        pvpc_entry = next(
            (item for item in included if item.get("type") == "PVPC"),
            None,
        )

        if pvpc_entry is None:
            # Try alternative type name
            pvpc_entry = next(
                (item for item in included if "PVPC" in item.get("id", "").upper()),
                None,
            )

        if pvpc_entry is None and included:
            pvpc_entry = included[0]

        if pvpc_entry:
            values = pvpc_entry.get("attributes", {}).get("values", [])
            # REE returns prices in €/MWh, convert to €/kWh
            prices = [v["value"] / 1000 for v in values[:24]]
            if len(prices) == 24:
                return prices, "REE PVPC"

    except Exception:
        pass

    return _demo_pvpc_prices(), "Demo PVPC"


def _demo_pvpc_prices() -> list[float]:
    """Realistic Spanish PVPC hourly prices (€/kWh) with valley/peak structure."""
    return [
        0.052, 0.048, 0.045, 0.043, 0.041, 0.044,  # 00-05h (valle profundo)
        0.062, 0.098, 0.145, 0.178, 0.192, 0.185,  # 06-11h (punta mañana)
        0.165, 0.148, 0.139, 0.132, 0.128, 0.135,  # 12-17h (llano tarde)
        0.168, 0.195, 0.212, 0.198, 0.155, 0.089,  # 18-23h (punta noche)
    ]
