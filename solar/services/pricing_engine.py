from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List


# ======================================================================
# PRICING CONSTANTS
# ======================================================================

ZERO = Decimal("0")
HUNDRED = Decimal("100")

CURRENCY = "NGN"

ENGINE_NAME = "Solar Pricing Engine"
ENGINE_VERSION = "11.0.0"


DEFAULT_INSTALLATION_PERCENTAGE = Decimal("10")
DEFAULT_PROFIT_PERCENTAGE = Decimal("15")
DEFAULT_VAT_PERCENTAGE = Decimal("7.5")


# ======================================================================
# DECIMAL HELPERS
# ======================================================================

def _to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Safely convert a value to Decimal.

    Floats are converted through str() to avoid binary floating-point
    artefacts entering commercial calculations.
    """

    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return default


def _non_negative(
    value: Any,
) -> Decimal:
    """
    Return a non-negative Decimal.
    """

    number = _to_decimal(value)

    if number < ZERO:
        return ZERO

    return number


def _output_number(
    value: Any,
):
    """
    Convert Decimal into a JSON/template-safe number.
    """

    number = _to_decimal(value)

    if number == number.to_integral_value():
        return int(number)

    return float(number)


# ======================================================================
# SETTINGS
# ======================================================================

def _extract_pricing_settings(
    boq_result: Dict[str, Any],
) -> Dict[str, Decimal]:
    """
    Extract commercial pricing settings.

    Phase 11 receives the BOQ as its upstream contract.

    Preferred source:

        boq_result["settings"]

    Supported keys:

        installation_percentage
        profit_percentage
        vat_percentage

    The defaults match the current DesignSetting model.
    """

    settings = boq_result.get(
        "settings",
        {},
    )

    if not isinstance(settings, dict):
        settings = {}

    installation_percentage = _to_decimal(
        settings.get(
            "installation_percentage"
        ),
        DEFAULT_INSTALLATION_PERCENTAGE,
    )

    profit_percentage = _to_decimal(
        settings.get(
            "profit_percentage"
        ),
        DEFAULT_PROFIT_PERCENTAGE,
    )

    vat_percentage = _to_decimal(
        settings.get(
            "vat_percentage"
        ),
        DEFAULT_VAT_PERCENTAGE,
    )

    # Prevent negative commercial percentages.

    installation_percentage = max(
        installation_percentage,
        ZERO,
    )

    profit_percentage = max(
        profit_percentage,
        ZERO,
    )

    vat_percentage = max(
        vat_percentage,
        ZERO,
    )

    return {
        "installation_percentage":
            installation_percentage,

        "profit_percentage":
            profit_percentage,

        "vat_percentage":
            vat_percentage,
    }


# ======================================================================
# BOQ ITEM EXTRACTION
# ======================================================================

def _extract_boq_items(
    boq_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract the authoritative BOQ item schedule.

    Pricing does NOT rebuild engineering items.

    The Phase 10 BOQ is the single source of truth for:

        quantity
        unit
        unit price
        total price
        category
        description
        specification
        source
    """

    items = boq_result.get(
        "items",
        [],
    )

    if not isinstance(
        items,
        list,
    ):
        return []

    return [
        item
        for item in items
        if isinstance(
            item,
            dict,
        )
    ]


# ======================================================================
# CATEGORY NORMALIZATION
# ======================================================================

def _normalize_category(
    category: Any,
) -> str:
    """
    Normalize BOQ categories into the commercial pricing groups.

    Engineering categories remain visible in the BOQ.

    Pricing only needs three commercial groups:

        Material
        Labour
        Transport
    """

    value = str(
        category or ""
    ).strip().lower()

    if value in {
        "labour",
        "labor",
        "installation labour",
        "installation labor",
    }:
        return "labour"

    if value in {
        "transport",
        "logistics",
        "delivery",
        "transportation",
    }:
        return "transport"

    return "material"


# ======================================================================
# BUILD PRICING LINES FROM BOQ
# ======================================================================

