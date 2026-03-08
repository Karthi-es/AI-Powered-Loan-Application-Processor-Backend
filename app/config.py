#Loads configs from YAML, validate with pydantic, enforce business rules
#cache the final config, the app reads and reuses it.
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ScoringConfig(BaseModel):
	income_verification_weight: float = Field(ge=0, le=100)
	income_level_weight: float = Field(ge=0, le=100)
	account_stability_weight: float = Field(ge=0, le=100)
	employment_status_weight: float = Field(ge=0, le=100)
	debt_to_income_weight: float = Field(ge=0, le=100)

	def total_weight(self) -> float:
		return (
			self.income_verification_weight
			+ self.income_level_weight
			+ self.account_stability_weight
			+ self.employment_status_weight
			+ self.debt_to_income_weight
		)


class ThresholdConfig(BaseModel):
	auto_approve: float = Field(ge=0, le=100)
	manual_review: float = Field(ge=0, le=100)


class DisbursementConfig(BaseModel):
	webhook_timeout_seconds: int = Field(gt=0)
	retry_attempts: int = Field(ge=0)
	retry_delay_seconds: int = Field(ge=0)
	escalate_to_manual_review_after_seconds: int = Field(gt=0)


class DatabaseConfig(BaseModel):
	url: str


class AdminConfig(BaseModel):
	username: str
	password: str


class AppConfig(BaseModel):
	scoring: ScoringConfig
	thresholds: ThresholdConfig
	income_tolerance: float = Field(ge=0, le=1)
	disbursement: DisbursementConfig
	duplicate_window_minutes: int = Field(gt=0)
	database: DatabaseConfig
	admin: AdminConfig


def _read_yaml(config_path: Path) -> dict[str, Any]:
	if not config_path.exists():
		raise FileNotFoundError(f"Config file not found: {config_path}")

	with config_path.open("r", encoding="utf-8") as file:
		data = yaml.safe_load(file) or {}

	if not isinstance(data, dict):
		raise ValueError("Config root must be a mapping/object.")
	return data


def _validate_cross_field_rules(config: AppConfig) -> None:
	if round(config.scoring.total_weight(), 6) != 100.0:
		raise ValueError("Scoring weights must add up to 100.")

	if config.thresholds.manual_review >= config.thresholds.auto_approve:
		raise ValueError("manual_review threshold must be less than auto_approve.")

	if (
		config.disbursement.escalate_to_manual_review_after_seconds
		< config.disbursement.webhook_timeout_seconds
	):
		raise ValueError(
			"escalate_to_manual_review_after_seconds must be greater than or equal to webhook_timeout_seconds."
		)


def load_config(config_path: str | Path | None = None) -> AppConfig:
	resolved_path = (
		Path(config_path)
		if config_path is not None
		else Path(__file__).resolve().parent.parent / "config.yaml"
	)

	raw = _read_yaml(resolved_path)
	config = AppConfig(**raw)
	_validate_cross_field_rules(config)
	return config


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
	return load_config()
