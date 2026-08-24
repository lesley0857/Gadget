# solar/services/product_bridge.py
"""
Bridge between the marketplace's ProductListing (commercial data)
and the solar engineering Specification models (engineering data).

WHY THIS FILE EXISTS
---------------------
None of the 11 engineering engines needed to change. Every engine
already reads candidate attributes through either direct attribute
access (candidate.voltage, candidate.power, ...) or through flexible
helper functions (get_value(), get_price(), get_name() in
pricing_engine.py) that already tolerate model instances, dicts, or
getattr-style objects.

That means the correct integration point is NOT inside the engines.
It's a thin adapter that wraps a *Specification instance together
with its linked ProductListing, and exposes the attribute names the
engines have always expected:

    candidate.brand        -> product.brand
    candidate.model        -> product.model_number
    candidate.price        -> product.final_price()
    candidate.active       -> product.is_active
    candidate.id           -> product.id   (so BOQ/pricing "id" refs
                                             point at the sellable
                                             listing, not the spec row)

Every OTHER attribute (voltage, capacity_ah, vmp, isc, rated_power,
max_charge_current, size_mm, current_rating, ...) passes straight
through to the underlying Specification row via __getattr__, because
those fields did not move — they still live on the Specification
model exactly as before.

USAGE IN views.py
------------------
Replace:

    Battery.objects.filter(active=True)

with:

    from solar.services import product_bridge
    product_bridge.get_active_batteries()

Every other engine call site in run_design_pipeline() stays exactly
the same — it just receives a list of adapters instead of a
queryset of the old standalone models.
"""

from __future__ import annotations

from typing import Any, Iterable, List


# ==================================================================
# GENERIC ADAPTER
# ==================================================================

class ProductCandidate:
    """
    Wraps one Specification instance + its linked ProductListing.

    Presents the commercial fields the engines expect (brand, model,
    price, active, id) sourced from ProductListing, and transparently
    passes through every engineering field to the wrapped
    Specification instance.
    """

    # Commercial fields resolved from ProductListing. Override per
    # subclass only if a particular spec type needs different
    # mapping (none currently do).
    _price_source = "final_price"  # ProductListing.final_price()

    def __init__(self, spec: Any):
        # Avoid clashing with __getattr__ below.
        object.__setattr__(self, "_spec", spec)
        object.__setattr__(self, "_product", spec.product)

    # ----------------------------------------------------------------
    # COMMERCIAL FIELDS — sourced from ProductListing
    # ----------------------------------------------------------------

    @property
    def id(self):
        return self._product.id

    @property
    def pk(self):
        return self._product.pk

    @property
    def brand(self):
        return self._product.brand or self._product.manufacturer or ""

    @property
    def model(self):
        return self._product.model_number or ""

    @property
    def name(self):
        return self._product.name

    @property
    def price(self):
        # final_price() applies PricingRule / category margin logic.
        # If you prefer the cached value (faster, but only correct
        # after ProductListing.refresh_price() has been called),
        # swap this to `return self._product.cached_price`.
        try:
            return self._product.final_price()
        except Exception:
            return self._product.cached_price

    @property
    def unit_price(self):
        return self.price

    @property
    def active(self):
        return self._product.is_active

    @property
    def stock(self):
        return self._product.stock

    @property
    def vendor(self):
        return self._product.vendor

    @property
    def product_id(self):
        return self._product.id

    # ----------------------------------------------------------------
    # ENGINEERING FIELDS — pass through to the Specification row
    # ----------------------------------------------------------------

    def __getattr__(self, item):
        # Only called when normal attribute lookup fails, i.e. the
        # attribute isn't one of the commercial properties above.
        return getattr(self._spec, item)

    # ----------------------------------------------------------------
    # DICT-STYLE ACCESS (some engine helpers use get_value() which
    # checks isinstance(source, dict) first, then falls back to
    # getattr — no dict support needed here, but .get() is provided
    # defensively in case any call site does hasattr(x, "get")).
    # ----------------------------------------------------------------

    def __repr__(self):
        return f"<{type(self).__name__} product_id={self._product.id} name={self._product.name!r}>"


