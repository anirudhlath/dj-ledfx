from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency


def test_static_latency() -> None:
    s = StaticLatency(latency_ms=10.0)
    assert s.get_latency() == 10.0
    s.update(20.0)
    assert s.get_latency() == 10.0


def test_ema_latency_basic() -> None:
    s = EMALatency(alpha=0.3)
    s.update(100.0)
    assert s.get_latency() == 100.0
    s.update(200.0)
    assert abs(s.get_latency() - 130.0) < 0.1


def test_ema_latency_outlier_rejection() -> None:
    s = EMALatency(alpha=0.3)
    for _ in range(10):
        s.update(100.0)
    s.update(3000.0)
    assert s.get_latency() < 150.0


def test_ema_latency_reset() -> None:
    s = EMALatency(alpha=0.3)
    s.update(100.0)
    s.reset()
    assert s.get_latency() == 0.0


def test_windowed_mean_basic() -> None:
    s = WindowedMeanLatency(window_size=3)
    s.update(100.0)
    s.update(200.0)
    s.update(300.0)
    assert abs(s.get_latency() - 200.0) < 0.1


def test_windowed_mean_rolls_over() -> None:
    s = WindowedMeanLatency(window_size=3)
    s.update(100.0)
    s.update(200.0)
    s.update(300.0)
    s.update(400.0)
    assert abs(s.get_latency() - 300.0) < 0.1


def test_windowed_mean_reset() -> None:
    s = WindowedMeanLatency(window_size=3)
    s.update(100.0)
    s.reset()
    assert s.get_latency() == 0.0


def test_windowed_mean_initial_value_ms() -> None:
    s = WindowedMeanLatency(window_size=3, initial_value_ms=100.0)
    assert s.get_latency() == 100.0


def test_windowed_mean_reset_returns_initial_value() -> None:
    s = WindowedMeanLatency(window_size=3, initial_value_ms=100.0)
    s.update(50.0)
    s.reset()
    assert s.get_latency() == 100.0


def test_windowed_mean_overrides_initial_after_updates() -> None:
    s = WindowedMeanLatency(window_size=3, initial_value_ms=100.0)
    s.update(10.0)
    s.update(20.0)
    s.update(30.0)
    assert abs(s.get_latency() - 20.0) < 0.1


def test_ema_initial_value_ms() -> None:
    s = EMALatency(alpha=0.3, initial_value_ms=50.0)
    assert s.get_latency() == 50.0


def test_ema_reset_returns_initial_value() -> None:
    s = EMALatency(alpha=0.3, initial_value_ms=50.0)
    s.update(100.0)
    s.reset()
    assert s.get_latency() == 50.0


def test_ema_overrides_initial_after_update() -> None:
    s = EMALatency(alpha=0.3, initial_value_ms=50.0)
    s.update(100.0)
    assert s.get_latency() == 100.0  # First sample replaces initial
