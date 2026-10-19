"""Unit and integration tests for AudioEngine lifecycle and error handling."""

import time
import pytest
from src.audio.devices import DeviceManager
from src.audio.engine import AudioEngine, EngineState


def test_engine_init():
    """Verify initial engine state and default metrics."""
    mgr = DeviceManager()
    engine = AudioEngine(device_manager=mgr)

    assert engine.state == EngineState.STOPPED
    metrics = engine.get_metrics()
    assert metrics["state"] == "Stopped"
    assert "main_peak" in metrics
    assert "bass_peak" in metrics
    mgr.close()


def test_engine_parameter_updates():
    """Verify runtime parameter adjustments update DSP and delay objects without error."""
    mgr = DeviceManager()
    engine = AudioEngine(device_manager=mgr)

    engine.set_parameters(
        crossover_freq=150.0,
        bass_gain_db=3.0,
        main_volume=0.8,
        bass_volume=1.2,
        bass_delay_ms=180.0,
        bass_muted=False,
        bass_split_enabled=True
    )

    assert engine.dsp.crossover_freq == 150.0
    assert engine.dsp.bass_gain_db == 3.0
    assert engine.dsp.main_volume == 0.8
    assert engine.delay_line.delay_ms == 180.0
    mgr.close()


def test_engine_start_stop():
    """Verify starting and cleanly stopping the engine with actual hardware endpoints."""
    mgr = DeviceManager()
    engine = AudioEngine(device_manager=mgr)

    outputs = mgr.get_output_devices()
    assert len(outputs) >= 1

    main_name = outputs[0].name
    bass_name = outputs[1].name if len(outputs) > 1 else outputs[0].name

    state_changes = []
    engine.on_state_changed = lambda s, err: state_changes.append(s)

    # Start engine
    started = engine.start(main_device_name=main_name, bass_device_name=bass_name, buffer_size=1024)
    assert started is True
    assert engine.state == EngineState.RUNNING

    # Run for 0.5s to verify threads process buffers
    time.sleep(0.5)

    metrics = engine.get_metrics()
    assert metrics["state"] == "Running"
    assert metrics["capture_rate"] > 0

    # Clean stop
    engine.stop()
    assert engine.state == EngineState.STOPPED
    mgr.close()


def test_missing_device_error_handling():
    """Verify requesting a non-existent device handles errors gracefully without crashing."""
    mgr = DeviceManager()
    engine = AudioEngine(device_manager=mgr)

    # Even with an arbitrary or missing device name, engine resolves to a safe available fallback
    # or sets state to ERROR cleanly without unhandled exceptions
    started = engine.start(main_device_name="FakeDeviceThatDoesNotExist", bass_device_name="FakeBassDevice")
    if not started:
        assert engine.state == EngineState.ERROR
        assert len(engine.error_message) > 0
    else:
        # If it fell back gracefully, state should be RUNNING and clean stop works
        assert engine.state == EngineState.RUNNING
        engine.stop()

    mgr.close()
