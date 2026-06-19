from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Factor(ABC):
    name = ""
    version = "v1"

    @abstractmethod
    def calculate(self, bars: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
