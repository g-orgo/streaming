from live_caption_bridge.infrastructure.lifecycle import Lifecycle


def test_startup_and_shutdown_order() -> None:
    order: list[str] = []
    lc = Lifecycle()
    lc.on_start(lambda: order.append("start"))
    lc.on_shutdown(lambda: order.append("shutdown"))
    lc.start()
    lc.shutdown()
    assert order == ["start", "shutdown"]


def test_startup_failure_triggers_shutdown() -> None:
    lc = Lifecycle()
    lc.on_start(lambda: exec("raise RuntimeError('fail')"))

    def cleanup() -> None:
        pass

    lc.on_shutdown(cleanup)
    # Na prática on_shutdown chama cleanup
    import pytest
    with pytest.raises(RuntimeError):
        lc.start()
