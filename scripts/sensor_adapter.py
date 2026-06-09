#!/usr/bin/env python3
"""
sensor_adapter.py — Live sensor ingestion adapter for SysML v2 V&V.

Reads real-time sensor data and converts it into the bind-value format used by
verify.py's fallback evaluator, enabling live system verification against the
formal SysML requirements.

Architecture:
  - SensorAdapter        — Abstract base class; all protocol adapters inherit this.
  - MQTTSensorAdapter    — MQTT broker (Mosquitto, AWS IoT, etc.)
  - OPCUASensorAdapter   — OPC-UA server (PLCs, SCADA systems)
  - RESTSensorAdapter    — HTTP polling (REST APIs, custom endpoints)
  - MockSensorAdapter    — Deterministic mock for testing (--demo mode)

Output schema (compatible with verify.py bind values):
  {
      "timestamp":  "2024-01-15T10:30:00Z",    # ISO-8601 UTC
      "system":     "<SystemType>",
      "source":     "mqtt",                     # adapter type
      "values": {
          "sys.sensor.waterLevel":        0.12,  # m  (reported water level)
          "sys.sensor.accuracy_m":        0.03,  # m  (sensor calibration class)
          "sys.controller.triggerLevel_m": 0.25, # m
          "sys.controller.responseTime_s":  1.0, # s
          "sys.controller.failoverTime_s":  0.8, # s
          "sys.pumpA.flowRate":           0.025,  # m³/s
          "sys.pumpA.efficiency":          0.82,  # dimensionless
          "sys.pumpB.flowRate":           0.025,  # m³/s
          "sys.pumpB.efficiency":          0.82,  # dimensionless
          "sys.pumpB.isRedundant":          True,
          "sys.discharge.pipeLossFactor":  0.05,
          "sys.alarm.activationDelay_s":    0.5, # s
          "sys.alarm.isActive":            False,
          "sys.ui.overrideActive":         False,
          "sys.inflowRate_m3s":           0.020,  # m³/s  (from stability analysis)
          "sys.criticalLevel_m":           0.50,  # m
      }
  }

Usage:
    # Demo mode (mock readings, no hardware):
    python scripts/sensor_adapter.py --demo

    # Poll a REST endpoint and print normalised values:
    python scripts/sensor_adapter.py --config config/sensors.json --once

    # Continuous loop — pipe to verify.py --live:
    python scripts/sensor_adapter.py --config config/sensors.json

Configuration file schema (sensors.json):
  {
      "adapter":   "rest" | "mqtt" | "opcua" | "mock",
      "system":    "<SystemType>",
      "interval_s": 5,
      "rest": {
          "url":         "http://vessel-gateway:8080/api/bilge",
          "headers":     {"Authorization": "Bearer <token>"},
          "mapping": {
              "data.sensorLevel":   "sys.sensor.waterLevel",
              "data.pumpAFlow":     "sys.pumpA.flowRate"
          }
      },
      "mqtt": {
          "broker":  "mqtt.vessel.local",
          "port":    1883,
          "topics": {
              "bilge/sensor/waterLevel":    "sys.sensor.waterLevel",
              "bilge/pumpA/flowRate":       "sys.pumpA.flowRate"
          }
      },
      "opcua": {
          "url":    "opc.tcp://plc.vessel.local:4840",
          "nodes": {
              "ns=2;i=1001":  "sys.sensor.waterLevel",
              "ns=2;i=1002":  "sys.pumpA.flowRate"
          }
      }
  }
"""

from __future__ import annotations

import abc
import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any


# ── Defaults (mirror Analysis.sysml nominal bind values) ─────────────────────

DEFAULTS: dict[str, Any] = {
    "sys.sensor.waterLevel": 0.15,
    "sys.sensor.accuracy_m": 0.03,
    "sys.controller.triggerLevel_m": 0.25,
    "sys.controller.responseTime_s": 1.0,
    "sys.controller.failoverTime_s": 0.8,
    "sys.pumpA.flowRate": 0.025,
    "sys.pumpA.efficiency": 0.82,
    "sys.pumpA.runHours": 120.0,
    "sys.pumpB.flowRate": 0.025,
    "sys.pumpB.efficiency": 0.82,
    "sys.pumpB.runHours": 85.0,
    "sys.pumpB.isRedundant": True,
    "sys.discharge.pipeLossFactor": 0.05,
    "sys.alarm.activationDelay_s": 0.5,
    "sys.alarm.isActive": False,
    "sys.ui.overrideActive": False,
    "sys.inflowRate_m3s": 0.020,
    "sys.criticalLevel_m": 0.50,
    "sys.power.nominalVoltage": 440.0,
    "sys.power.redundancyActive": False,
}


