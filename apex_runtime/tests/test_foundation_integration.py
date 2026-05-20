"""
APEX v3 — Integration Test for New Foundation Modules
Tests Sections 1.5, 1.7, 1.8 functionality with real scenarios
"""

import time
import threading
from apex_runtime import (
    MemoryGuard, BoundedCache,
    HealthCheckSystem, SignalHandler,
    RuntimePhase
)


def test_memory_guard_integration():
    """Test MemoryGuard with realistic workload simulation."""
    print("\n=== Testing MemoryGuard Integration ===")
    
    alerts_received = []
    restart_triggered = False
    
    def alert_handler(msg, stats):
        alerts_received.append((msg, stats.alert_count))
        print(f"  [ALERT #{stats.alert_count}] {msg}")
    
    def restart_handler():
        nonlocal restart_triggered
        restart_triggered = True
        print("  [RESTART] Graceful restart triggered")
    
    # Create guard with reasonable thresholds for testing
    guard = MemoryGuard(
        max_rss_mb=2048.0,  # 2GB ceiling
        leak_threshold_mb_per_hour=100.0,
        snapshot_interval_sec=2.0,
        alert_callback=alert_handler,
        restart_callback=restart_handler
    )
    
    # Start monitoring
    guard.start()
    time.sleep(1)
    
    # Simulate workload with bounded caches
    caches = []
    for i in range(5):
        cache = guard.get_bounded_cache(max_size=100)
        # Fill cache
        for j in range(150):  # Exceed max to trigger evictions
            cache[f"key_{i}_{j}"] = {"data": j * 1000}
        caches.append(cache)
    
    # Check memory stats
    stats = guard.check_memory()
    print(f"  RSS: {stats.last_snapshot.rss_mb:.2f}MB")
    print(f"  Peak: {stats.peak_rss_mb:.2f}MB")
    print(f"  Heap: {stats.last_snapshot.heap_mb:.2f}MB")
    print(f"  Total evictions: {sum(c.eviction_count for c in caches)}")
    
    # Verify bounded cache behavior
    total_evictions = sum(c.eviction_count for c in caches)
    assert total_evictions > 0, "No evictions occurred - bounded cache not working"
    assert len(caches[0]) == 100, f"Cache size {len(caches[0])} != 100"
    
    # Stop monitoring
    guard.stop()
    
    print("  ✓ MemoryGuard integration test PASSED")
    return True


def test_health_check_integration():
    """Test HealthCheckSystem with realistic check scenarios."""
    print("\n=== Testing HealthCheckSystem Integration ===")
    
    health = HealthCheckSystem(version="3.0.0")
    
    # Register realistic checks
    check_results = {
        'database': True,
        'cache': True,
        'vendor_api': True,
        'llm_provider': False,  # Simulate failure
    }
    
    def make_check(name, is_critical=False):
        def check_fn():
            passed = check_results.get(name, True)
            latency = 5.0 + hash(name) % 50  # Simulate varying latencies
            return (passed, f"{name} {'healthy' if passed else 'unavailable'}", latency)
        return check_fn
    
    health.register_check('ready_database', make_check('database'))
    health.register_check('ready_cache', make_check('cache'))
    health.register_check('critical_vendor', make_check('vendor_api', is_critical=True))
    health.register_check('critical_llm', make_check('llm_provider', is_critical=True))
    
    # Run all checks
    status = health.run_all_checks()
    print(f"  Overall status: {status.status}")
    print(f"  Checks executed: {len(status.checks)}")
    
    for name, result in sorted(status.checks.items()):
        symbol = "✓" if result['status'] == 'pass' else "✗"
        print(f"    {symbol} {name}: {result['status']} ({result['latency_ms']:.2f}ms)")
    
    # Verify critical failure makes system unhealthy
    assert status.status == 'unhealthy', "System should be unhealthy with critical failure"
    
    # Test individual endpoints
    live = health.get_live_status()
    assert live['status'] == 'alive', "Live check failed"
    print(f"  ✓ Live endpoint: {live['status']}")
    
    ready = health.get_ready_status()
    assert ready.status == 'unhealthy', "Ready check should reflect unhealthy state"
    print(f"  ✓ Ready endpoint: {ready.status}")
    
    startup = health.get_startup_status(RuntimePhase.SERVICES)
    assert startup['ready'] == True, "Startup check should show ready at SERVICES phase"
    print(f"  ✓ Startup endpoint: phase={startup['phase']}, ready={startup['ready']}")
    
    deep = health.get_deep_health()
    assert 'memory_info' in deep, "Deep health missing memory info"
    assert 'pid' in deep, "Deep health missing pid"
    print(f"  ✓ Deep health: pid={deep['pid']}, memory={deep['memory_info']}")
    
    # Simulate recovery
    check_results['llm_provider'] = True
    status_after = health.run_all_checks()
    print(f"  After recovery: {status_after.status}")
    assert status_after.status == 'healthy', "System should be healthy after recovery"
    
    print("  ✓ HealthCheckSystem integration test PASSED")
    return True


