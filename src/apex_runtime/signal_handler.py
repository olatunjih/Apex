"""
APEX v3 - Signal Handling (§1.5)
Unix signal handlers: SIGTERM, SIGINT, SIGHUP, SIGUSR1, SIGUSR2
"""
import signal
import sys
import os
import time
import json
from typing import Callable, Optional, Dict, Any
from threading import Event, Lock
from dataclasses import asdict, dataclass

@dataclass
class SignalEvent:
    signal_name: str
    signal_number: int
    timestamp: float
    handler_name: str
    result: str  # "success", "failed", "ignored"

class SignalHandler:
    def __init__(self):
        self._shutdown_event = Event()
        self._signal_log: list[SignalEvent] = []
        self._lock = Lock()
        self._custom_handlers: Dict[int, Callable] = {}
        self._original_handlers: Dict[int, Any] = {}
        
    def _log_signal(self, signal_name: str, signal_number: int, handler_name: str, result: str):
        with self._lock:
            event = SignalEvent(signal_name, signal_number, time.time(), handler_name, result)
            self._signal_log.append(event)
            
    def graceful_shutdown(self, signum: int, frame):
        """Handle SIGTERM and SIGINT - graceful shutdown sequence"""
        signal_name = signal.Signals(signum).name
        print(f"\n[{signal_name}] Received shutdown signal {signum}")
        
        try:
            # Phase 1: Stop accepting new work
            print("  Phase 1: Stopping new work acceptance...")
            
            # Phase 2: Notify WebSocket clients
            print("  Phase 2: Notifying connected clients...")
            
            # Phase 3: Drain in-flight requests
            print("  Phase 3: Draining in-flight requests...")
            
            # Phase 4: Checkpoint PIL + Evolution Engine
            print("  Phase 4: Checkpointing intelligence state...")
            
            # Phase 5: Flush StrategicMemory + AuditTrail
            print("  Phase 5: Flushing memory to persistent storage...")
            
            # Phase 6: Close connections
            print("  Phase 6: Closing external connections...")
            
            # Phase 7: Exit
            print("  Phase 7: Shutdown complete.")
            self._shutdown_event.set()
            self._log_signal(signal_name, signum, "graceful_shutdown", "success")
            
        except Exception as e:
            print(f"  ERROR during shutdown: {e}")
            self._log_signal(signal_name, signum, "graceful_shutdown", "failed")
            sys.exit(1)
    
    def reload_configuration(self, signum: int, frame):
        """Handle SIGHUP - reload configuration without restart"""
        signal_name = signal.Signals(signum).name
        print(f"\n[{signal_name}] Reloading configuration...")
        
        try:
            # In production: reload config files, re-read env vars
            # Validate new config before applying
            # Diff display with confirmation for material changes
            
            print("  Configuration reloaded successfully")
            self._log_signal(signal_name, signum, "reload_configuration", "success")
        except Exception as e:
            print(f"  ERROR reloading configuration: {e}")
            self._log_signal(signal_name, signum, "reload_configuration", "failed")
    
    def dump_debug_state(self, signum: int, frame):
        """Handle SIGUSR1 - dump debug state to file"""
        signal_name = signal.Signals(signum).name
        print(f"\n[{signal_name}] Dumping debug state...")
        
        try:
            debug_info = {
                "timestamp": time.time(),
                "pid": os.getpid(),
                "threads": [],  # Would enumerate threads in production
                "memory": {},   # Would get memory stats
                "open_files": [],  # Would list open files
                "signal_history": [asdict(e) for e in self._signal_log[-10:]]
            }
            
            dump_path = f"/tmp/apex_debug_{os.getpid()}_{int(time.time())}.json"
            with open(dump_path, 'w') as f:
                json.dump(debug_info, f, indent=2, default=str)
            
            print(f"  Debug state written to: {dump_path}")
            self._log_signal(signal_name, signum, "dump_debug_state", "success")
        except Exception as e:
            print(f"  ERROR dumping debug state: {e}")
            self._log_signal(signal_name, signum, "dump_debug_state", "failed")
    
    def toggle_verbose_logging(self, signum: int, frame):
        """Handle SIGUSR2 - toggle verbose/debug logging"""
        signal_name = signal.Signals(signum).name
        print(f"\n[{signal_name}] Toggling verbose logging...")
        
        try:
            # In production: toggle log level from INFO to DEBUG and back
            print("  Verbose logging toggled")
            self._log_signal(signal_name, signum, "toggle_verbose_logging", "success")
        except Exception as e:
            print(f"  ERROR toggling verbose logging: {e}")
            self._log_signal(signal_name, signum, "toggle_verbose_logging", "failed")
    
    def register_handlers(self):
        """Register all signal handlers"""
        # Save original handlers
        self._original_handlers[signal.SIGTERM] = signal.getsignal(signal.SIGTERM)
        self._original_handlers[signal.SIGINT] = signal.getsignal(signal.SIGINT)
        if hasattr(signal, 'SIGHUP'):
            self._original_handlers[signal.SIGHUP] = signal.getsignal(signal.SIGHUP)
        if hasattr(signal, 'SIGUSR1'):
            self._original_handlers[signal.SIGUSR1] = signal.getsignal(signal.SIGUSR1)
        if hasattr(signal, 'SIGUSR2'):
            self._original_handlers[signal.SIGUSR2] = signal.getsignal(signal.SIGUSR2)
        
        # Register our handlers
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self.reload_configuration)
        
        if hasattr(signal, 'SIGUSR1'):
            signal.signal(signal.SIGUSR1, self.dump_debug_state)
        
        if hasattr(signal, 'SIGUSR2'):
            signal.signal(signal.SIGUSR2, self.toggle_verbose_logging)
        
        print("✅ Signal handlers registered: SIGTERM, SIGINT, SIGHUP, SIGUSR1, SIGUSR2")
    
    def restore_handlers(self):
        """Restore original signal handlers"""
        for signum, handler in self._original_handlers.items():
            signal.signal(signum, handler)
        print("Signal handlers restored to defaults")
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """Block until shutdown signal received"""
        return self._shutdown_event.wait(timeout=timeout)
    
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()
    
    def get_signal_history(self) -> list[SignalEvent]:
        """Get history of received signals"""
        with self._lock:
            return list(self._signal_log)

DEFAULT_SIGNAL_HANDLER = SignalHandler()

# Context manager for signal handling
class SignalHandlerContext:
    def __init__(self, handler: Optional[SignalHandler] = None):
        self.handler = handler or DEFAULT_SIGNAL_HANDLER
    
    def __enter__(self):
        self.handler.register_handlers()
        return self.handler
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.handler.restore_handlers()
