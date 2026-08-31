from __future__ import annotations

from abc import ABC

import requests
from typing import Any
from dotenv import load_dotenv
import os
import logging

load_dotenv()


class DittoClient:
    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()

        if username and password:
            self.session.auth = (username, password)

        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def create_thing(
        self,
        thing_id: str,
        definition: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict:
        response = self.session.put(
            f"{self.base_url}/api/2/things/{thing_id}",
            json={
                "definition": definition,
                "attributes": attributes or {},
            },
            timeout=self.timeout,
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        if response.text:
            return response.json()

        return {}

    def get_thing(self, thing_id: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/2/things/{thing_id}",
            timeout=self.timeout,
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        return response.json() if response.text else {}

    def thing_exists(self, thing_id: str) -> bool:
        response = self.session.get(
            f"{self.base_url}/api/2/things/{thing_id}",
            timeout=self.timeout,
        )

        if response.status_code == 404:
            return False

        response.raise_for_status()
        return True

    def delete_thing(self, thing_id: str) -> None:
        response = self.session.delete(
            f"{self.base_url}/api/2/things/{thing_id}",
            timeout=self.timeout,
        )

        response.raise_for_status()

    def add_feature(
        self,
        thing_id: str,
        feature_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict:
        response = self.session.put(
            f"{self.base_url}/api/2/things/{thing_id}/features/{feature_id}",
            json={"properties": properties or {}},
            timeout=self.timeout,
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        return response.json() if response.text else {}

    def feature_exists(
        self,
        thing_id: str,
        feature_id: str,
    ) -> bool:
        response = self.session.get(
            f"{self.base_url}/api/2/things/{thing_id}/features/{feature_id}",
            timeout=self.timeout,
        )

        if response.status_code == 404:
            return False

        response.raise_for_status()
        return True

    def update_feature_property(
        self,
        thing_id: str,
        feature_id: str,
        property_name: str,
        value: Any,
    ) -> dict | bool | int | str | None:
        response = self.session.put(
            f"{self.base_url}/api/2/things/"
            f"{thing_id}/features/"
            f"{feature_id}/properties/"
            f"{property_name}",
            json=value,
            timeout=self.timeout,
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        if response.text:
            return response.json()

        return {}

    def get_feature_property(
        self,
        thing_id: str,
        feature_id: str,
        property_name: str,
    ):
        response = self.session.get(
            f"{self.base_url}/api/2/things/"
            f"{thing_id}/features/"
            f"{feature_id}/properties/"
            f"{property_name}",
            timeout=self.timeout,
        )

        response.status_code
        response.text

        response.raise_for_status()

        if response.text:
            return response.json()

        return None

    def search_things(self, filter_expr: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/2/search/things",
            params={"filter": filter_expr},
            timeout=self.timeout,
        )

        print(response.status_code)
        print(response.text)

        response.raise_for_status()

        return response.json() if response.text else {}

    def property_exists(
        self,
        thing_id: str,
        feature_id: str,
        property_name: str,
    ) -> bool:
        response = self.session.get(
            f"{self.base_url}/api/2/things/"
            f"{thing_id}/features/"
            f"{feature_id}/properties/"
            f"{property_name}",
            timeout=self.timeout,
        )

        if response.status_code == 404:
            return False

        response.raise_for_status()
        return True


class Sensor(ABC):
    def __init__(
        self,
        twin_client: DittoClient,
        thing_id: str,
        feature_id: str,
        definition: str,
        attributes: dict[str, Any] | None = None,
    ):
        self.twin_client = twin_client
        self.thing_id = thing_id
        self.feature_id = feature_id

        if not self.twin_client.thing_exists(self.thing_id):
            logging.info(f"Creating thing with ID: {self.thing_id}")
            self.twin_client.create_thing(
                thing_id=self.thing_id,
                definition=definition,
                attributes=attributes or {},
            )

    def add_features(self, properties: dict[str, Any] | None = None) -> None:
        properties = properties or {}

        if not self.twin_client.feature_exists(
            thing_id=self.thing_id,
            feature_id=self.feature_id,
        ):
            self.twin_client.add_feature(
                thing_id=self.thing_id,
                feature_id=self.feature_id,
                properties=properties,
            )
            return

        for name, value in properties.items():
            if not self.twin_client.property_exists(
                thing_id=self.thing_id,
                feature_id=self.feature_id,
                property_name=name,
            ):
                self.twin_client.update_feature_property(
                    thing_id=self.thing_id,
                    feature_id=self.feature_id,
                    property_name=name,
                    value=value,
                )

    def publish(self, property_name: str, value: Any):
        self.twin_client.update_feature_property(
            thing_id=self.thing_id,
            feature_id=self.feature_id,
            property_name=property_name,
            value=value,
        )


class DraftSensor(Sensor):
    def __init__(self, twin_client: DittoClient, thing_id: str, definition: str):
        self.property_name = "draft"
        self.state_property_name = "sensor_state"
        self.state_property = "idle"
        self.feature_id = "loading"
        self.attributes = {"description": "Draft sensor for ship loading"}

        super().__init__(
            twin_client,
            thing_id,
            feature_id=self.feature_id,
            definition=definition,
            attributes=self.attributes,
        )
        self.add_features(properties={})


if __name__ == "__main__":
    ditto = DittoClient(
        base_url="http://localhost:8080",
        username=os.getenv("DITTO_USERNAME"),
        password=os.getenv("DITTO_PASSWORD"),
    )
    draft_sensor = DraftSensor(
        twin_client=ditto, thing_id="ship:norway02", definition="urn:mycompany:ship"
    )
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.4)
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.3)
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.2)
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.1)

    draft_sensor = DraftSensor(
        twin_client=ditto, thing_id="ship:norway04", definition="urn:dnv:ship3"
    )
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.4)
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.3)
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.2)
    draft_sensor.publish(property_name=draft_sensor.property_name, value=8.1)
