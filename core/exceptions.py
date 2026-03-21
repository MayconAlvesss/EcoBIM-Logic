import logging

logger = logging.getLogger(__name__)


class AuraCoreException(Exception):
    """Base exception for all custom errors in the Aura Core engine."""
    pass


class VolumeCalculationError(AuraCoreException):
    """
    Raised when a BIM element has a negative, zero, or completely invalid volume.
    Usually caused by corrupted Revit geometry or boolean void cuts gone wrong.
    """
    def __init__(self, element_id: str, volume: float):
        self.element_id = element_id
        self.volume = volume
        self.message = (
            f"Corrupted geometry detected: Invalid volume ({volume} m3) "
            f"in Revit Element ID: {element_id}"
        )
        logger.error(self.message)
        super().__init__(self.message)


class MaterialNotFoundError(AuraCoreException):
    """
    Raised when Revit sends a material name/ID that doesn't exist in our SQLite database.
    Prevents the Pandas engine from silently failing during the join operation.
    """
    def __init__(self, material_id: str):
        self.material_id = material_id
        self.message = (
            f"Material '{material_id}' not found in the database. "
            "Please map it before processing."
        )
        logger.warning(self.message)
        super().__init__(self.message)


class DatabaseConnectionError(AuraCoreException):
    """
    Raised when the system cannot locate or connect to the SQLite materials database.
    Crucial for local deployments where file paths might get messed up.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.message = f"Critical Error: Could not connect to the database at {db_path}."
        logger.critical(self.message)
        super().__init__(self.message)


class InvalidPayloadError(AuraCoreException):
    """
    Raised when the JSON payload from Revit/API lacks required fields (like the elements array).
    """
    def __init__(self, missing_field: str):
        self.missing_field = missing_field
        self.message = (
            f"Malformed payload: Missing required field '{missing_field}' "
            "from the Revit sync."
        )
        logger.error(self.message)
        super().__init__(self.message)