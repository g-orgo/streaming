from live_caption_bridge.services.resource_governor import ResourceGovernor


def test_degradation_triggers_on_high_queue() -> None:
    g = ResourceGovernor(queue_max=5, check_interval_s=0)
    actions: list[str] = []
    g.on_degradation(lambda msg: actions.append(msg))
    g.check(10)
    assert "fps_reduced" in actions


def test_no_degradation_when_queue_below_limit() -> None:
    g = ResourceGovernor(queue_max=5, check_interval_s=0)
    actions: list[str] = []
    g.on_degradation(lambda msg: actions.append(msg))
    g.check(3)
    assert len(actions) == 0
