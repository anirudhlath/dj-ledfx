import pytest

from dj_ledfx.latency.strategies import (
    STRATEGIES,
    EMALatency,
    ProbeStrategy,
    StaticLatency,
    WindowedMeanLatency,
    WindowedMedianLatency,
    make_strategy,
)


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


# Review Focus 3: a light whose latency jumps and stays high is followed.
@pytest.mark.parametrize(
    "strategy",
    [
        EMALatency(initial_value_ms=10.0),
        WindowedMedianLatency(window_size=9, initial_value_ms=10.0),
    ],
    ids=["ema", "windowed_median"],
)
def test_a_latency_that_jumps_and_stays_is_followed(strategy: ProbeStrategy) -> None:
    for _ in range(20):
        strategy.update(20.0)
    for _ in range(10):
        strategy.update(80.0)
    assert strategy.get_latency() > 70.0


def test_the_ema_still_ignores_a_lone_spike() -> None:
    ema = EMALatency()
    for _ in range(10):
        ema.update(20.0)
    ema.update(300.0)
    ema.update(20.0)
    ema.update(300.0)  # never three in a row: still spikes
    assert ema.get_latency() == pytest.approx(20.0)


def test_the_median_shrugs_off_spikes_and_follows_a_level() -> None:
    median = WindowedMedianLatency(window_size=9, initial_value_ms=10.0)
    assert median.get_latency() == 10.0
    for sample in (20.0, 20.0, 300.0, 20.0, 20.0, 250.0, 20.0):
        median.update(sample)
    assert median.get_latency() == 20.0
    for _ in range(5):
        median.update(60.0)
    assert median.get_latency() == 60.0
    median.reset()
    assert median.get_latency() == 10.0


@pytest.mark.parametrize("name", STRATEGIES)
def test_every_strategy_a_config_names_can_be_made(name: str) -> None:
    assert make_strategy(name, 12.0, 9).get_latency() == 12.0  # seeded


def test_make_strategy_refuses_an_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown latency strategy 'fastest'"):
        make_strategy("fastest", 10.0, 9)
