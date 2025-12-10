import importlib.util
import json
import os
import sys
import time
import traceback
from types import ModuleType
from typing import Any, Callable, Optional

import redis


USER_MODULE_PATH = "/opt/usermodule.py"
POLL_INTERVAL_SECONDS = 5


class Context:
	"""Holds runtime metadata shared with the user handler."""

	def __init__(self, host: str, port: int, input_key: str, output_key: str, function_mtime: float) -> None:
		self.host = host
		self.port = port
		self.input_key = input_key
		self.output_key = output_key
		self.function_getmtime = function_mtime
		self.last_execution: Optional[float] = None
		self.env: dict[str, Any] = {}


def log(msg: str) -> None:
	print(msg, flush=True)


def load_user_handler(path: str) -> Callable[[dict, Context], Any]:
	if not os.path.isfile(path):
		log(f"[error] User module not found at {path}")
		sys.exit(1)

	spec = importlib.util.spec_from_file_location("usermodule", path)
	if spec is None or spec.loader is None:
		log("[error] Failed to create module spec for usermodule")
		sys.exit(1)

	module = importlib.util.module_from_spec(spec)
	try:
		spec.loader.exec_module(module)  # type: ignore[arg-type]
	except Exception:
		log("[error] Failed to load user module:")
		traceback.print_exc()
		sys.exit(1)

	handler = getattr(module, "handler", None)
	if not callable(handler):
		log("[error] usermodule.py must define a callable 'handler' function")
		sys.exit(1)

	return handler  # type: ignore[return-value]


def parse_input(raw_value: Any) -> Optional[dict]:
	if raw_value is None:
		return None
	try:
		text = raw_value if isinstance(raw_value, str) else raw_value.decode("utf-8")
		return json.loads(text)
	except Exception:
		log("[warn] Failed to parse JSON input from Redis")
		traceback.print_exc()
		return None


def main() -> None:
	host = os.environ.get("REDIS_HOST", "localhost")
	port_str = os.environ.get("REDIS_PORT", "6379")
	input_key = os.environ.get("REDIS_INPUT_KEY", "metrics")
	output_key = os.environ.get("REDIS_OUTPUT_KEY")

	if output_key is None:
		log("[error] REDIS_OUTPUT_KEY not set; exiting")
		sys.exit(1)

	try:
		port = int(port_str)
	except ValueError:
		log(f"[error] Invalid REDIS_PORT value: {port_str}")
		sys.exit(1)

	handler = load_user_handler(USER_MODULE_PATH)
	function_mtime = os.path.getmtime(USER_MODULE_PATH)
	context = Context(host, port, input_key, output_key, function_mtime)

	client = redis.Redis(host=host, port=port, decode_responses=False)
	last_raw_value: Any = None

	log(
		"Runtime started with host={host}, port={port}, input_key={input_key}, output_key={output_key}".format(
			host=host, port=port, input_key=input_key, output_key=output_key
		)
	)

	while True:
		try:
			raw_value = client.get(input_key)
		except Exception:
			log("[error] Failed to read from Redis; retrying after delay")
			traceback.print_exc()
			time.sleep(POLL_INTERVAL_SECONDS)
			continue

		if raw_value == last_raw_value:
			time.sleep(POLL_INTERVAL_SECONDS)
			continue

		last_raw_value = raw_value

		payload = parse_input(raw_value)
		if payload is None:
			time.sleep(POLL_INTERVAL_SECONDS)
			continue

		try:
			result = handler(payload, context)
		except Exception:
			log("[error] Exception inside user handler")
			traceback.print_exc()
			time.sleep(POLL_INTERVAL_SECONDS)
			continue

		if not isinstance(result, dict):
			log("[warn] Handler return is not a dict; skipping write")
			time.sleep(POLL_INTERVAL_SECONDS)
			continue

		try:
			output_payload = json.dumps(result)
			client.set(output_key, output_payload)
			context.last_execution = time.time()
			log(f"[info] Processed input and wrote output to key '{output_key}'")
		except Exception:
			log("[error] Failed to write handler output to Redis")
			traceback.print_exc()

		time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
	main()
