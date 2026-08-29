# solar/services/constants.py

from decimal import Decimal


# ================================================================
# OPERATING MODES
# ================================================================

OFF_GRID = "off_grid"
HYBRID = "hybrid"
GRID_TIED = "grid_tied"

OPERATING_MODES = (
    OFF_GRID,
    HYBRID,
    GRID_TIED,
)


# ================================================================
# STANDARD SYSTEM VOLTAGE CLASSES
# ================================================================

SYSTEM_VOLTAGE_CLASSES = (
    Decimal("12"),
    Decimal("24"),
    Decimal("48"),
    Decimal("96"),
    Decimal("192"),
    Decimal("384"),
)


# ================================================================
# NOMINAL BATTERY VOLTAGES
# ================================================================

LEAD_ACID_NOMINAL_VOLTAGES = (
    Decimal("12"),
    Decimal("24"),
    Decimal("48"),
    Decimal("96"),
    Decimal("192"),
)

LITHIUM_NOMINAL_VOLTAGES = (
    Decimal("12.8"),
    Decimal("25.6"),
    Decimal("51.2"),
    Decimal("102.4"),
    Decimal("204.8"),
)


# ================================================================
# BATTERY TYPES
# ================================================================

BATTERY_LEAD_ACID = "lead_acid"
BATTERY_LITHIUM = "lithium"

BATTERY_TYPES = (
    BATTERY_LEAD_ACID,
    BATTERY_LITHIUM,
)


# ================================================================
# DEFAULT ENGINEERING FACTORS
# ================================================================

DEFAULT_PERFORMANCE_RATIO = Decimal("0.75")

DEFAULT_INVERTER_EFFICIENCY = Decimal("0.95")

DEFAULT_CONTROLLER_EFFICIENCY = Decimal("0.98")

DEFAULT_LITHIUM_DOD = Decimal("0.95")

DEFAULT_LEAD_ACID_DOD = Decimal("0.50")

DEFAULT_FUTURE_EXPANSION_FACTOR = Decimal("1.20")

DEFAULT_BATTERY_EFFICIENCY = Decimal("0.90")


# ================================================================
# DESIGN SAFETY FACTORS
# ================================================================

INVERTER_CONTINUOUS_MARGIN = Decimal("1.25")

INVERTER_SURGE_MARGIN = Decimal("1.10")

CONTROLLER_CURRENT_MARGIN = Decimal("1.25")

PV_RESERVE_FACTOR = Decimal("1.10")


# ================================================================
# ELECTRICAL CONSTANTS
# ================================================================

COPPER_RESISTIVITY = Decimal("0.0175")

ALUMINIUM_RESISTIVITY = Decimal("0.0282")


# ================================================================
# VOLTAGE DROP LIMITS
# ================================================================

MAX_PV_VOLTAGE_DROP = Decimal("0.03")

MAX_BATTERY_VOLTAGE_DROP = Decimal("0.02")

MAX_AC_VOLTAGE_DROP = Decimal("0.03")

MAX_EARTH_VOLTAGE_DROP = Decimal("0.05")


# ================================================================
# ROUNDING
# ================================================================

DECIMAL_PLACES = Decimal("0.01")

POWER_ROUNDING = Decimal("1")

CURRENT_ROUNDING = Decimal("0.01")

VOLTAGE_ROUNDING = Decimal("0.01")

ENERGY_ROUNDING = Decimal("0.01")
