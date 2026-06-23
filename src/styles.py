import numpy as np

EUROPE_EXTENT = [-15, 40, 30, 72]

FIGSIZE = (14, 9)
DPI = 600

MAP_AXES = [0.06, 0.10, 0.76, 0.76]
COLORBAR_AXES = [0.86, 0.20, 0.025, 0.56]

T850_CMAP = "RdYlBu_r"

LAND_ALPHA = 0.15
OCEAN_ALPHA = 0.10

COASTLINE_RESOLUTION = "50m"
COASTLINE_WIDTH = 0.8
BORDER_WIDTH = 0.4

GRIDLINE_WIDTH = 0.3
GRIDLINE_ALPHA = 0.5
GRIDLINE_STYLE = "--"

T850_CONTOUR_LINEWIDTH = 0.45
Z500_CONTOUR_LINEWIDTH = 1.2

TITLE_FONTSIZE = 16
TITLE_FONTSIZE_LONG = 15
COLORBAR_LABEL_FONTSIZE = 11
CONTOUR_LABEL_FONTSIZE = 8

MSLP_CONTOUR_LINEWIDTH = 0.9

# 250 hPa jet stream styling
JET250_CMAP = "viridis"
JET250_FILL_LEVELS_MS = list(range(10, 75, 5))
JET250_CONTOUR_LEVELS_MS = [20, 30, 40, 50, 60, 70]
JET250_CORE_LEVELS_MS = [50, 60, 70]
JET250_CONTOUR_LINEWIDTH = 0.7
JET250_CORE_LINEWIDTHS = [1.5, 2.0, 2.5]
JET250_VECTOR_SKIP = 15
JET250_SHOW_BARBS = False


# Precipitable water styling
PWAT_CMAP = "YlGnBu"
PWAT_FILL_LEVELS_MM = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60]
PWAT_CONTOUR_LEVELS_MM = [20, 30]
PWAT_HIGH_LEVELS_MM = [40, 50]
PWAT_CONTOUR_LINEWIDTH = 0.7
PWAT_HIGH_LINEWIDTHS = [2.0, 3.0]


# CAPE / CIN styling
CAPE_CMAP = "YlOrRd"
CAPE_FILL_LEVELS_JKG = [
    0, 100, 250, 500,
    1000, 1500, 2000,
    3000, 4000,
]

CAPE_CONTOUR_LEVELS_JKG = [500, 1000]
CAPE_HIGH_LEVELS_JKG = [2000, 3000]
CAPE_CONTOUR_LINEWIDTH = 0.7
CAPE_HIGH_LINEWIDTHS = [1.6, 2.4]

CIN_HATCH_LEVELS_JKG = [0, 250, 10000]
CIN_HATCHES = [None, "////"]

# Precipitation levels
#
# Fixed meteorological thresholds keep maps comparable between runs.
# The upper end is extended automatically when a forecast exceeds the
# predefined range, so extreme cases are not clipped into one colour class.

PRECIP_BASE_LEVELS = [
    0.0,
    0.1,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    20.0,
    40.0,
    80.0,
]

PRECIP_ACCUM_BASE_LEVELS = [
    0.0,
    0.5,
    2.0,
    5.0,
    10.0,
    20.0,
    40.0,
    80.0,
    150.0,
]

PRECIP_EXTRA_LEVELS = [
    100.0,
    150.0,
    200.0,
    300.0,
    500.0,
    750.0,
    1000.0,
    1500.0,
    2000.0,
]


def finite_field_max(field) -> float:
    """Return finite maximum of an xarray-like field; 0.0 for empty/all-NaN."""
    try:
        values = np.asarray(field.values, dtype=float)
    except AttributeError:
        values = np.asarray(field, dtype=float)

    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0
    return float(np.nanmax(finite))


def build_adaptive_levels(
    max_value: float,
    base_levels: list[float],
    *,
    fallback_step: float = 100.0,
) -> list[float]:
    """Build strictly increasing contour levels with adaptive upper bound."""
    levels = [float(level) for level in base_levels]

    if not np.isfinite(max_value) or max_value <= levels[-1]:
        return levels

    for level in PRECIP_EXTRA_LEVELS:
        level = float(level)
        if level <= levels[-1]:
            continue
        levels.append(level)
        if level >= max_value:
            return levels

    upper = float(np.ceil(max_value / fallback_step) * fallback_step)
    if upper <= levels[-1]:
        upper = levels[-1] + fallback_step
    levels.append(upper)
    return levels


def get_precip_levels(field) -> list[float]:
    """Adaptive contour levels for period precipitation [mm]."""
    return build_adaptive_levels(
        finite_field_max(field),
        PRECIP_BASE_LEVELS,
        fallback_step=100.0,
    )


def get_precip_accum_levels(field) -> list[float]:
    """Adaptive contour levels for cumulative precipitation [mm]."""
    return build_adaptive_levels(
        finite_field_max(field),
        PRECIP_ACCUM_BASE_LEVELS,
        fallback_step=100.0,
    )
