from dj_ledfx.status import SystemStatus


def test_system_status_defaults() -> None:
    status = SystemStatus()
    assert status.prodjlink_connected is False
    assert status.active_player_count == 0
    assert status.current_bpm is None
    assert status.connected_devices == []
    assert status.buffer_fill_level == 0.0


def test_system_status_log_summary() -> None:
    status = SystemStatus(
        prodjlink_connected=True,
        active_player_count=2,
        current_bpm=128.0,
        connected_devices=["OpenRGB:0"],
        buffer_fill_level=0.95,
        avg_frame_render_time_ms=0.5,
    )
    summary = status.summary()
    assert "128.0" in summary
    assert "OpenRGB:0" in summary
