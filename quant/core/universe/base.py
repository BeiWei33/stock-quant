from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class Universe(ABC):
    universe_id = "base"

    @abstractmethod
    def get_universe(self, trade_date: date, stocks: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
