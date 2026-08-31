from unittest.mock import Mock

import pytest
from ditto_wrapper.sensor import DraftSensor, DittoClient


def test_sensor_creates_thing_when_missing():
    client = Mock()

    client.thing_exists.return_value = False

    DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    client.create_thing.assert_called_once_with(
        thing_id="ship:test",
        definition="urn:test:ship",
        attributes={"description": "Draft sensor for ship loading"},
    )


def test_sensor_does_not_create_existing_thing():
    client = Mock()

    client.thing_exists.return_value = True

    DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    client.create_thing.assert_not_called()


def test_add_features_creates_feature_when_missing():
    client = Mock()

    client.thing_exists.return_value = True
    client.feature_exists.return_value = False

    DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    client.add_feature.assert_called_once_with(
        thing_id="ship:test",
        feature_id="loading",
        properties={},
    )


def test_add_features_skips_feature_creation_when_exists():
    client = Mock()

    client.thing_exists.return_value = True
    client.feature_exists.return_value = True

    DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    client.add_feature.assert_not_called()


def test_add_features_creates_missing_properties():
    client = Mock()

    client.thing_exists.return_value = True
    client.feature_exists.return_value = True
    client.property_exists.return_value = False

    sensor = DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    sensor.add_features(
        {
            "draft": 8.4,
            "sensor_state": "idle",
        }
    )

    assert client.update_feature_property.call_count == 2


def test_add_features_skips_existing_properties():
    client = Mock()

    client.thing_exists.return_value = True
    client.feature_exists.return_value = True
    client.property_exists.return_value = True

    sensor = DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    sensor.add_features(
        {
            "draft": 8.4,
            "sensor_state": "idle",
        }
    )

    client.update_feature_property.assert_not_called()


def test_publish_updates_property():
    client = Mock()

    client.thing_exists.return_value = True
    client.feature_exists.return_value = True

    sensor = DraftSensor(
        twin_client=client,
        thing_id="ship:test",
        definition="urn:test:ship",
    )

    sensor.publish("draft", 8.4)

    client.update_feature_property.assert_called_with(
        thing_id="ship:test",
        feature_id="loading",
        property_name="draft",
        value=8.4,
    )


@pytest.mark.skipif(
    reason="Ditto server is not available",
)
def test_create_and_update_real_ditto():
    client = DittoClient(
        base_url="http://localhost:8080",
        username="ditto",
        password="ditto",
    )

    sensor = DraftSensor(
        twin_client=client,
        thing_id="ship:test01",
        definition="urn:test:ship",
    )

    sensor.publish("draft", 8.4)

    value = client.get_feature_property(
        thing_id="ship:test01",
        feature_id="loading",
        property_name="draft",
    )

    assert value == 8.4
