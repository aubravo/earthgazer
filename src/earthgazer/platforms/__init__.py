from abc import ABC
from abc import abstractmethod

import earthgazer.definitions


class Band:
    def __init__(self, name: str, description: str | None, wavelength: float | None, resolution: float | None):
        self.name = name
        self.description = description
        self.wavelength = wavelength
        self.resolution = resolution

    def __repr__(self):
        return f"{self.name}({self.description})"


class Platform(ABC):
    name: str
    bigquery_attribute_mapping: dict
    bands: list[Band]
    athmospheric_reference_level: str

    def get_band_by_name(self, name: str) -> Band:
        for band in self.bands:
            if band.name == name:
                return band
        raise ValueError(f"Band {name} not found in {self.name}")

    @abstractmethod
    def calculate_radiometric_measure(**kwargs) -> earthgazer.definitions.RadiometricMeasure:
        pass

    @abstractmethod
    def calculate_athmospheric_reference_level(**kwargs) -> earthgazer.definitions.AtmosphericReferenceLevel:
        pass
