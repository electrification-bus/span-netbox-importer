from types import SimpleNamespace

from test_collector import CIRCUIT_1P, CIRCUIT_2P, PANEL, circuit, device, panel, tree


def make(importer, devices):
    collector = importer.SpanTreeCollector(PANEL, "h", "pw", ca_cert_path=None)
    collector.devices = devices
    collector.read()
    return collector


def test_unconnected_is_unusable(importer):
    assert not importer.usable_collection(make(importer, {}))


def test_flat_model_panel_is_unusable(importer):
    flat = {PANEL: device(PANEL, {"type": "energy.ebus.device.distribution-enclosure"}, core__breaker_rating="200")}
    assert not importer.usable_collection(make(importer, flat))


def test_panel_missing_main_breaker_is_unusable(importer):
    devices = {PANEL: panel([])}
    devices[PANEL].properties["breaker"].pop("rating")
    assert not importer.usable_collection(make(importer, devices))


def test_panel_not_ready_is_unusable(importer):
    devices = tree()
    devices[PANEL].update_state("init")
    assert not importer.usable_collection(make(importer, devices))


def test_unresolvable_host_is_unusable(importer):
    collector = importer.SpanTreeCollector(PANEL, "no-such-host.invalid", "pw", ca_cert_path=None)
    collector.collect()
    assert collector.error
    assert not importer.usable_collection(collector)


def test_incomplete_circuit_is_dropped(importer):
    devices = tree()
    devices[CIRCUIT_1P] = circuit(CIRCUIT_1P, "Attic", "5", "1")
    devices[CIRCUIT_1P].properties["breaker"].pop("poles")
    collector = make(importer, devices)
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
