"""Plotly JSON figures and simple Three.js scene specs."""

import math

import plotly.graph_objects as go


def blackbody_spectrum_json(T_kelvin: float, lambda_min_nm: float = 100, lambda_max_nm: float = 3000, n: int = 120):
    """Planck law vs wavelength (nm), arbitrary scale."""
    h = 6.62607015e-34
    c = 2.99792458e8
    k = 1.380649e-23
    T = max(100.0, float(T_kelvin))

    lambdas_nm = [lambda_min_nm + (lambda_max_nm - lambda_min_nm) * i / (n - 1) for i in range(n)]
    intensities = []
    for lam_nm in lambdas_nm:
        lam = lam_nm * 1e-9
        x = (h * c) / (lam * k * T)
        if x > 700:
            intensities.append(0.0)
        else:
            b = (2 * h * c**2) / (lam**5 * (math.exp(x) - 1))
            intensities.append(b)

    m = max(intensities) or 1.0
    intensities = [v / m for v in intensities]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=lambdas_nm,
            y=intensities,
            mode="lines",
            name=f"T = {T:.0f} K",
            line=dict(color="#7c3aed", width=2),
        )
    )
    fig.update_layout(
        title=dict(text="Blackbody spectrum (normalized)", font=dict(size=16)),
        xaxis_title="Wavelength (nm)",
        yaxis_title="Relative intensity",
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1e293b",
        font=dict(color="#e2e8f0"),
        margin=dict(l=50, r=20, t=50, b=50),
    )
    return fig.to_plotly_json()


def orbit_demo_spec():
    """Minimal JSON for a sun + planet ring; consumed by Three.js front-end."""
    return {
        "bodies": [
            {"name": "star", "color": "#fbbf24", "radius": 0.35, "orbitRadius": 0, "speed": 0},
            {"name": "inner", "color": "#38bdf8", "radius": 0.08, "orbitRadius": 0.8, "speed": 1.2},
            {"name": "outer", "color": "#a78bfa", "radius": 0.1, "orbitRadius": 1.35, "speed": 0.75},
        ],
        "note": "Schematic; not to scale.",
    }