def test_signal_handler_integration():
    """Test SignalHandler setup and callback wiring."""
    print("\n=== Testing SignalHandler Integration ===")
    
    shutdown_called = False
    reload_called = False
    debug_dump_called = False
    logging_toggled = False
    
    captured_dump = {}
    
    def shutdown_fn():
        nonlocal shutdown_called
        shutdown_called = True
        print("  [SHUTDOWN] Callback executed")
    
    def reload_fn():
        nonlocal reload_called
        reload_called = True
        print("  [RELOAD] Configuration reloaded")
    
    def debug_dump_fn():
        nonlocal debug_dump_called
        debug_dump_called = True
        return {"runtime_state": "test", "timestamp": time.time()}
    
    def toggle_logging_fn():
        nonlocal logging_toggled
        logging_toggled = True
        print("  [LOGGING] Verbose mode toggled")
    
    # Create handler (don't actually install signals in test)
    handler = SignalHandler(
        shutdown_callback=shutdown_fn,
        reload_callback=reload_fn,
        debug_dump_callback=debug_dump_fn,
        toggle_logging_callback=toggle_logging_fn
    )
    
    # Manually trigger handlers to test callbacks
    print("  Testing callback wiring...")
    
    # Simulate SIGTERM
    handler._handle_shutdown(15, None)  # 15 = SIGTERM
    assert shutdown_called, "Shutdown callback not called"
    assert handler.shutdown_requested, "Shutdown flag not set"
    
    # Simulate SIGHUP
    handler._handle_reload(1, None)
    assert reload_called, "Reload callback not called"
    
    # Simulate SIGUSR1
    handler._handle_debug_dump(10, None)
    assert debug_dump_called, "Debug dump callback not called"
    
    # Simulate SIGUSR2
    handler._handle_toggle_logging(12, None)
    assert logging_toggled, "Toggle logging callback not called"
    
    print("  ✓ All signal callbacks properly wired")
    print("  ✓ SignalHandler integration test PASSED")
    return True


def test_concurrent_operation():
    """Test all systems operating concurrently."""
    print("\n=== Testing Concurrent Operation ===")
    
    health = HealthCheckSystem()
    guard = MemoryGuard(
        max_rss_mb=2048.0,
        snapshot_interval_sec=1.0
    )
    
    # Start both systems
    guard.start()
    
    # Register health checks that use guarded resources
    shared_cache = guard.get_bounded_cache(1000)
    
    def cache_check():
        try:
            # Simulate cache access
            shared_cache[f"check_{time.time()}"] = True
            return (True, "Cache operational", 2.0)
        except Exception as e:
            return (False, str(e), 0.0)
    
    health.register_check('ready_cache', cache_check)
    
    # Run concurrent operations
    results = []
    
    def health_monitor():
        for _ in range(5):
            status = health.run_all_checks()
            results.append(('health', status.status))
            time.sleep(0.1)
    
    def memory_monitor():
        for _ in range(5):
            stats = guard.check_memory()
            results.append(('memory', stats.last_snapshot.rss_mb))
            time.sleep(0.1)
    
    # Run both monitors concurrently
    t1 = threading.Thread(target=health_monitor)
    t2 = threading.Thread(target=memory_monitor)
    
    t1.start()
    t2.start()
    
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)
    
    # Verify results
    assert len(results) == 10, f"Expected 10 results, got {len(results)}"
    health_checks = [r for r in results if r[0] == 'health']
    memory_checks = [r for r in results if r[0] == 'memory']
    
    assert len(health_checks) == 5, "Health checks not running"
    assert len(memory_checks) == 5, "Memory checks not running"
    
    # All health checks should pass
    for _, status in health_checks:
        assert status == 'healthy', f"Health check failed: {status}"
    
    print(f"  Executed {len(health_checks)} health checks, {len(memory_checks)} memory checks")
    print("  ✓ Concurrent operation test PASSED")
    
    # Cleanup
    guard.stop()
    
    return True


def run_all_integration_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("APEX v3 — Foundation Modules Integration Tests")
    print("Sections: 1.5 (Signals), 1.7 (Memory), 1.8 (Health)")
    print("=" * 60)
    
    tests = [
        ("Memory Guard", test_memory_guard_integration),
        ("Health Check System", test_health_check_integration),
        ("Signal Handler", test_signal_handler_integration),
        ("Concurrent Operation", test_concurrent_operation),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"  ✗ {name} FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    
    for name, passed_flag, error in results:
        symbol = "✓ PASS" if passed_flag else "✗ FAIL"
        print(f"  {symbol}: {name}")
        if error:
            print(f"    Error: {error}")
    
    print(f"\nTotal: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        print("\n🎉 ALL INTEGRATION TESTS PASSED")
        return True
    else:
        print(f"\n❌ {total - passed_count} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = run_all_integration_tests()
    exit(0 if success else 1)
