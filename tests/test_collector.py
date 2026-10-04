import json
from typing import ClassVar

import pytest
from ebus_sdk.homie import DiscoveredDevice

PANEL = "nt-0000-abcde"
CIRCUIT_2P = "ac3dccda46a94b98878a227df6fed588"
CIRCUIT_1P = "6d2ccc482e8a48c7bc5bdf5d37b99b8c"
LUGS = f"{PANEL}-lugs-up"


def device(device_id, description=None, state="ready", **props):
    d = DiscoveredDevice(device_id)
    d.update_state(state)
    if description is not None:
        d.update_description(json.dumps(description))
    for key, value in props.items():
        node, prop = key.split("__")
        d.update_property(node, prop.replace("_", "-"), value)
    return d


def panel(children, **props):
    defaults = {"info__data_model_version": "1.0", "info__hardware_version": "1.2", "breaker__rating": "200"}
    defaults.update(props)
    return device(PANEL, {"type": "energy.ebus.device.distribution-enclosure", "children": children}, **defaults)


def circuit(cid, name, spaces, poles, rating=None):
    props = {"info__name": name, "info__spaces": spaces, "breaker__poles": poles}
    if rating is not None:
        props["breaker__rating"] = rating
    return device(cid, {"type": "energy.ebus.device.circuit", "parent": PANEL, "root": PANEL}, **props)


def tree():
    return {
        PANEL: panel([LUGS, CIRCUIT_2P, CIRCUIT_1P], info__model="MAIN_32", info__vendor_name="SPAN"),
        LUGS: device(LUGS, {"type": "energy.ebus.device.lugs", "parent": PANEL, "root": PANEL}),
        CIRCUIT_2P: circuit(CIRCUIT_2P, "Ovens", "14,16", "2", "50"),
        CIRCUIT_1P: circuit(CIRCUIT_1P, "Attic-Back-Outlet", "5", "1", "20"),
    }


@pytest.fixture
def collector(importer):
    return importer.SpanTreeCollector(PANEL, "localhost", "pw", ca_cert_path="/tmp/ca.crt")


def test_mqtt_cfg_verifies_tls(collector):
    cfg = collector.mqtt_cfg()
    assert cfg["use_tls"] is True
    assert cfg["tls_insecure"] is False
    assert cfg["tls_ca_cert"] == "/tmp/ca.crt"
    assert cfg["authentication"] == {"type": "USER_PASS", "username": PANEL, "password": "pw"}


def test_panel_fields(collector):
    collector.devices = tree()
    data = collector.read()
    assert (data.hardware_version, data.model, data.data_model_version) == ("1.2", "MAIN_32", "1.0")
    assert data.main_breaker_rating == 200
    assert collector.connected
    assert collector.panel_complete


def test_only_circuit_children_become_circuits(collector):
    collector.devices = tree()
    assert set(collector.read().circuits) == {CIRCUIT_2P, CIRCUIT_1P}


def test_circuit_mapping(collector):
    collector.devices = tree()
    circuits = collector.read().circuits
    two_pole, one_pole = circuits[CIRCUIT_2P], circuits[CIRCUIT_1P]
    assert (two_pole.name, two_pole.breaker_rating, two_pole.space) == ("Ovens", 50, 14)
    assert (two_pole.is_duplex, two_pole.voltage) == (True, 240)
    assert (one_pole.space, one_pole.is_duplex, one_pole.voltage) == (5, False, 120)
    assert collector._complete()


def test_missing_rating_reads_as_zero(collector):
    devices = tree()
    devices[CIRCUIT_1P] = circuit(CIRCUIT_1P, "Commissioned PV System", "29,31", "2")
    collector.devices = devices
    pv = collector.read().circuits[CIRCUIT_1P]
    assert pv.breaker_rating == 0
    assert pv.complete


def test_incomplete_until_all_values_arrive(collector):
    devices = tree()
    devices[CIRCUIT_2P] = device(
        CIRCUIT_2P, {"type": "energy.ebus.device.circuit"}, info__name="Ovens", info__spaces="14,16"
    )
    collector.devices = devices
    assert not collector._complete()
    devices[CIRCUIT_2P].update_property("breaker", "poles", "2")
    assert collector._complete()


def test_undescribed_child_blocks_completion(collector):
    devices = tree()
    devices[CIRCUIT_2P] = DiscoveredDevice(CIRCUIT_2P)
    collector.devices = devices
    assert not collector._complete()
    assert set(collector.read().circuits) == {CIRCUIT_1P}


def test_flat_model_panel_is_incomplete(collector):
    collector.devices = {PANEL: device(PANEL, {"type": "energy.ebus.device.distribution-enclosure"})}
    assert collector.connected
    assert not collector.panel_complete


def test_nothing_received(collector):
    assert not collector.connected
    assert not collector.panel_complete
    assert collector.read().circuits == {}


def test_meter_updates_do_not_reset_quiet_timer(collector):
    collector._on_property(CIRCUIT_2P, "meter", "active-power", "-6.2", None)
    assert collector._last_update == 0.0
    collector._on_property(CIRCUIT_2P, "info", "name", "Ovens", None)
    assert collector._last_update > 0.0


class FakeController:
    instances: ClassVar[list] = []

    def __init__(self, mqtt_cfg, root_device_id):
        self.mqtt_cfg, self.root_device_id = mqtt_cfg, root_device_id
        self.devices = tree()
        self.stopped = False
        FakeController.instances.append(self)

    def set_on_description_received_callback(self, cb):
        pass

    def set_on_property_changed_callback(self, cb):
        pass

    def start_discovery(self):
        pass

    def stop(self):
        self.stopped = True


def test_collect_reads_tree_and_stops(importer, collector, monkeypatch):
    monkeypatch.setattr(importer, "Controller", FakeController, raising=False)
    data = collector.collect()
    controller = FakeController.instances[-1]
    assert controller.root_device_id == PANEL
    assert controller.stopped
    assert set(data.circuits) == {CIRCUIT_2P, CIRCUIT_1P}


def test_collect_times_out_and_still_stops(importer, collector, monkeypatch):
    class Silent(FakeController):
        def __init__(self, mqtt_cfg, root_device_id):
            super().__init__(mqtt_cfg, root_device_id)
            self.devices = {}

    monkeypatch.setattr(importer, "Controller", Silent, raising=False)
    collector.timeout = 0.2
    data = collector.collect()
    assert FakeController.instances[-1].stopped
    assert not collector.connected
    assert data.circuits == {}
