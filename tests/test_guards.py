from types import SimpleNamespace

from test_collector import CIRCUIT_1P, CIRCUIT_2P, PANEL, FakeClient, deliver, make_collector, publish_tree


def connected_collector(importer):
    collector = make_collector(importer)
    collector._connected = True
    return collector


def test_unconnected_is_unusable(importer):
    assert not importer.usable_collection(make_collector(importer))


def test_flat_model_panel_is_unusable(importer):
    collector, client = connected_collector(importer), FakeClient()
    deliver(collector, client, f"ebus/5/{PANEL}/$description", {"children": []})
    deliver(collector, client, f"ebus/5/{PANEL}/core/breaker-rating", "200")
    assert not importer.usable_collection(collector)


def test_panel_missing_main_breaker_is_unusable(importer):
    collector, client = connected_collector(importer), FakeClient()
    deliver(collector, client, f"ebus/5/{PANEL}/$description", {"children": []})
    deliver(collector, client, f"ebus/5/{PANEL}/info/data-model-version", "1.0")
    deliver(collector, client, f"ebus/5/{PANEL}/info/hardware-version", "1.2")
    assert not importer.usable_collection(collector)
    deliver(collector, client, f"ebus/5/{PANEL}/breaker/rating", "200")
    assert importer.usable_collection(collector)


def test_incomplete_circuit_is_dropped(importer):
    collector, client = connected_collector(importer), FakeClient()
    publish_tree(collector, client)
    collector.panel_data.circuits[CIRCUIT_1P].received.discard("breaker/poles")
    assert importer.usable_collection(collector)
    assert set(collector.panel_data.circuits) == {CIRCUIT_2P}


class Panel(SimpleNamespace):
    saved = 0

    def save(self):
        self.saved += 1


def test_power_panel_update_keeps_other_custom_fields(importer):
    existing = Panel(
        name="LC1",
        custom_fields={"serial_number": PANEL, "upstream_source": "Utility 200A Service", "main_breaker_rating": 100},
    )
    nb = SimpleNamespace(dcim=SimpleNamespace(power_panels=SimpleNamespace(filter=lambda site_id: [existing])))
    data = importer.PanelData(serial_number=PANEL, hostname="h", hardware_version="1.2", main_breaker_rating=200)
    assert importer.sync_power_panel(nb, data, SimpleNamespace(id=1), None) == (existing, False)
    assert existing.saved == 1
    assert existing.name == "LC1"
    assert existing.custom_fields["upstream_source"] == "Utility 200A Service"
    assert existing.custom_fields["main_breaker_rating"] == 200