def _now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Abstract base ─────────────────────────────────────────────────────────────


class SensorAdapter(abc.ABC):
    """
    Abstract base for all sensor adapters.

    Subclasses implement :meth:`read` to return a flat dict mapping SysML
    bind-value paths to their current readings.  Unknown keys are merged with
    :data:`DEFAULTS` so the output is always a complete bind-value set.
    """

    def __init__(self, config: dict, system: str = "<SystemType>"):
        self.config = config
        self.system = system

    @abc.abstractmethod
    def read(self) -> dict[str, Any]:
        """
        Poll the sensor source once and return a partial or complete
        bind-value dict (SysML path → value).
        """

    def snapshot(self) -> dict:
        """
        Return a normalised snapshot dict ready for consumption by verify.py.
        Missing keys are filled from DEFAULTS.
        """
        raw = self.read()
        values = {**DEFAULTS, **raw}
        return {
            "timestamp": _now_utc(),
            "system": self.system,
            "source": self.__class__.__name__,
            "values": values,
        }


# ── Mock adapter ──────────────────────────────────────────────────────────────


class MockSensorAdapter(SensorAdapter):
    """
    Deterministic mock adapter for testing and demo mode.

    Cycles through three scenarios:
      Step 0–2:  nominal (all requirements satisfied)
      Step 3–4:  rising water level (approaching trigger)
      Step 5:    alarm active + override inactive (normal operation)
    """

    def __init__(self, config: dict, system: str = "<SystemType>"):
        super().__init__(config, system)
        self._step = 0
        self._scenarios = [
            # Nominal
            {"sys.sensor.waterLevel": 0.10, "sys.alarm.isActive": False},
            {"sys.sensor.waterLevel": 0.15, "sys.alarm.isActive": False},
            {"sys.sensor.waterLevel": 0.20, "sys.alarm.isActive": False},
            # Rising — approaching trigger (0.25)
            {"sys.sensor.waterLevel": 0.22, "sys.alarm.isActive": False},
            {"sys.sensor.waterLevel": 0.24, "sys.alarm.isActive": False},
            # Alarm triggered
            {"sys.sensor.waterLevel": 0.26, "sys.alarm.isActive": True},
        ]

    def read(self) -> dict[str, Any]:
        scenario = self._scenarios[self._step % len(self._scenarios)]
        self._step += 1
        return dict(scenario)


# ── REST adapter ──────────────────────────────────────────────────────────────


class RESTSensorAdapter(SensorAdapter):
    """
    HTTP polling adapter.  Fetches JSON from a REST endpoint and maps fields
    to SysML bind-value paths using the 'mapping' in the config.

    Requires: requests (pip install requests)
    """

    def read(self) -> dict[str, Any]:
        try:
            import requests  # noqa: PLC0415
        except ImportError:
            raise RuntimeError(
                "requests is required for the REST adapter: pip install requests"
            )

        rest_cfg = self.config.get("rest", {})
        url = rest_cfg.get("url", "")
        headers = rest_cfg.get("headers", {})
        mapping = rest_cfg.get("mapping", {})

        if not url:
            raise ValueError("REST adapter requires 'rest.url' in config")

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        result: dict[str, Any] = {}
        for json_path, sysml_path in mapping.items():
            # Support simple dot-notation traversal (e.g. "data.sensorLevel")
            value = data
            for key in json_path.split("."):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    value = None
                    break
            if value is not None:
                result[sysml_path] = value

        return result


# ── MQTT adapter ──────────────────────────────────────────────────────────────


class MQTTSensorAdapter(SensorAdapter):
    """
    MQTT subscriber adapter.  Subscribes to configured topics and collects
    one value per topic in a single poll cycle.

    Requires: paho-mqtt (pip install paho-mqtt)
    """

    def read(self) -> dict[str, Any]:
        try:
            import paho.mqtt.client as mqtt  # noqa: PLC0415
        except ImportError:
            raise RuntimeError(
                "paho-mqtt is required for the MQTT adapter: pip install paho-mqtt"
            )

        mqtt_cfg = self.config.get("mqtt", {})
        broker = mqtt_cfg.get("broker", "localhost")
        port = int(mqtt_cfg.get("port", 1883))
        topics = mqtt_cfg.get("topics", {})  # {topic: sysml_path}
        timeout = float(mqtt_cfg.get("poll_timeout_s", 5.0))

        collected: dict[str, Any] = {}

        def _on_message(client, userdata, msg):
            sysml_path = topics.get(msg.topic)
            if sysml_path:
                try:
                    collected[sysml_path] = float(msg.payload.decode())
                except ValueError:
                    raw = msg.payload.decode().lower()
                    if raw in ("true", "1"):
                        collected[sysml_path] = True
                    elif raw in ("false", "0"):
                        collected[sysml_path] = False

        client = mqtt.Client()
        client.on_message = _on_message
        client.connect(broker, port, keepalive=10)
        for topic in topics:
            client.subscribe(topic)
        client.loop_start()
        time.sleep(timeout)
        client.loop_stop()
        client.disconnect()
        return collected


