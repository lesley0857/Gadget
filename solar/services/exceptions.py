# solar/services/exceptions.py


class SolarEngineeringError(Exception):
    """Base exception for all solar engineering calculations."""


class InvalidDesignInput(SolarEngineeringError):
    """Raised when the user provides invalid design input."""


class MissingDesignInput(SolarEngineeringError):
    """Raised when required design data is missing."""


class IncompatibleEquipment(SolarEngineeringError):
    """Raised when equipment cannot operate together."""


class InsufficientEquipment(SolarEngineeringError):
    """Raised when the equipment database contains no suitable option."""


class EngineeringConstraintError(SolarEngineeringError):
    """Raised when an engineering rule cannot be satisfied."""


class UnsupportedOperatingMode(SolarEngineeringError):
    """Raised when an unsupported operating mode is requested."""