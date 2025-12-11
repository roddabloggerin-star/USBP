# src/chart_utils.py
from __future__ import annotations
import io
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import math

# plotting libs
import matplotlib
matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Defensive helpers ---------------------------------------------------------

def _parse_hourly_periods(periods: List[Dict[str, Any]], max_hours: int = 24) -> pd.DataFrame:
    """
    Accepts NWS hourly 'periods' list and returns a DataFrame with:
      - dt (datetime UTC)
      - temp (int/float)
      - is_day (bool)
      - precip_prob (int 0-100) if available
      - snow_amount (float) if available (defensive)
    """
    rows = []
    for i, p in enumerate(periods):
        if i >= max_hours:
            break
        start = p.get("startTime") or p.get("start") or p.get("timestamp")
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except Exception:
            # fallback: skip row if no parseable time
            continue

        temp = p.get("temperature")
        # some NWS variants put temperature as dict; handle that
        if isinstance(temp, dict):
            temp_val = temp.get("value")
        else:
            temp_val = temp

        try:
            temp_val = float(temp_val) if temp_val is not None else None
        except Exception:
            temp_val = None

        precip = None
        # probabilityOfPrecipitation in NWS hourly is often an object
        pop = p.get("probabilityOfPrecipitation") or p.get("probabilityOfPrecip")
        if isinstance(pop, dict):
            try:
                precip = int(pop.get("value") or pop.get("amount") or 0)
            except Exception:
                precip = None
        else:
            try:
                precip = int(pop) if pop is not None else None
            except Exception:
                precip = None

        # Snow amount (defensive; many feeds don't include this)
        snow_val = None
        # look for properties like "snowProbability" or "snowAmount"
        snow = p.get("snowAmount") or p.get("snow") or p.get("iceAccumulation")
        if isinstance(snow, dict):
            try:
                snow_val = float(snow.get("value") or 0.0)
            except Exception:
                snow_val = None
        else:
            try:
                snow_val = float(snow) if snow is not None else None
            except Exception:
                snow_val = None

        rows.append({
            "dt": dt,
            "temp": temp_val,
            "is_day": p.get("isDaytime", False),
            "pop": precip,
            "snow": snow_val,
            "shortForecast": p.get("shortForecast") or "",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("dt").reset_index(drop=True)
    return df

def _fig_to_base64_png(fig, dpi=100) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    b = base64.b64encode(buf.read()).decode("utf-8")
    return b

# Chart generators ----------------------------------------------------------

def make_temp_minmax_chart(df: pd.DataFrame, zone_name: str = "") -> Optional[str]:
    """Generates a compact min/max temperature box + values summary (PNG base64)."""
    if df.empty or "temp" not in df or df["temp"].dropna().empty:
        return None

    temps = df["temp"].dropna()
    tmin = temps.min()
    tmax = temps.max()
    tmean = temps.mean()

    fig, ax = plt.subplots(figsize=(6, 2.2))
    ax.set_title(f"{zone_name} — 24h Temp Summary (°C)")
    # Simple horizontal bar indicating range
    ax.hlines(1, tmin, tmax, linewidth=8)
    ax.plot([tmin, tmax, tmean], [1, 1, 1], marker='o', markersize=6)
    ax.text(tmin, 1.08, f"Min: {tmin:.0f}°", ha='center', va='bottom', fontsize=8)
    ax.text(tmax, 1.08, f"Max: {tmax:.0f}°", ha='center', va='bottom', fontsize=8)
    ax.text(tmean, 0.9, f"Avg: {tmean:.0f}°", ha='center', va='top', fontsize=8)
    ax.set_yticks([])
    ax.set_xlabel("Temperature (°C)")
    ax.grid(axis='x', linestyle=':', linewidth=0.6)
    fig.tight_layout()

    return _fig_to_base64_png(fig)

def make_temp_line_chart(df: pd.DataFrame, zone_name: str = "") -> Optional[str]:
    """Generates a line chart of temperature for the next 24 hours (PNG base64)."""
    if df.empty or "temp" not in df or df["temp"].dropna().empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(df["dt"], df["temp"], marker='o')
    ax.set_title(f"{zone_name} — Temperature Next 24 Hours (°C)")
    ax.set_ylabel("°C")
    ax.set_xlabel("UTC hour")
    ax.grid(True, linestyle=':', linewidth=0.6)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    return _fig_to_base64_png(fig)

def make_precip_chart(df: pd.DataFrame, zone_name: str = "") -> Optional[str]:
    """Bar chart of hourly precip probability (POP) for the next 24 hours."""
    if df.empty or "pop" not in df or df["pop"].dropna().empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.bar(df["dt"], df["pop"], width=0.03)
    ax.set_title(f"{zone_name} — Hourly Precip Probability (%)")
    ax.set_ylabel("%")
    ax.set_xlabel("UTC hour")
    ax.set_ylim(0, 100)
    ax.grid(axis='y', linestyle=':', linewidth=0.6)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    return _fig_to_base64_png(fig)

def make_snow_chart(df: pd.DataFrame, zone_name: str = "") -> Optional[str]:
    """Bar chart of hourly snow accumulation (if present)."""
    if df.empty or "snow" not in df or df["snow"].dropna().empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.bar(df["dt"], df["snow"], width=0.03)
    ax.set_title(f"{zone_name} — Hourly Snow / Ice Accumulation")
    ax.set_ylabel("mm (or units reported)")
    ax.set_xlabel("UTC hour")
    ax.grid(axis='y', linestyle=':', linewidth=0.6)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    return _fig_to_base64_png(fig)

# Public entry --------------------------------------------------------------

def build_inline_charts_html(
    periods: List[Dict[str, Any]],
    zone_name: str = "Zone",
    max_hours: int = 24,
    include_map_placeholder: bool = False,
    placeholder_html: Optional[str] = None,
) -> str:
    """
    Main entry:
      - periods: NWS hourly periods array (as used elsewhere in your project)
      - returns a single HTML string with multiple <img> tags (base64) ready to inject
    Notes:
      - if include_map_placeholder True and placeholder_html provided, it is prepended.
      - Images are rendered inline with small caption text.
    """
    df = _parse_hourly_periods(periods, max_hours=max_hours)
    imgs = []

    # order: minmax summary, temp line, precip, snow (if exists)
    b = make_temp_minmax_chart(df, zone_name)
    if b:
        imgs.append(("24h Temp Summary", b))

    b = make_temp_line_chart(df, zone_name)
    if b:
        imgs.append(("Temp Next 24h", b))

    b = make_precip_chart(df, zone_name)
    if b:
        imgs.append(("Precip Probability (24h)", b))

    b = make_snow_chart(df, zone_name)
    if b:
        imgs.append(("Snow / Ice (24h)", b))

    # Build HTML
    parts = []
    if include_map_placeholder and placeholder_html:
        parts.append(placeholder_html)

    for caption, b64 in imgs:
        # Note: avoid very large inline images by using moderate DPI above
        img_tag = f'<div style="margin-bottom:12px;text-align:center;">' \
                  f'<img src="data:image/png;base64,{b64}" alt="{caption}" style="max-width:100%;height:auto;border-radius:6px;"/>' \
                  f'<div style="font-size:0.8em;color:#666;margin-top:6px;">{caption}</div>' \
                  f'</div>'
        parts.append(img_tag)

    if not parts:
        # fallback small message if nothing generated
        parts.append('<p style="color:#666;font-size:0.9em;">Charts unavailable (insufficient hourly data).</p>')

    return "\n".join(parts)
