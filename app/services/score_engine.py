from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import get_settings


@dataclass
class ScoreResult:
	income_verification_score: float
	income_level_score: float
	account_stability_score: float
	employment_status_score: float
	debt_to_income_score: float
	total_score: float
	decision: str
	reasoning: dict[str, Any]


class ScoreEngine:
	"""Computes application score using config-driven rubric weights and thresholds."""

	def __init__(self) -> None:
		self.settings = get_settings()

	def _income_verification_score(self, stated_income: float, documented_income: float | None) -> tuple[float, dict[str, Any]]:
		weight = self.settings.scoring.income_verification_weight
		tolerance = self.settings.income_tolerance

		if documented_income is None:
			return 0.0, {
				"stated_income": stated_income,
				"documented_income": None,
				"tolerance": tolerance,
				"interpretation": "symmetric_within_plus_minus_tolerance",
				"allowed_delta": None,
				"actual_delta": None,
				"passed": False,
				"missing_documentation": True,
			}

		# Deliberate ambiguity resolution: treat tolerance as symmetric (+/- 10% by default).
		# This is more robust for small reporting variance in either direction.
		if stated_income == 0:
			is_within_tolerance = documented_income == 0
			allowed_delta = 0.0
			actual_delta = abs(documented_income - stated_income)
		else:
			#main logic for +/- 10% tolerance - works for both ways.
			allowed_delta = abs(stated_income) * tolerance
			actual_delta = abs(documented_income - stated_income)
			is_within_tolerance = actual_delta <= allowed_delta

		score = weight if is_within_tolerance else 0.0
		return score, {
			"stated_income": stated_income,
			"documented_income": documented_income,
			"tolerance": tolerance,
			"interpretation": "symmetric_within_plus_minus_tolerance",
			"allowed_delta": allowed_delta,
			"actual_delta": actual_delta,
			"passed": is_within_tolerance,
		}

	def _income_level_score(self, loan_amount: float, documented_income: float | None) -> tuple[float, dict[str, Any]]:
		weight = self.settings.scoring.income_level_weight
		if documented_income is None:
			return 0.0, {
				"documented_income": None,
				"required_income": loan_amount * 3,
				"passed": False,
				"missing_documentation": True,
			}
		required_income = loan_amount * 3
		passed = documented_income >= required_income
		score = weight if passed else 0.0
		return score, {
			"documented_income": documented_income,
			"required_income": required_income,
			"passed": passed,
		}

	def _account_stability_score(
		self,
		bank_ending_balance: float | None,
		bank_has_overdrafts: bool | None,
		bank_has_consistent_deposits: bool | None,
	) -> tuple[float, dict[str, Any]]:
		weight = self.settings.scoring.account_stability_weight
		if (
			bank_ending_balance is None
			or bank_has_overdrafts is None
			or bank_has_consistent_deposits is None
		):
			return 0.0, {
				"positive_ending_balance": None,
				"no_overdrafts": None,
				"consistent_deposits": None,
				"passed_checks": 0,
				"total_checks": 3,
				"missing_documentation": True,
			}
		checks = [
			bank_ending_balance > 0,
			not bank_has_overdrafts,
			bank_has_consistent_deposits,
		]
		passed_checks = sum(1 for check in checks if check)
		score = (passed_checks / 3.0) * weight
		return score, {
			"positive_ending_balance": bank_ending_balance > 0,
			"no_overdrafts": not bank_has_overdrafts,
			"consistent_deposits": bank_has_consistent_deposits,
			"passed_checks": passed_checks,
			"total_checks": 3,
		}

	def _employment_status_score(self, employment_status: str) -> tuple[float, dict[str, Any]]:
		weight = self.settings.scoring.employment_status_weight
		normalized = employment_status.strip().lower()

		# ordered priority from rubric: employed > self-employed > unemployed
		multipliers = {
			"employed": 1.0,
			"self-employed": 0.6,
			"unemployed": 0.0,
		}
		multiplier = multipliers.get(normalized, 0.3)
		score = weight * multiplier
		return score, {
			"employment_status": normalized,
			"multiplier": multiplier,
		}

	def _debt_to_income_score(
		self,
		monthly_withdrawals: float | None,
		monthly_deposits: float | None,
	) -> tuple[float, dict[str, Any]]:
		weight = self.settings.scoring.debt_to_income_weight

		if monthly_withdrawals is None or monthly_deposits is None:
			return 0.0, {
				"ratio": None,
				"multiplier": 0.0,
				"monthly_withdrawals": monthly_withdrawals,
				"monthly_deposits": monthly_deposits,
				"missing_documentation": True,
			}

		if monthly_deposits <= 0:
			ratio = float("inf") if monthly_withdrawals > 0 else 0.0
		else:
			ratio = monthly_withdrawals / monthly_deposits

		if ratio <= 0.5:
			multiplier = 1.0
		elif ratio <= 0.75:
			multiplier = 0.7
		elif ratio <= 1.0:
			multiplier = 0.4
		else:
			multiplier = 0.0

		score = weight * multiplier
		return score, {
			"ratio": ratio,
			"multiplier": multiplier,
			"monthly_withdrawals": monthly_withdrawals,
			"monthly_deposits": monthly_deposits,
		}

	def _decision_from_score(
		self,
		total_score: float,
		*,
		has_missing_documents: bool,
	) -> str:
		if has_missing_documents:
			return "flagged_for_review"

		if total_score >= self.settings.thresholds.auto_approve:
			return "approved"
		if total_score >= self.settings.thresholds.manual_review:
			return "flagged_for_review"
		return "denied"

	def score_application(
		self,
		*,
		loan_amount: float,
		stated_monthly_income: float,
		employment_status: str,
		documented_monthly_income: float | None,
		bank_ending_balance: float | None,
		bank_has_overdrafts: bool | None,
		bank_has_consistent_deposits: bool | None,
		monthly_withdrawals: float | None,
		monthly_deposits: float | None,
	) -> ScoreResult:
		has_missing_documents = any(
			value is None
			for value in [
				documented_monthly_income,
				bank_ending_balance,
				bank_has_overdrafts,
				bank_has_consistent_deposits,
				monthly_withdrawals,
				monthly_deposits,
			]
		)

		income_verification_score, income_verification_reason = self._income_verification_score(
			stated_income=stated_monthly_income,
			documented_income=documented_monthly_income,
		)
		income_level_score, income_level_reason = self._income_level_score(
			loan_amount=loan_amount,
			documented_income=documented_monthly_income,
		)
		account_stability_score, account_stability_reason = self._account_stability_score(
			bank_ending_balance=bank_ending_balance,
			bank_has_overdrafts=bank_has_overdrafts,
			bank_has_consistent_deposits=bank_has_consistent_deposits,
		)
		employment_status_score, employment_status_reason = self._employment_status_score(
			employment_status=employment_status,
		)
		debt_to_income_score, debt_to_income_reason = self._debt_to_income_score(
			monthly_withdrawals=monthly_withdrawals,
			monthly_deposits=monthly_deposits,
		)

		total_score = round(
			income_verification_score
			+ income_level_score
			+ account_stability_score
			+ employment_status_score
			+ debt_to_income_score,
			2,
		)
		decision = self._decision_from_score(
			total_score,
			has_missing_documents=has_missing_documents,
		)

		return ScoreResult(
			income_verification_score=round(income_verification_score, 2),
			income_level_score=round(income_level_score, 2),
			account_stability_score=round(account_stability_score, 2),
			employment_status_score=round(employment_status_score, 2),
			debt_to_income_score=round(debt_to_income_score, 2),
			total_score=total_score,
			decision=decision,
			reasoning={
				"has_missing_documents": has_missing_documents,
				"income_verification": income_verification_reason,
				"income_level": income_level_reason,
				"account_stability": account_stability_reason,
				"employment_status": employment_status_reason,
				"debt_to_income": debt_to_income_reason,
				"thresholds": {
					"auto_approve": self.settings.thresholds.auto_approve,
					"manual_review": self.settings.thresholds.manual_review,
				},
			},
		)
