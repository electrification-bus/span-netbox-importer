from types import SimpleNamespace


class Feed(SimpleNamespace):
    saved = 0

    def save(self):
        self.saved += 1


class FakeFeeds:
    def __init__(self, feeds):
        self.feeds = feeds
        self.created = []

    def filter(self, power_panel_id):
        return list(self.feeds)

    def create(self, data):
        self.created.append(data)


def fake_nb(feeds):
    return SimpleNamespace(dcim=SimpleNamespace(power_feeds=FakeFeeds(feeds)))


def feed(circuit_id, name, amperage, space, duplex, voltage):
    return Feed(
        name=name,
        amperage=amperage,
        voltage=voltage,
        custom_fields={"panel_circuit_id": circuit_id, "panel_space": space, "is_duplex": duplex},
    )


def panel_with(importer, *circuits):
    data = importer.PanelData(serial_number="nt-0000-abcde", hostname="h")
    for c in circuits:
        data.circuits[c.circuit_id] = c
    return data


def circuit(importer, cid, name, rating, spaces, poles):
    return importer.CircuitData(circuit_id=cid, name=name, breaker_rating=rating, spaces=spaces, poles=poles)


def test_matching_feed_is_unchanged(importer):
    existing = feed("c1", "Ovens", 50, 14, True, 240)
    nb = fake_nb([existing])
    data = panel_with(importer, circuit(importer, "c1", "Ovens", 50, [14, 16], 2))
    assert importer.sync_power_feeds(nb, data, SimpleNamespace(id=1)) == {"created": 0, "updated": 0, "unchanged": 1}
    assert existing.saved == 0


def test_missing_rating_keeps_existing_amperage(importer):
    existing = feed("c1", "Commissioned PV System", 20, 29, True, 240)
    nb = fake_nb([existing])
    data = panel_with(importer, circuit(importer, "c1", "Commissioned PV System", 0, [29, 31], 2))
    assert importer.sync_power_feeds(nb, data, SimpleNamespace(id=1))["unchanged"] == 1


def test_voltage_follows_poles(importer):
    existing = feed("c1", "Dryer", 30, 2, True, 120)
    nb = fake_nb([existing])
    data = panel_with(importer, circuit(importer, "c1", "Dryer", 30, [2, 4], 2))
    assert importer.sync_power_feeds(nb, data, SimpleNamespace(id=1))["updated"] == 1
    assert existing.voltage == 240
    assert existing.saved == 1


def test_new_feed(importer):
    nb = fake_nb([])
    data = panel_with(importer, circuit(importer, "c2", "", 0, [7], 1))
    importer.sync_power_feeds(nb, data, SimpleNamespace(id=1))
    (created,) = nb.dcim.power_feeds.created
    assert created["name"] == "Circuit c2"
    assert (created["amperage"], created["voltage"]) == (1, 120)
    assert created["custom_fields"] == {"panel_circuit_id": "c2", "panel_space": 7, "is_duplex": False}


def test_dry_run_writes_nothing(importer):
    existing = feed("c1", "Old", 30, 2, True, 240)
    nb = fake_nb([existing])
    data = panel_with(importer, circuit(importer, "c1", "New", 30, [2, 4], 2), circuit(importer, "c3", "X", 15, [9], 1))
    importer.sync_power_feeds(nb, data, SimpleNamespace(id=1), dry_run=True)
    assert existing.saved == 0
    assert existing.name == "Old"
    assert not nb.dcim.power_feeds.created
