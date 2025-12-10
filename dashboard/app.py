"""Streamlit dashboard for monitoring serverless VM metrics stored in Redis."""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import redis
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# Load local .env if present; Kubernetes/docker can still inject env vars normally.
load_dotenv(".env")


def debug_env() -> Dict[str, str]:
	"""Collect env vars used for Redis and log them for debugging."""
	env_info = {
		"REDIS_HOST": os.environ.get("REDIS_HOST", "<default:localhost>"),
		"REDIS_PORT": os.environ.get("REDIS_PORT", "<default:6379>"),
		"REDIS_DB": os.environ.get("REDIS_DB", "<default:0>"),
		"REDIS_KEY": os.environ.get("REDIS_KEY", "<default:ifs4-proj3-output>"),
	}
	print("[env-debug]", env_info)
	return env_info


def get_redis_client() -> redis.Redis:
	"""Create a Redis client using environment variables with safe defaults."""
	host = os.environ.get("REDIS_HOST", "localhost")
	port = int(os.environ.get("REDIS_PORT", "6379"))
	db = int(os.environ.get("REDIS_DB", "0"))
	return redis.Redis(host=host, port=port, db=db, decode_responses=True)


def check_redis_connection() -> Dict[str, Any]:
	"""Ping Redis to verify connectivity from inside the app/container."""
	info: Dict[str, Any] = {"ok": False, "message": "not tested"}
	client = get_redis_client()
	try:
		client.ping()
		info.update({"ok": True, "message": "PING ok"})
	except Exception as exc:  # Broad on purpose for diagnostics
		info.update({"ok": False, "message": f"Erro de conexão: {exc}"})
	return info


@st.cache_resource(show_spinner=False)
def cached_client() -> redis.Redis:
	return get_redis_client()


def read_metrics_from_redis(key: str) -> Optional[Dict[str, Any]]:
	"""Read and parse JSON metrics from Redis, returning None on any error."""
	client = cached_client()
	try:
		raw_value = client.get(key)
		if raw_value is None:
			return None
		return json.loads(raw_value)
	except Exception:
		return None


def find_metric(data: Dict[str, Any], pattern: str, fallback_keys: Optional[list] = None) -> Optional[float]:
	"""Find the first metric matching regex pattern or fallback keys."""
	regex = re.compile(pattern)
	for k, v in data.items():
		if regex.search(k):
			try:
				return float(v)
			except (TypeError, ValueError):
				continue
	if fallback_keys:
		for name in fallback_keys:
			if name in data:
				try:
					return float(data[name])
				except (TypeError, ValueError):
					continue
	return None


def extract_cpu_metrics(data: Dict[str, Any]) -> Dict[str, float]:
	"""Extract per-CPU 60s averages into a labeled dict sorted by CPU id."""
	cpu_pattern = re.compile(r"cpu(\d+)", re.IGNORECASE)
	metrics: Dict[str, float] = {}
	for key, value in data.items():
		if "avg" not in key or "60" not in key:
			continue
		match = cpu_pattern.search(key)
		if not match:
			continue
		try:
			metrics[f"CPU {int(match.group(1))}"] = float(value)
		except (TypeError, ValueError):
			continue
	# Sort by CPU number for consistent ordering
	return dict(sorted(metrics.items(), key=lambda item: int(item[0].split()[1])))


def update_history(key: str, value: Optional[float]) -> None:
	"""Store metric history in session state for charts."""
	if "history" not in st.session_state:
		st.session_state["history"] = {}
	history = st.session_state["history"].setdefault(key, [])
	if value is not None:
		history.append({"ts": datetime.utcnow(), "value": value})
		# Keep only the latest 500 points to avoid unbounded growth.
		if len(history) > 500:
			st.session_state["history"][key] = history[-500:]


def update_multi_history(key: str, values: Dict[str, float]) -> None:
	"""Store multi-series metric history (e.g., per-CPU) for charts."""
	if "history_multi" not in st.session_state:
		st.session_state["history_multi"] = {}
	history = st.session_state["history_multi"].setdefault(key, [])
	if values:
		record = {"ts": datetime.utcnow(), **values}
		history.append(record)
		if len(history) > 500:
			st.session_state["history_multi"][key] = history[-500:]


def history_to_dataframe(key: str) -> Optional[pd.DataFrame]:
	series = st.session_state.get("history", {}).get(key, [])
	if not series:
		return None
	df = pd.DataFrame(series)
	df.set_index("ts", inplace=True)
	return df


def multi_history_to_dataframe(key: str) -> Optional[pd.DataFrame]:
	series = st.session_state.get("history_multi", {}).get(key, [])
	if not series:
		return None
	df = pd.DataFrame(series)
	return df.set_index("ts")


