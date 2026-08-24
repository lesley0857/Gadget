# solar/services/load_engine.py

"""
Solar PV Load Analysis Engine.

Responsibilities
----------------
This engine is responsible ONLY for electrical load analysis.

It does NOT:
    - select system voltage
    - size batteries
    - size PV
    - select panels
    - select inverters
    - select charge controllers
    - size cables
    - select protection
    - calculate pricing

Those responsibilities belong to later engines.

Input
-----
A list of normalized load dictionaries.

Each load may contain:

{
    "appliance": Appliance instance,     # optional
    "name": "Refrigerator",
    "wattage": Decimal("150"),
    "quantity": 1,
    "hours_per_day": Decimal("10"),
    "surge_factor": Decimal("3"),
    "load_type": "compressor",
    "starting_type": "single",
}

Output
------
A standardized engine result dictionary.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import QuerySet

from ..models import Appliance
from .engineering import (
    build_result,
    make_json_safe,
    to_decimal,
    round_decimal,
)
from .exceptions import (
    InvalidDesignInput,
    MissingDesignInput,
)


# ================================================================
# CONSTANTS
# ================================================================

ZERO = Decimal("0")
ONE = Decimal("1")

MIN_HOURS_PER_DAY = Decimal("0")
MAX_HOURS_PER_DAY = Decimal("24")

MIN_QUANTITY = 1

VALID_LOAD_TYPES = {
    "resistive",
    "motor",
    "compressor",
    "electronics",
    "lighting",
}

VALID_STARTING_TYPES = {
    "single",
    "possible",
    "simultaneous",
}


# ================================================================
# LOAD ENGINE
# ================================================================

class LoadEngine:
    """
    Main load-analysis engine.
    """

    def __init__(self, loads=None):
        self.loads = loads or []

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(self):
        """
        Perform complete load analysis.
        """

        normalized_loads = self._normalize_loads()

        if not normalized_loads:
            raise MissingDesignInput(
                "At least one appliance/load is required."
            )

        load_rows = []

        for index, load in enumerate(normalized_loads, start=1):
            load_rows.append(
                self._calculate_load_row(
                    load,
                    index,
                )
            )

        totals = self._calculate_totals(load_rows)

        category_summary = self._calculate_category_summary(
            load_rows
        )

        starting_summary = self._calculate_starting_summary(
            load_rows
        )

        warnings = self._generate_warnings(
            load_rows,
            totals,
        )

        result = build_result(
            status="ok",
            inputs={
                "load_count": len(load_rows),
            },
            calculations={
                "connected_load_w": totals["connected_load_w"],
                "daily_energy_wh": totals["daily_energy_wh"],
                "daily_energy_kwh": totals["daily_energy_kwh"],
                "running_peak_load_w": totals["running_peak_load_w"],
                "surge_peak_load_w": totals["surge_peak_load_w"],
                "peak_design_load_w": totals["peak_design_load_w"],
                "additional_surge_w": totals["additional_surge_w"],
                "average_daily_load_w": totals[
                    "average_daily_load_w"
                ],
                "load_factor": totals["load_factor"],
            },
            selected={
                "connected_load_w": totals["connected_load_w"],
                "daily_energy_wh": totals["daily_energy_wh"],
                "daily_energy_kwh": totals["daily_energy_kwh"],
                "peak_load_w": totals["peak_design_load_w"],
                "surge_load_w": totals["surge_peak_load_w"],
            },
            candidates=load_rows,
            warnings=warnings,
            messages=[
                "Load analysis completed successfully."
            ],
        )

        result["load_rows"] = load_rows
        result["category_summary"] = category_summary
        result["starting_summary"] = starting_summary

        return make_json_safe(result)

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_loads(self):
        """
        Normalize every load into a predictable internal structure.

        This method deliberately converts all engineering numbers
        to Decimal before calculations begin.
        """

        if isinstance(self.loads, QuerySet):
            loads = list(self.loads)

        elif isinstance(self.loads, (list, tuple)):
            loads = list(self.loads)

        else:
            raise InvalidDesignInput(
                "Loads must be a list, tuple, or QuerySet."
            )

        normalized = []

        for index, item in enumerate(loads, start=1):

            if isinstance(item, Appliance):
                normalized.append(
                    self._normalize_appliance(
                        appliance=item,
                        quantity=1,
                        hours_per_day=0,
                    )
                )

                continue

            if not isinstance(item, dict):
                raise InvalidDesignInput(
                    f"Load item {index} must be a dictionary "
                    f"or Appliance instance."
                )

            normalized.append(
                self._normalize_dictionary(
                    item,
                    index,
                )
            )

        return normalized

    # ============================================================
    # APPLIANCE NORMALIZATION
    # ============================================================

    def _normalize_appliance(
        self,
        appliance,
        quantity,
        hours_per_day,
    ):
        wattage = to_decimal(
            appliance.wattage
        )

        surge_factor = to_decimal(
            appliance.surge_factor,
            default=ONE,
        )

        return {
            "name": str(appliance.name),
            "wattage": wattage,
            "quantity": int(quantity),
            "hours_per_day": to_decimal(
                hours_per_day
            ),
            "surge_factor": surge_factor,
            "load_type": appliance.load_type,
            "starting_type": appliance.starting_type,
        }

    # ============================================================
    # DICTIONARY NORMALIZATION
    # ============================================================

    def _normalize_dictionary(
        self,
        item,
        index,
    ):
        appliance = item.get("appliance")

        if appliance is not None:

            if not isinstance(
                appliance,
                Appliance,
            ):
                raise InvalidDesignInput(
                    f"Load item {index}: appliance must be "
                    f"an Appliance instance."
                )

            name = item.get(
                "name",
                appliance.name,
            )

            wattage = item.get(
                "wattage",
                appliance.wattage,
            )

            surge_factor = item.get(
                "surge_factor",
                appliance.surge_factor,
            )

            load_type = item.get(
                "load_type",
                appliance.load_type,
            )

            starting_type = item.get(
                "starting_type",
                appliance.starting_type,
            )

        else:

            name = item.get(
                "name"
            )

            wattage = item.get(
                "wattage"
            )

            surge_factor = item.get(
                "surge_factor",
                ONE,
            )

            load_type = item.get(
                "load_type",
                "resistive",
            )

            starting_type = item.get(
                "starting_type",
                "single",
            )

        if not name:
            raise MissingDesignInput(
                f"Load item {index} has no appliance name."
            )

        if wattage is None:
            raise MissingDesignInput(
                f"{name}: wattage is required."
            )

        quantity = item.get(
            "quantity",
            1,
        )

        hours_per_day = item.get(
            "hours_per_day",
            0,
        )

        wattage = to_decimal(wattage)
        surge_factor = to_decimal(
            surge_factor,
            default=ONE,
        )

        quantity = int(quantity)

        hours_per_day = to_decimal(
            hours_per_day
        )

        self._validate_load_values(
            name=name,
            wattage=wattage,
            surge_factor=surge_factor,
            quantity=quantity,
            hours_per_day=hours_per_day,
            load_type=load_type,
            starting_type=starting_type,
        )

        return {
            "name": str(name),
            "wattage": wattage,
            "quantity": quantity,
            "hours_per_day": hours_per_day,
            "surge_factor": surge_factor,
            "load_type": load_type,
            "starting_type": starting_type,
        }

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_load_values(
        self,
        name,
        wattage,
        surge_factor,
        quantity,
        hours_per_day,
        load_type,
        starting_type,
    ):

        if wattage <= ZERO:
            raise InvalidDesignInput(
                f"{name}: wattage must be greater than zero."
            )

        if surge_factor < ONE:
            raise InvalidDesignInput(
                f"{name}: surge factor cannot be less than 1."
            )

        if quantity < MIN_QUANTITY:
            raise InvalidDesignInput(
                f"{name}: quantity must be at least 1."
            )

        if (
            hours_per_day < MIN_HOURS_PER_DAY
            or hours_per_day > MAX_HOURS_PER_DAY
        ):
            raise InvalidDesignInput(
                f"{name}: hours per day must be between "
                f"0 and 24."
            )

        if load_type not in VALID_LOAD_TYPES:
            raise InvalidDesignInput(
                f"{name}: unsupported load type "
                f"'{load_type}'."
            )

        if starting_type not in VALID_STARTING_TYPES:
            raise InvalidDesignInput(
                f"{name}: unsupported starting type "
                f"'{starting_type}'."
            )

    # ============================================================
    # ROW CALCULATION
    # ============================================================

    def _calculate_load_row(
        self,
        load,
        index,
    ):
        wattage = load["wattage"]
        quantity = load["quantity"]
        hours = load["hours_per_day"]
        surge_factor = load["surge_factor"]

        connected_power = (
            wattage
            * Decimal(quantity)
        )

        daily_energy = (
            connected_power
            * hours
        )

        surge_power = (
            connected_power
            * surge_factor
        )

        additional_surge = (
            surge_power
            - connected_power
        )

        return {
            "index": index,
            "name": load["name"],
            "wattage_w": round_decimal(
                wattage
            ),
            "quantity": quantity,
            "hours_per_day": round_decimal(
                hours
            ),
            "load_type": load["load_type"],
            "starting_type": load["starting_type"],
            "surge_factor": round_decimal(
                surge_factor
            ),
            "connected_power_w": round_decimal(
                connected_power
            ),
            "daily_energy_wh": round_decimal(
                daily_energy
            ),
            "daily_energy_kwh": round_decimal(
                daily_energy / Decimal("1000")
            ),
            "surge_power_w": round_decimal(
                surge_power
            ),
            "additional_surge_w": round_decimal(
                additional_surge
            ),
        }

    # ============================================================
    # TOTALS
    # ============================================================

    def _calculate_totals(
        self,
        rows,
    ):
        connected_load = sum(
            (
                to_decimal(
                    row["connected_power_w"]
                )
                for row in rows
            ),
            ZERO,
        )

        daily_energy = sum(
            (
                to_decimal(
                    row["daily_energy_wh"]
                )
                for row in rows
            ),
            ZERO,
        )

        # All loads are assumed capable of running together
        # for the conservative continuous design load.
        running_peak = connected_load

        additional_surge = (
            self._calculate_additional_surge(
                rows
            )
        )

        surge_peak = (
            running_peak
            + additional_surge
        )

        # Conservative design peak is the higher of:
        # running load or calculated surge condition.
        peak_design = max(
            running_peak,
            surge_peak,
        )

        average_daily_load = (
            daily_energy / Decimal("24")
        )

        if connected_load > ZERO:
            load_factor = (
                average_daily_load
                / connected_load
            )
        else:
            load_factor = ZERO

        return {
            "connected_load_w": round_decimal(
                connected_load
            ),
            "daily_energy_wh": round_decimal(
                daily_energy
            ),
            "daily_energy_kwh": round_decimal(
                daily_energy
                / Decimal("1000")
            ),
            "running_peak_load_w": round_decimal(
                running_peak
            ),
            "surge_peak_load_w": round_decimal(
                surge_peak
            ),
            "additional_surge_w": round_decimal(
                additional_surge
            ),
            "peak_design_load_w": round_decimal(
                peak_design
            ),
            "average_daily_load_w": round_decimal(
                average_daily_load
            ),
            "load_factor": round_decimal(
                load_factor
            ),
        }

    # ============================================================
    # SURGE CALCULATION
    # ============================================================

    def _calculate_additional_surge(
        self,
        rows,
    ):
        """
        Determine the additional starting surge.

        Strategy
        --------
        simultaneous:
            All additional surge contributions are included.

        possible:
            All additional surge contributions are included
            conservatively.

        single:
            Only the largest single additional surge is applied.

        This prevents several independent "single-start" loads
        from automatically being treated as simultaneous starts.
        """

        simultaneous_surge = ZERO
        possible_surge = ZERO
        largest_single_surge = ZERO

        for row in rows:

            additional = to_decimal(
                row["additional_surge_w"]
            )

            starting_type = row[
                "starting_type"
            ]

            if starting_type == "simultaneous":
                simultaneous_surge += additional

            elif starting_type == "possible":
                possible_surge += additional

            elif starting_type == "single":
                largest_single_surge = max(
                    largest_single_surge,
                    additional,
                )

        grouped_surge = (
            simultaneous_surge
            + possible_surge
        )

        return max(
            grouped_surge,
            largest_single_surge,
        )

    # ============================================================
    # CATEGORY SUMMARY
    # ============================================================

    def _calculate_category_summary(
        self,
        rows,
    ):
        summary = defaultdict(
            lambda: {
                "connected_power_w": ZERO,
                "daily_energy_wh": ZERO,
                "quantity": 0,
            }
        )

        for row in rows:

            category = row[
                "load_type"
            ]

            summary[category][
                "connected_power_w"
            ] += to_decimal(
                row["connected_power_w"]
            )

            summary[category][
                "daily_energy_wh"
            ] += to_decimal(
                row["daily_energy_wh"]
            )

            summary[category][
                "quantity"
            ] += row["quantity"]

        result = {}

        for category, values in summary.items():

            result[category] = {
                "connected_power_w": round_decimal(
                    values["connected_power_w"]
                ),
                "daily_energy_wh": round_decimal(
                    values["daily_energy_wh"]
                ),
                "daily_energy_kwh": round_decimal(
                    values["daily_energy_wh"]
                    / Decimal("1000")
                ),
                "quantity": values["quantity"],
            }

        return result

    # ============================================================
    # STARTING SUMMARY
    # ============================================================

    def _calculate_starting_summary(
        self,
        rows,
    ):
        summary = {
            "single": {
                "count": 0,
                "additional_surge_w": ZERO,
            },
            "possible": {
                "count": 0,
                "additional_surge_w": ZERO,
            },
            "simultaneous": {
                "count": 0,
                "additional_surge_w": ZERO,
            },
        }

        for row in rows:

            starting_type = row[
                "starting_type"
            ]

            summary[
                starting_type
            ]["count"] += 1

            summary[
                starting_type
            ]["additional_surge_w"] += to_decimal(
                row["additional_surge_w"]
            )

        for values in summary.values():
            values[
                "additional_surge_w"
            ] = round_decimal(
                values["additional_surge_w"]
            )

        return summary

    # ============================================================
    # WARNINGS
    # ============================================================

    def _generate_warnings(
        self,
        rows,
        totals,
    ):
        warnings = []

        if totals["daily_energy_wh"] <= ZERO:
            warnings.append(
                "Daily energy consumption is zero."
            )

        if totals["connected_load_w"] > ZERO:

            load_factor = to_decimal(
                totals["load_factor"]
            )

            if load_factor > ONE:
                warnings.append(
                    "Calculated load factor exceeds 100%. "
                    "Review appliance operating hours."
                )

        for row in rows:

            if row["hours_per_day"] if False else False:
                pass

        for row in rows:

            hours = to_decimal(
                row["hours_per_day"]
            )

            if hours >= Decimal("24"):
                warnings.append(
                    f"{row['name']} is configured to operate "
                    f"24 hours per day."
                )

            if row["surge_factor"] > Decimal("5"):
                warnings.append(
                    f"{row['name']} has a very high surge factor "
                    f"of {row['surge_factor']}."
                )

        return warnings


# ================================================================
# FUNCTION API
# ================================================================

def calculate_load(loads):
    """
    Functional API for the Load Engine.

    Example:

        result = calculate_load([
            {
                "name": "Refrigerator",
                "wattage": Decimal("150"),
                "quantity": 1,
                "hours_per_day": Decimal("10"),
                "surge_factor": Decimal("3"),
                "load_type": "compressor",
                "starting_type": "single",
            }
        ])
    """

    engine = LoadEngine(
        loads=loads
    )

    return engine.calculate()


# ================================================================
# APPLIANCE CATALOG HELPER
# ================================================================

def build_load_from_appliance(
    appliance,
    quantity,
    hours_per_day,
):
    """
    Convert an Appliance catalogue record plus user inputs
    into the normalized dictionary consumed by LoadEngine.
    """

    if not isinstance(
        appliance,
        Appliance,
    ):
        raise InvalidDesignInput(
            "appliance must be an Appliance instance."
        )

    quantity = int(quantity)

    hours_per_day = to_decimal(
        hours_per_day
    )

    if quantity < 1:
        raise InvalidDesignInput(
            "Quantity must be at least 1."
        )

    if (
        hours_per_day < ZERO
        or hours_per_day > Decimal("24")
    ):
        raise InvalidDesignInput(
            "Hours per day must be between 0 and 24."
        )

    return {
        "appliance": appliance,
        "quantity": quantity,
        "hours_per_day": hours_per_day,
    }