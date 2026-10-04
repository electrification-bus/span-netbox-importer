import json
from types import SimpleNamespace

PANEL = "nt-0000-abcde"
CIRCUIT_2P = "ac3dccda46a94b98878a227df6fed588"
CIRCUIT_1P = "6d2ccc482e8a48c7bc5bdf5d37b99b8c"
LUGS = f"{PANEL}-lugs-up"


class FakeClient:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self, topic):
        self.subscriptions.append(topic)


def make_collector(importer):
    return importer.SpanMqttCollector(PANEL, f"span-{PANEL}.local", "pw", ca_cert_path=None)


def deliver(collector, client, topic, payload):
    if not isinstance(payload, str):
        payload = json.dumps(payload)
    collector._on_message(client, None, SimpleNamespace(topic=topic, payload=payload.encode()))


def publish_tree(collector, client):
    deliver(collector, client, f"ebus/5/{PANEL}/$description", {"children": [LUGS, CIRCUIT_2P, CIRCUIT_1P]})
    deliver(collector, client, f"ebus/5/{PANEL}/info/hardware-version", "1.2")
    deliver(collector, client, f"ebus/5/{PANEL}/info/model", "MAIN_32")
    deliver(collector, client, f"ebus/5/{PANEL}/info/data-model-version", "1.0")
    deliver(collector, client, f"ebus/5/{PANEL}/breaker/rating", "200")
    deliver(collector, client, f"ebus/5/{LUGS}/$description", {"type": "energy.ebus.device.lugs"})
    for cid in (CIRCUIT_2P, CIRCUIT_1P):
        deliver(collector, client, f"ebus/5/{cid}/$description", {"type": "energy.ebus.device.circuit"})
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/info/name", "Ovens")
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/info/spaces", "14,16")
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/breaker/rating", "50")
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/breaker/poles", "2")
    deliver(collector, client, f"ebus/5/{CIRCUIT_1P}/info/name", "Attic-Back-Outlet")
    deliver(collector, client, f"ebus/5/{CIRCUIT_1P}/info/spaces", "5")
    deliver(collector, client, f"ebus/5/{CIRCUIT_1P}/breaker/rating", "20")
    deliver(collector, client, f"ebus/5/{CIRCUIT_1P}/breaker/poles", "1")


def test_panel_fields(importer):
    collector, client = make_collector(importer), FakeClient()
    publish_tree(collector, client)
    data = collector.panel_data
    assert (data.hardware_version, data.model, data.data_model_version) == ("1.2", "MAIN_32", "1.0")
    assert data.main_breaker_rating == 200
    assert collector.panel_complete


def test_only_circuit_children_become_circuits(importer):
    collector, client = make_collector(importer), FakeClient()
    publish_tree(collector, client)
    assert set(collector.panel_data.circuits) == {CIRCUIT_2P, CIRCUIT_1P}
    assert f"ebus/5/{LUGS}/info/+" not in client.subscriptions
    assert f"ebus/5/{CIRCUIT_2P}/breaker/+" in client.subscriptions


def test_circuit_mapping(importer):
    collector, client = make_collector(importer), FakeClient()
    publish_tree(collector, client)
    two_pole = collector.panel_data.circuits[CIRCUIT_2P]
    one_pole = collector.panel_data.circuits[CIRCUIT_1P]
    assert (two_pole.name, two_pole.breaker_rating, two_pole.space) == ("Ovens", 50, 14)
    assert (two_pole.is_duplex, two_pole.voltage) == (True, 240)
    assert (one_pole.space, one_pole.is_duplex, one_pole.voltage) == (5, False, 120)
    assert collector._complete()


def test_incomplete_until_all_values_arrive(importer):
    collector, client = make_collector(importer), FakeClient()
    deliver(collector, client, f"ebus/5/{PANEL}/$description", {"children": [CIRCUIT_2P]})
    deliver(collector, client, f"ebus/5/{PANEL}/info/data-model-version", "1.0")
    deliver(collector, client, f"ebus/5/{PANEL}/info/hardware-version", "1.2")
    deliver(collector, client, f"ebus/5/{PANEL}/breaker/rating", "200")
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/$description", {"type": "energy.ebus.device.circuit"})
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/info/name", "Ovens")
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/info/spaces", "14,16")
    assert not collector.panel_data.circuits[CIRCUIT_2P].complete
    assert not collector._complete()
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/breaker/poles", "2")
    assert collector._complete()


def test_undescribed_child_blocks_completion(importer):
    collector, client = make_collector(importer), FakeClient()
    deliver(collector, client, f"ebus/5/{PANEL}/$description", {"children": [CIRCUIT_2P]})
    deliver(collector, client, f"ebus/5/{CIRCUIT_2P}/$description", "")
    assert not collector._complete()


def test_flat_model_topics_are_ignored(importer):
    collector, client = make_collector(importer), FakeClient()
    deliver(collector, client, f"ebus/5/{PANEL}/core/breaker-rating", "200")
    deliver(collector, client, f"ebus/5/{PANEL}/{CIRCUIT_2P}/name", "Ovens")
    assert collector.panel_data.main_breaker_rating == 0
    assert not collector.panel_data.circuits
    assert not collector.panel_complete
