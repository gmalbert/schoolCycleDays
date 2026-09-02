"""Optional MQTT publishing with Home Assistant Discovery."""

from __future__ import annotations

import json
from datetime import date, timedelta

import paho.mqtt.client as mqtt

from .config import Settings
from .schedule import ScheduleService


def publish_discovery_and_state(settings: Settings, schedule: ScheduleService) -> None:
    """Publish retained discovery configs and current schedule state.

    This adapter is optional. The standalone app remains fully functional when
    MQTT is not configured or the broker is unavailable.
    """
    if not settings.mqtt_enabled:
        return

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="school-cycle-days")
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password or None)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.loop_start()
    try:
        device = {
            "identifiers": ["school_cycle_days"],
            "name": "School Cycle Days",
            "manufacturer": "School Cycle Days",
            "model": "Standalone Calendar",
        }
        entities = {
            "today": schedule.today(),
            "tomorrow": schedule.today(date.today() + timedelta(days=1)),
            "next_school_day": schedule.next_school_day(date.today()) or {
                "day": "",
                "kind": "none",
                "cycle_day": None,
                "title": "No future school day",
                "detail": "",
                "source": "system",
            },
        }

        for key, payload in entities.items():
            state_topic = f"{settings.mqtt_base_topic}/{key}"
            object_id = f"school_cycle_days_{key}"
            discovery_topic = (
                f"{settings.mqtt_discovery_prefix}/sensor/{object_id}/config"
            )
            config = {
                "name": key.replace("_", " ").title(),
                "unique_id": object_id,
                "state_topic": state_topic,
                "value_template": "{{ value_json.title }}",
                "json_attributes_topic": state_topic,
                "device": device,
                "icon": "mdi:calendar-school",
            }
            client.publish(discovery_topic, json.dumps(config), qos=1, retain=True)
            client.publish(state_topic, json.dumps(payload), qos=1, retain=True)
    finally:
        client.loop_stop()
        client.disconnect()