class BatteryCandidate(ProductCandidate):
    pass


class PanelCandidate(ProductCandidate):
    pass


class InverterCandidate(ProductCandidate):
    pass


class ControllerCandidate(ProductCandidate):
    pass


class CableCandidate(ProductCandidate):
    pass


class FuseCandidate(ProductCandidate):
    pass


class BreakerCandidate(ProductCandidate):
    pass


class SPDCandidate(ProductCandidate):
    pass


class IsolatorCandidate(ProductCandidate):
    pass


class MountingStructureCandidate(ProductCandidate):
    pass


class AccessoryCandidate(ProductCandidate):
    pass


# ==================================================================
# QUERY HELPERS
#
# Each function returns a plain list of adapters (not a QuerySet).
# select_related("product") avoids the N+1 query that would
# otherwise happen when each adapter accesses spec.product.
#
# require_stock: pass True to exclude out-of-stock listings from
# candidate selection. Defaults to False (stock is informational
# only, out-of-stock items can still be engineered/quoted). Flip the
# default here once you've decided your stock policy.
# ==================================================================

def _wrap(queryset, wrapper_cls, require_stock: bool) -> List[ProductCandidate]:
    queryset = queryset.select_related("product").filter(
        product__is_active=True,
    )

    if require_stock:
        queryset = queryset.filter(product__stock__gt=0)

    return [wrapper_cls(spec) for spec in queryset]


def get_active_batteries(require_stock: bool = False) -> List[BatteryCandidate]:
    from solar.models import BatterySpecification
    return _wrap(BatterySpecification.objects.all(), BatteryCandidate, require_stock)


def get_active_panels(require_stock: bool = False) -> List[PanelCandidate]:
    from solar.models import PanelSpecification
    return _wrap(PanelSpecification.objects.all(), PanelCandidate, require_stock)


def get_active_inverters(require_stock: bool = False) -> List[InverterCandidate]:
    from solar.models import InverterSpecification
    return _wrap(InverterSpecification.objects.all(), InverterCandidate, require_stock)


def get_active_controllers(require_stock: bool = False) -> List[ControllerCandidate]:
    from solar.models import ControllerSpecification
    return _wrap(ControllerSpecification.objects.all(), ControllerCandidate, require_stock)


def get_active_cables(require_stock: bool = False) -> List[CableCandidate]:
    from solar.models import CableSpecification
    return _wrap(CableSpecification.objects.all(), CableCandidate, require_stock)


def get_active_fuses(require_stock: bool = False) -> List[FuseCandidate]:
    from solar.models import FuseSpecification
    return _wrap(FuseSpecification.objects.all(), FuseCandidate, require_stock)


def get_active_breakers(require_stock: bool = False) -> List[BreakerCandidate]:
    from solar.models import BreakerSpecification
    return _wrap(BreakerSpecification.objects.all(), BreakerCandidate, require_stock)


def get_active_spds(require_stock: bool = False) -> List[SPDCandidate]:
    from solar.models import SPDSpecification
    return _wrap(SPDSpecification.objects.all(), SPDCandidate, require_stock)


def get_active_isolators(require_stock: bool = False) -> List[IsolatorCandidate]:
    from solar.models import IsolatorSpecification
    return _wrap(IsolatorSpecification.objects.all(), IsolatorCandidate, require_stock)


def get_active_mounting_structures(require_stock: bool = False) -> List[MountingStructureCandidate]:
    from solar.models import MountingStructureSpecification
    return _wrap(MountingStructureSpecification.objects.all(), MountingStructureCandidate, require_stock)


def get_active_accessories(require_stock: bool = False) -> List[AccessoryCandidate]:
    from solar.models import AccessorySpecification
    return _wrap(AccessorySpecification.objects.all(), AccessoryCandidate, require_stock)