def main() -> None:
	st.set_page_config(page_title="Serverless VM Metrics", layout="wide")
	st.title("Dashboard - Serverless VM Metrics")

	env_info = debug_env()
	conn_status = check_redis_connection()

	redis_key = os.environ.get("REDIS_KEY", "ifs4-proj3-output")
	refresh_ms = int(os.environ.get("REFRESH_MS", "5000"))

	st.caption(
		f"Lendo métricas da chave Redis `{redis_key}` (atualiza a cada {refresh_ms/1000:.0f}s)."
	)

	# Slightly bold styling for cards and charts.
	st.markdown(
		"""
		<style>
		.metric-card {background: linear-gradient(135deg, #0f172a, #111827); color: #e5e7eb; padding: 12px 14px; border-radius: 10px; border: 1px solid #1f2937; box-shadow: 0 8px 30px rgba(0,0,0,0.25);} 
		.metric-card h3 {margin: 0 0 6px 0; font-size: 0.95rem; font-weight: 600; letter-spacing: 0.01em;}
		.metric-card .value {font-size: 1.6rem; font-weight: 700;}
		</style>
		""",
		unsafe_allow_html=True,
	)

	st.sidebar.write(f"Auto-refresh: {refresh_ms} ms")
	st.sidebar.write("Redis host:", os.environ.get("REDIS_HOST", "localhost"))
	st.sidebar.write("Redis port:", os.environ.get("REDIS_PORT", "6379"))
	st.sidebar.button("Atualizar agora", on_click=lambda: st.rerun())
	st.sidebar.write("Conn status:", "OK" if conn_status.get("ok") else conn_status.get("message"))
	with st.sidebar.expander("Debug env"):
		st.json(env_info)

	# Auto refresh the page periodically to poll Redis.
	st_autorefresh(interval=refresh_ms, key="auto_refresh")

	data = read_metrics_from_redis(redis_key)

	if data is None:
		st.warning(
			"Não foi possível ler dados do Redis (chave ausente ou conexão indisponível)."
		)
		return

	net_egress = find_metric(
		data,
		pattern=r"network.*egress|egress",
		fallback_keys=["percent-network-egress", "network-egress"],
	)
	mem_cache = find_metric(
		data,
		pattern=r"memory.*cache|memory.*caching|cache",
		fallback_keys=["percent-memory-cache", "percent-memory-caching"],
	)
	cpu_metrics = extract_cpu_metrics(data)
	cpu_avg = None
	if cpu_metrics:
		cpu_avg = sum(cpu_metrics.values()) / len(cpu_metrics)
	else:
		cpu_avg = find_metric(data, pattern=r"avg.*cpu.*60")

	# Update histories for charts.
	update_history("network_egress", net_egress)
	update_history("memory_cache", mem_cache)
	update_history("cpu_avg", cpu_avg)
	update_multi_history("cpu_multi", cpu_metrics)

	cols = st.columns(3)
	cols[0].metric("Network Egress (%)", f"{net_egress:.2f}" if net_egress is not None else "—")
	cols[1].metric("Memory Cache (%)", f"{mem_cache:.2f}" if mem_cache is not None else "—")
	cols[2].metric("CPU Avg 60s (todos)", f"{cpu_avg:.2f}" if cpu_avg is not None else "—")

	# Per-CPU cards with a slightly bolder style.
	if cpu_metrics:
		st.subheader("CPU por núcleo")
		cpu_cols = st.columns(min(len(cpu_metrics), 4) or 1)
		for idx, (label, value) in enumerate(cpu_metrics.items()):
			col = cpu_cols[idx % len(cpu_cols)]
			col.markdown(
				f"<div class='metric-card'><h3>{label}</h3><div class='value'>{value:.2f}%</div></div>",
				unsafe_allow_html=True,
			)

	charts = st.container()
	with charts:
		chart_cols = st.columns(3)

		net_df = history_to_dataframe("network_egress")
		if net_df is not None:
			chart_cols[0].line_chart(net_df, y="value")
		else:
			chart_cols[0].info("Aguardando dados de network egress…")

		mem_df = history_to_dataframe("memory_cache")
		if mem_df is not None:
			chart_cols[1].line_chart(mem_df, y="value")
		else:
			chart_cols[1].info("Aguardando dados de memória em cache…")

		cpu_multi_df = multi_history_to_dataframe("cpu_multi")
		if cpu_multi_df is not None:
			chart_cols[2].line_chart(cpu_multi_df)
		else:
			chart_cols[2].info("Aguardando dados de CPU por núcleo…")

	with st.expander("JSON bruto lido do Redis"):
		st.json(data)


if __name__ == "__main__":
	main()