# ── OPC-UA adapter ────────────────────────────────────────────────────────────


class OPCUASensorAdapter(SensorAdapter):
    """
    OPC-UA client adapter.  Reads node values from a PLC or SCADA OPC-UA server.

    Requires: opcua (pip install opcua)  or  asyncua (pip install asyncua)
    """

    def read(self) -> dict[str, Any]:
        try:
            from opcua import Client  # noqa: PLC0415
        except ImportError:
            raise RuntimeError(
                "opcua is required for the OPC-UA adapter: pip install opcua"
            )

        opcua_cfg = self.config.get("opcua", {})
        url = opcua_cfg.get("url", "opc.tcp://localhost:4840")
        nodes = opcua_cfg.get("nodes", {})  # {node_id: sysml_path}

        collected: dict[str, Any] = {}
        client = Client(url)
        try:
            client.connect()
            for node_id, sysml_path in nodes.items():
                node = client.get_node(node_id)
                value = node.get_value()
                collected[sysml_path] = value
        finally:
            client.disconnect()
        return collected


# ── Factory ───────────────────────────────────────────────────────────────────


def make_adapter(config: dict) -> SensorAdapter:
    """Create the appropriate adapter from a config dict."""
    adapter_type = config.get("adapter", "mock").lower()
    system = config.get("system", "<SystemType>")
    mapping = {
        "mock": MockSensorAdapter,
        "rest": RESTSensorAdapter,
        "mqtt": MQTTSensorAdapter,
        "opcua": OPCUASensorAdapter,
    }
    cls = mapping.get(adapter_type)
    if cls is None:
        raise ValueError(
            f"Unknown adapter type '{adapter_type}'. "
            f"Valid options: {list(mapping.keys())}"
        )
    return cls(config, system)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sensor_adapter.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to sensor configuration JSON (see module docstring for schema).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run mock adapter in demo mode — no hardware required.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Take a single snapshot and exit (default: continuous loop).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        metavar="SECONDS",
        default=5.0,
        help="Polling interval in seconds for continuous mode (default: 5).",
    )
    parser.add_argument(
        "--output",
        choices=["json", "pretty"],
        default="pretty",
        help="Output format: json (one JSON object per line) or pretty (default).",
    )
    args = parser.parse_args()
    run_sensor(args)


def run_sensor(args) -> None:
    # ── Build config ──────────────────────────────────────────────────────────
    if args.demo:
        config = {"adapter": "mock", "system": "<SystemType>"}
    elif args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR: config file not found: {args.config}", file=sys.stderr)
            sys.exit(2)
        with open(config_path) as f:
            config = json.load(f)
    else:
        raise ValueError("Either --demo or --config FILE is required.")

    adapter = make_adapter(config)
    interval = config.get("interval_s", args.interval)

    def _emit(snap: dict) -> None:
        if args.output == "json":
            print(json.dumps(snap))
        else:
            ts = snap["timestamp"]
            system = snap["system"]
            source = snap["source"]
            print(f"\n[{ts}]  {system}  ({source})")
            print("─" * 60)
            for k, v in snap["values"].items():
                _ = k.split(".")[-1]
                print(f"  {k:<44}  {v}")
            print()

    if args.once or args.demo:
        # Demo: cycle through all mock scenarios once
        steps = len(adapter._scenarios) if isinstance(adapter, MockSensorAdapter) else 1
        for _ in range(steps if args.demo else 1):
            snap = adapter.snapshot()
            _emit(snap)
            if args.demo and steps > 1:
                time.sleep(0.5)
    else:
        # Continuous loop
        print(f"Starting sensor poll loop (interval={interval}s). Ctrl-C to stop.")
        try:
            while True:
                snap = adapter.snapshot()
                _emit(snap)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