def _build_pricing_lines(
    boq_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convert Phase 10 BOQ lines into the Phase 11 pricing schedule.

    IMPORTANT:

    Pricing does not create new engineering items.

    It only consumes the already-normalized BOQ.

    BOQ quantities are preserved exactly.
    """

    lines: List[Dict[str, Any]] = []

    for index, item in enumerate(
        boq_items,
        start=1,
    ):

        category = _normalize_category(
            item.get(
                "category"
            )
        )

        description = (
            item.get(
                "description"
            )
            or
            item.get(
                "name"
            )
            or
            f"BOQ Item {index}"
        )

        quantity = _non_negative(
            item.get(
                "quantity",
                ZERO,
            )
        )

        unit = (
            item.get(
                "unit"
            )
            or
            "pcs"
        )

        unit_price = _non_negative(
            item.get(
                "unit_price",
                item.get(
                    "price",
                    ZERO,
                ),
            )
        )

        # The BOQ already calculates total_price.
        #
        # Pricing preserves that value where available.
        #
        # If unavailable, calculate it from quantity × unit_price.

        supplied_total = item.get(
            "total_price"
        )

        if supplied_total is not None:

            total_price = _non_negative(
                supplied_total
            )

        else:

            total_price = (
                quantity
                * unit_price
            )

        lines.append(
            {
                "index": index,

                "category": category,

                "boq_category": item.get(
                    "category"
                ),

                "name": str(
                    description
                ),

                "description": str(
                    description
                ),

                "specification": (
                    item.get(
                        "specification",
                        "",
                    )
                    or
                    ""
                ),

                "quantity": (
                    quantity
                ),

                "unit": str(
                    unit
                ),

                "unit_price": (
                    unit_price
                ),

                "total_price": (
                    total_price
                ),

                "source": (
                    item.get(
                        "source",
                        "boq_engine",
                    )
                    or
                    "boq_engine"
                ),

                "reference": item.get(
                    "reference"
                ),

                "item_type": (
                    item.get(
                        "item_type",
                        "",
                    )
                    or
                    ""
                ),

                "notes": (
                    item.get(
                        "notes",
                        "",
                    )
                    or
                    ""
                ),
            }
        )

    return lines


# ======================================================================
# CATEGORY TOTALS
# ======================================================================

def _calculate_category_totals(
    lines: List[Dict[str, Any]],
) -> Dict[str, Decimal]:
    """
    Calculate commercial category totals from BOQ lines.
    """

    totals = {
        "material": ZERO,
        "labour": ZERO,
        "transport": ZERO,
    }

    for line in lines:

        category = line.get(
            "category",
            "material",
        )

        total_price = _non_negative(
            line.get(
                "total_price",
                ZERO,
            )
        )

        if category not in totals:
            category = "material"

        totals[
            category
        ] += total_price

    return totals


# ======================================================================
# BOQ CATEGORY SUMMARY
# ======================================================================

def _build_category_summary(
    lines: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a commercial category summary.

    The original BOQ engineering categories are retained separately
    through each line's boq_category.
    """

    material_lines = [
        line
        for line in lines
        if line["category"] == "material"
    ]

    labour_lines = [
        line
        for line in lines
        if line["category"] == "labour"
    ]

    transport_lines = [
        line
        for line in lines
        if line["category"] == "transport"
    ]

    def total(
        selected_lines,
    ):
        return sum(
            (
                _non_negative(
                    line.get(
                        "total_price",
                        ZERO,
                    )
                )
                for line in selected_lines
            ),
            ZERO,
        )

    return {
        "material": {
            "line_count": len(
                material_lines
            ),
            "total_price": _output_number(
                total(
                    material_lines
                )
            ),
        },

        "labour": {
            "line_count": len(
                labour_lines
            ),
            "total_price": _output_number(
                total(
                    labour_lines
                )
            ),
        },

        "transport": {
            "line_count": len(
                transport_lines
            ),
            "total_price": _output_number(
                total(
                    transport_lines
                )
            ),
        },
    }


# ======================================================================
# MAIN PHASE 11 ENGINE
# ======================================================================

def calculate_pricing(
    *,
    boq_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Complete Phase 11 Commercial Pricing Engine.

    CONTRACT
    --------

        calculate_pricing(
            boq_result=boq_result,
        )

    Phase 10 BOQ is the authoritative commercial input.

    Pricing does NOT receive:

        battery
        battery_qty
        panel
        panel_qty
        inverter
        controller
        cables
        protections
        accessories

    Those have already been consolidated by Phase 10.

    Pricing performs only commercial calculations:

        BOQ material cost
            ↓
        labour
            ↓
        transport
            ↓
        subtotal
            ↓
        installation
            ↓
        cost before profit
            ↓
        profit
            ↓
        discount
            ↓
        taxable amount
            ↓
        VAT
            ↓
        grand total
    """

    warnings: List[str] = []
    messages: List[str] = []

    # ==============================================================
    # VALIDATE BOQ RESULT
    # ==============================================================

    if boq_result is None:

        return {
            "success": False,
            "status": "missing_boq_result",
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "currency": CURRENCY,
            "items": [],
            "category_summary": {},
            "settings": {},
            "material_cost": 0,
            "labour_cost": 0,
            "transport_cost": 0,
            "subtotal": 0,
            "installation_cost": 0,
            "cost_before_profit": 0,
            "profit": 0,
            "discount": 0,
            "taxable_amount": 0,
            "vat": 0,
            "tax": 0,
            "grand_total": 0,
            "summary": {},
            "warnings": [
                "Pricing cannot be calculated because the "
                "BOQ result was not provided."
            ],
            "messages": [],
            "errors": [
                "boq_result is required."
            ],
            "message": (
                "Pricing could not be calculated because "
                "the BOQ result is missing."
            ),
        }

    if not isinstance(
        boq_result,
        dict,
    ):

        return {
            "success": False,
            "status": "invalid_boq_result",
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "currency": CURRENCY,
            "items": [],
            "category_summary": {},
            "settings": {},
            "material_cost": 0,
            "labour_cost": 0,
            "transport_cost": 0,
            "subtotal": 0,
            "installation_cost": 0,
            "cost_before_profit": 0,
            "profit": 0,
            "discount": 0,
            "taxable_amount": 0,
            "vat": 0,
            "tax": 0,
            "grand_total": 0,
            "summary": {},
            "warnings": [],
            "messages": [],
            "errors": [
                "boq_result must be a dictionary."
            ],
            "message": (
                "Pricing could not be calculated because "
                "the BOQ result is invalid."
            ),
        }

    # ==============================================================
    # CHECK BOQ SUCCESS
    # ==============================================================

    if boq_result.get(
        "success"
    ) is False:

        boq_message = boq_result.get(
            "message",
            "The BOQ engine did not complete successfully.",
        )

        return {
            "success": False,
            "status": "boq_failed",
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "currency": CURRENCY,
            "items": [],
            "category_summary": {},
            "settings": {},
            "material_cost": 0,
            "labour_cost": 0,
            "transport_cost": 0,
            "subtotal": 0,
            "installation_cost": 0,
            "cost_before_profit": 0,
            "profit": 0,
            "discount": 0,
            "taxable_amount": 0,
            "vat": 0,
            "tax": 0,
            "grand_total": 0,
            "summary": {},
            "warnings": [],
            "messages": [],
            "errors": [
                str(boq_message)
            ],
            "message": (
                "Pricing could not be calculated because "
                "the BOQ engine failed."
            ),
        }

    # ==============================================================
    # EXTRACT BOQ ITEMS
    # ==============================================================

    boq_items = _extract_boq_items(
        boq_result
    )

    if not boq_items:

        warnings.append(
            "The BOQ contains no pricing lines."
        )

    # ==============================================================
    # EXTRACT COMMERCIAL SETTINGS
    # ==============================================================

    commercial_settings = (
        _extract_pricing_settings(
            boq_result
        )
    )

    installation_percentage = (
        commercial_settings[
            "installation_percentage"
        ]
    )

    profit_percentage = (
        commercial_settings[
            "profit_percentage"
        ]
    )

    vat_percentage = (
        commercial_settings[
            "vat_percentage"
        ]
    )

    # ==============================================================
    # BUILD PRICING LINES
    # ==============================================================

    lines = _build_pricing_lines(
        boq_items
    )

    # ==============================================================
    # CATEGORY TOTALS
    # ==============================================================

    category_totals = (
        _calculate_category_totals(
            lines
        )
    )

    material_cost = (
        category_totals[
            "material"
        ]
    )

    labour_cost = (
        category_totals[
            "labour"
        ]
    )

    transport_cost = (
        category_totals[
            "transport"
        ]
    )

    # ==============================================================
    # DIRECT COST / SUBTOTAL
    # ==============================================================

    subtotal = (
        material_cost
        + labour_cost
        + transport_cost
    )

    # ==============================================================
    # INSTALLATION
    # ==============================================================

    installation_cost = (
        material_cost
        * installation_percentage
        / HUNDRED
    )

    # ==============================================================
    # COST BEFORE PROFIT
    # ==============================================================

    cost_before_profit = (
        subtotal
        + installation_cost
    )

    # ==============================================================
    # PROFIT
    # ==============================================================

    profit = (
        cost_before_profit
        * profit_percentage
        / HUNDRED
    )

    # ==============================================================
    # DISCOUNT
    # ==============================================================

    # Discount is deliberately zero at the engineering pricing
    # layer. A future quotation/commercial negotiation layer can
    # apply a customer-specific discount.

    discount = ZERO

    # ==============================================================
    # TAXABLE AMOUNT
    # ==============================================================

    taxable_amount = (
        cost_before_profit
        + profit
        - discount
    )

    if taxable_amount < ZERO:
        taxable_amount = ZERO

    # ==============================================================
    # VAT
    # ==============================================================

    vat = (
        taxable_amount
        * vat_percentage
        / HUNDRED
    )

    # ==============================================================
    # GRAND TOTAL
    # ==============================================================

    grand_total = (
        taxable_amount
        + vat
    )

    # ==============================================================
    # ZERO-PRICE WARNING
    # ==============================================================

    zero_price_items = []

    for line in lines:

        unit_price = _non_negative(
            line.get(
                "unit_price",
                ZERO,
            )
        )

        if unit_price <= ZERO:

            zero_price_items.append(
                line.get(
                    "name",
                    "Unnamed item",
                )
            )

    if zero_price_items:

        warnings.append(
            "The following BOQ items have zero unit price: "
            + ", ".join(
                zero_price_items
            )
        )

    # ==============================================================
    # PRESERVE BOQ WARNINGS
    # ==============================================================

    boq_warnings = boq_result.get(
        "warnings",
        [],
    )

    if isinstance(
        boq_warnings,
        list,
    ):

        for warning in boq_warnings:

            if warning not in warnings:
                warnings.append(
                    warning
                )

    # ==============================================================
    # SERIALIZE PRICING ITEMS
    # ==============================================================

    serialized_items = []

    for line in lines:

        serialized_items.append(
            {
                "index": line[
                    "index"
                ],

                "category": line[
                    "boq_category"
                ],

                "pricing_category": line[
                    "category"
                ],

                "name": line[
                    "name"
                ],

                "description": line[
                    "description"
                ],

                "specification": line[
                    "specification"
                ],

                "quantity": _output_number(
                    line[
                        "quantity"
                    ]
                ),

                "unit": line[
                    "unit"
                ],

                "unit_price": _output_number(
                    line[
                        "unit_price"
                    ]
                ),

                "total_price": _output_number(
                    line[
                        "total_price"
                    ]
                ),

                "source": line[
                    "source"
                ],

                "reference": line[
                    "reference"
                ],

                "item_type": line[
                    "item_type"
                ],

                "notes": line[
                    "notes"
                ],
            }
        )

    # ==============================================================
    # CATEGORY SUMMARY
    # ==============================================================

    category_summary = (
        _build_category_summary(
            lines
        )
    )

    # ==============================================================
    # COMMERCIAL MESSAGES
    # ==============================================================

    messages.append(
        "Solar design pricing calculated successfully."
    )

    messages.append(
        f"Installation allowance applied at "
        f"{_output_number(installation_percentage)}%."
    )

    messages.append(
        f"Profit margin applied at "
        f"{_output_number(profit_percentage)}%."
    )

    messages.append(
        f"VAT applied at "
        f"{_output_number(vat_percentage)}%."
    )

    # ==============================================================
    # FINAL SUMMARY
    # ==============================================================

    summary = {
        "item_count": len(
            serialized_items
        ),

        "material_cost": _output_number(
            material_cost
        ),

        "labour_cost": _output_number(
            labour_cost
        ),

        "transport_cost": _output_number(
            transport_cost
        ),

        "subtotal": _output_number(
            subtotal
        ),

        "installation_cost": _output_number(
            installation_cost
        ),

        "cost_before_profit": _output_number(
            cost_before_profit
        ),

        "profit": _output_number(
            profit
        ),

        "discount": _output_number(
            discount
        ),

        "taxable_amount": _output_number(
            taxable_amount
        ),

        "vat": _output_number(
            vat
        ),

        "grand_total": _output_number(
            grand_total
        ),
    }

    # ==============================================================
    # FINAL RESULT
    # ==============================================================

    return {
        "success": True,

        "status": "priced",

        "currency": CURRENCY,

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,

        # ----------------------------------------------------------
        # SOURCE
        # ----------------------------------------------------------

        "source": {
            "engine": "boq_engine",
            "boq_status": boq_result.get(
                "status"
            ),
            "boq_engine": boq_result.get(
                "engine"
            ),
            "boq_engine_version": boq_result.get(
                "engine_version"
            ),
        },

        # ----------------------------------------------------------
        # PRICING SCHEDULE
        # ----------------------------------------------------------

        "items": serialized_items,

        # ----------------------------------------------------------
        # CATEGORY SUMMARY
        # ----------------------------------------------------------

        "category_summary": category_summary,

        # ----------------------------------------------------------
        # COMMERCIAL SETTINGS
        # ----------------------------------------------------------

        "settings": {
            "installation_percentage":
                _output_number(
                    installation_percentage
                ),

            "profit_percentage":
                _output_number(
                    profit_percentage
                ),

            "vat_percentage":
                _output_number(
                    vat_percentage
                ),
        },

        # ----------------------------------------------------------
        # CORE TOTALS
        # ----------------------------------------------------------

        "material_cost":
            _output_number(
                material_cost
            ),

        "labour_cost":
            _output_number(
                labour_cost
            ),

        "transport_cost":
            _output_number(
                transport_cost
            ),

        "subtotal":
            _output_number(
                subtotal
            ),

        "installation_cost":
            _output_number(
                installation_cost
            ),

        "cost_before_profit":
            _output_number(
                cost_before_profit
            ),

        "profit":
            _output_number(
                profit
            ),

        "discount":
            _output_number(
                discount
            ),

        "taxable_amount":
            _output_number(
                taxable_amount
            ),

        "vat":
            _output_number(
                vat
            ),

        # Backward-compatible alias.
        "tax":
            _output_number(
                vat
            ),

        "grand_total":
            _output_number(
                grand_total
            ),

        # ----------------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------------

        "summary": summary,

        # ----------------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------------

        "warnings": warnings,

        "messages": messages,

        "errors": [],

        "message": (
            "Solar design pricing calculated successfully."
        ),
    }