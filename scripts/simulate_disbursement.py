from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def build_payload(application_id: str, status: str, transaction_id: str) -> dict[str, str]:
	return {
		"application_id": application_id,
		"status": status,
		"transaction_id": transaction_id,
		"timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
	}


def post_webhook(base_url: str, payload: dict[str, str]) -> tuple[int, str]:
	url = f"{base_url.rstrip('/')}/webhook/disbursement"
	data = json.dumps(payload).encode("utf-8")
	request = Request(
		url=url,
		data=data,
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	try:
		with urlopen(request, timeout=30) as response:
			body = response.read().decode("utf-8")
			return response.status, body
	except HTTPError as exc:
		error_body = exc.read().decode("utf-8", errors="replace")
		return exc.code, error_body
	except URLError as exc:
		return 0, f"Connection error: {exc}"


def run_success(base_url: str, application_id: str, transaction_id: str | None) -> int:
	tx_id = transaction_id or f"txn_success_{uuid.uuid4().hex[:10]}"
	payload = build_payload(application_id, "success", tx_id)
	status_code, body = post_webhook(base_url, payload)
	print("[success] payload:")
	print(json.dumps(payload, indent=2))
	print(f"[success] response status: {status_code}")
	print(f"[success] response body: {body}\n")
	return 0 if status_code in (200, 201) else 1


def run_failed(base_url: str, application_id: str, transaction_id: str | None) -> int:
	tx_id = transaction_id or f"txn_failed_{uuid.uuid4().hex[:10]}"
	payload = build_payload(application_id, "failed", tx_id)
	status_code, body = post_webhook(base_url, payload)
	print("[failed] payload:")
	print(json.dumps(payload, indent=2))
	print(f"[failed] response status: {status_code}")
	print(f"[failed] response body: {body}\n")
	return 0 if status_code in (200, 201) else 1


def run_replay(base_url: str, application_id: str, transaction_id: str | None) -> int:
	tx_id = transaction_id or f"txn_replay_{uuid.uuid4().hex[:10]}"
	first_payload = build_payload(application_id, "success", tx_id)
	second_payload = build_payload(application_id, "success", tx_id)

	first_status, first_body = post_webhook(base_url, first_payload)
	second_status, second_body = post_webhook(base_url, second_payload)

	print("[replay] first payload:")
	print(json.dumps(first_payload, indent=2))
	print(f"[replay] first response status: {first_status}")
	print(f"[replay] first response body: {first_body}\n")

	print("[replay] second payload (same transaction_id):")
	print(json.dumps(second_payload, indent=2))
	print(f"[replay] second response status: {second_status}")
	print(f"[replay] second response body: {second_body}\n")

	return 0 if first_status in (200, 201) and second_status in (200, 201) else 1


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Simulate disbursement webhook events: success, failed, and replay."
	)
	parser.add_argument(
		"--base-url",
		default="http://127.0.0.1:8000",
		help="Base URL of the running API server (default: http://127.0.0.1:8000)",
	)
	parser.add_argument(
		"--application-id",
		required=True,
		help="Application ID to target in webhook payload.",
	)
	parser.add_argument(
		"--scenario",
		choices=["success", "failed", "replay", "all"],
		default="all",
		help="Webhook scenario to run (default: all).",
	)
	parser.add_argument(
		"--transaction-id",
		default=None,
		help="Optional transaction_id override. For replay, same ID is sent twice.",
	)
	return parser.parse_args()


def main() -> int:
	args = parse_args()

	if args.scenario == "success":
		return run_success(args.base_url, args.application_id, args.transaction_id)
	if args.scenario == "failed":
		return run_failed(args.base_url, args.application_id, args.transaction_id)
	if args.scenario == "replay":
		return run_replay(args.base_url, args.application_id, args.transaction_id)

	# all
	status_codes = [
		run_success(args.base_url, args.application_id, None),
		run_failed(args.base_url, args.application_id, None),
		run_replay(args.base_url, args.application_id, None),
	]
	return 0 if all(code == 0 for code in status_codes) else 1


if __name__ == "__main__":
	sys.exit(main())
