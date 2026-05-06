"""Shared data types and column schemas — imported by both backends and data_manager."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class UserSettings:
    userName: str = ""
    investment: float = 0.0
    remainingAmount: float = 0.0
    taxPercentage: float = 0.0
    brokeragePercentage: float = 0.0
    dividendPercentage: float = 0.0
    sellProfitTarget: float = 3.0
    buyInDipThreshold: float = 2.5


USER_COLUMNS = [
    "userName",
    "investment",
    "remainingAmount",
    "taxPercentage",
    "brokeragePercentage",
    "dividendPercentage",
    "sellProfitTarget",
    "buyInDipThreshold",
]

HOLDING_COLUMNS = [
    "id",
    "etfName",
    "etfType",
    "averagePrice",
    "lastPurchasePrice",
    "totalQuantity",
    "lastPurchaseDate",
]

SELL_COLUMNS = [
    "id",
    "etfName",
    "etfType",
    "quantity",
    "averagePurchasePrice",
    "sellPrice",
    "brokerageCharges",
    "tax",
    "dividendPaidToSelf",
    "lastPurchaseDate",
    "sellDate",
]

BUY_COLUMNS = [
    "id",
    "holdingId",
    "etfName",
    "etfType",
    "quantity",
    "price",
    "brokerageCharges",
    "tax",
    "totalCharges",
    "buyDate",
]

ETF_COLUMNS = [
    "etfCode",
    "name",
    "cmp",
    "the20Dma",
    "change20DmaVsCmp",
    "changePercentage",
    "dailyAverageVolumeInLast30Days",
    "dailyAverageVolumeInLast90Days",
    "dailyAverageVolumeInLast365Days",
    "type",
]
