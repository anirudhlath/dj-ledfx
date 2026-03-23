from dj_ledfx.events import TransportStateChangedEvent
from dj_ledfx.transport import TransportState


def test_transport_state_values():
    assert TransportState.STOPPED.value == "stopped"
    assert TransportState.PLAYING.value == "playing"
    assert TransportState.SIMULATING.value == "simulating"


def test_transport_state_from_string():
    assert TransportState("stopped") == TransportState.STOPPED
    assert TransportState("playing") == TransportState.PLAYING
    assert TransportState("simulating") == TransportState.SIMULATING


def test_transport_state_is_active():
    assert not TransportState.STOPPED.is_active
    assert TransportState.PLAYING.is_active
    assert TransportState.SIMULATING.is_active


def test_transport_state_changed_event():
    event = TransportStateChangedEvent(
        old_state=TransportState.STOPPED,
        new_state=TransportState.PLAYING,
    )
    assert event.old_state == TransportState.STOPPED
    assert event.new_state == TransportState.PLAYING
