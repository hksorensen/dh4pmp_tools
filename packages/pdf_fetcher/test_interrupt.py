#!/usr/bin/env python3
"""
Test script to verify Ctrl+C interrupt handling.

Run this and press Ctrl+C twice:
- First Ctrl+C should print "shutting down gracefully"
- Second Ctrl+C should force quit immediately

Usage:
    python test_interrupt.py
"""
import time
import signal

# Simulate the PDFFetcher signal handling
_interrupt_count = 0

def signal_handler(signum, frame):
    import os
    global _interrupt_count
    _interrupt_count += 1

    if _interrupt_count == 1:
        print(f"\n⚠ SIGINT received - shutting down gracefully...")
        print("  (Press Ctrl+C again to force quit)")
    else:
        print(f"\n⚠ Force quit (interrupt #{_interrupt_count})")
        os._exit(1)

signal.signal(signal.SIGINT, signal_handler)

print("Test script running. Press Ctrl+C to test interrupt handling.")
print("First Ctrl+C: graceful shutdown message")
print("Second Ctrl+C: force quit with os._exit(1)")
print()

# Simulate long-running work
for i in range(1000):
    print(f"Working... {i}/1000 (interrupt_count={_interrupt_count})")
    time.sleep(1)

    # Check if interrupted (simulating the polling loop)
    if _interrupt_count > 0:
        print("Detected interrupt, cleaning up...")
        time.sleep(2)  # Simulate cleanup
        print("Cleanup done, but still running (press Ctrl+C again to force quit)")
