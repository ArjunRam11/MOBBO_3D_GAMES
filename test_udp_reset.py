#!/usr/bin/env python3
"""
Test UDP Reset Command Communication

This script tests the reset command flow:
1. Sends reset command to Python on port 9000
2. Waits for acknowledgments from Python on port 9001
3. Prints status and timing information

Usage:
    python test_udp_reset.py

Requirements:
    - main.py must be running and listening on port 9000
    - No other process should be listening on port 9001
"""

import socket
import json
import time
import sys


def test_reset_command(target_host="127.0.0.1", target_port=9000, ack_port=9001, timeout=5.0):
	"""
	Test reset command communication

	Args:
		target_host: Target IP address for reset command (default: localhost)
		target_port: Target UDP port for reset command (default: 9000)
		ack_port: Local port to listen for acknowledgments (default: 9001)
		timeout: Maximum time to wait for acknowledgments (default: 5.0s)

	Returns:
		dict: Test results with status and timing info
	"""
	print("\n" + "=" * 70)
	print("UDP RESET COMMAND TEST")
	print("=" * 70)

	results = {
		"command_sent": False,
		"ack_received_received": False,
		"ack_completed_received": False,
		"errors": [],
		"timing": {}
	}

	# Create command socket
	print("\n[1/4] Creating command socket...")
	try:
		command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		print("  ✅ Command socket created")
	except Exception as e:
		error_msg = f"Failed to create command socket: {e}"
		print(f"  ❌ {error_msg}")
		results["errors"].append(error_msg)
		return results

	# Create reset command
	print("\n[2/4] Creating reset command...")
	reset_command = {
		"type": "reset_board",
		"action": "stop_all_threads",
		"timestamp": int(time.time() * 1000)
	}
	json_str = json.dumps(reset_command)
	print(f"  Command: {json_str}")
	print(f"  Size: {len(json_str)} bytes")

	# Send command
	print(f"\n[3/4] Sending command to {target_host}:{target_port}...")
	command_send_time = time.time()
	try:
		bytes_sent = command_socket.sendto(json_str.encode('utf-8'), (target_host, target_port))
		print(f"  ✅ Command sent ({bytes_sent} bytes)")
		results["command_sent"] = True
		results["timing"]["command_sent"] = command_send_time
	except Exception as e:
		error_msg = f"Failed to send reset command: {e}"
		print(f"  ❌ {error_msg}")
		results["errors"].append(error_msg)
		command_socket.close()
		return results

	# Listen for acknowledgments
	print(f"\n[4/4] Listening for acknowledgments on port {ack_port}...")
	print(f"  Timeout: {timeout} seconds")

	try:
		ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		ack_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		ack_socket.bind(("127.0.0.1", ack_port))
		ack_socket.settimeout(timeout)
		print(f"  ✅ Bound to port {ack_port}")
	except Exception as e:
		error_msg = f"Failed to bind ACK socket on port {ack_port}: {e}"
		print(f"  ❌ {error_msg}")
		results["errors"].append(error_msg)
		command_socket.close()
		return results

	# Receive acknowledgments
	start_time = time.time()
	ack_count = 0

	while True:
		elapsed = time.time() - start_time
		if elapsed > timeout:
			print(f"\n  ⏱️  Timeout ({timeout}s) - no more acknowledgments")
			break

		try:
			data, addr = ack_socket.recvfrom(1024)
			ack_received_time = time.time()
			ack_count += 1

			try:
				response = json.loads(data.decode('utf-8'))

				if response.get("type") == "reset_ack":
					status = response.get("status", "unknown")
					print(f"\n  ✅ ACK #{ack_count} received (status={status})")
					print(f"     From: {addr}")
					print(f"     Latency: {(ack_received_time - command_send_time) * 1000:.1f}ms")

					if status == "received":
						results["ack_received_received"] = True
						results["timing"]["ack_received"] = ack_received_time
						print("     [Python received the reset command]")

					elif status == "completed":
						results["ack_completed_received"] = True
						results["timing"]["ack_completed"] = ack_received_time
						print("     [Python completed the reset and re-detected boards]")

					elif status == "error":
						error_detail = response.get("error", "unknown")
						print(f"     ❌ [Python error: {error_detail}]")
						results["errors"].append(f"Python error: {error_detail}")
				else:
					print(f"  ⚠️  Received non-reset ACK: {response}")

			except json.JSONDecodeError as e:
				print(f"  ⚠️  Failed to parse ACK as JSON: {e}")
				print(f"     Raw data: {data[:100]}")

		except socket.timeout:
			# This is expected when timeout expires
			pass
		except Exception as e:
			error_msg = f"Error receiving ACK: {e}"
			print(f"  ⚠️  {error_msg}")
			results["errors"].append(error_msg)
			break

	# Cleanup
	command_socket.close()
	ack_socket.close()

	# Print summary
	print("\n" + "=" * 70)
	print("TEST SUMMARY")
	print("=" * 70)
	print(f"Command sent:        {'✅ YES' if results['command_sent'] else '❌ NO'}")
	print(f"ACK (received):      {'✅ YES' if results['ack_received_received'] else '❌ NO'}")
	print(f"ACK (completed):     {'✅ YES' if results['ack_completed_received'] else '❌ NO'}")

	if results["timing"]:
		print(f"\nTiming:")
		if "ack_received" in results["timing"] and results["command_sent"]:
			latency_1 = (results["timing"]["ack_received"] - results["timing"]["command_sent"]) * 1000
			print(f"  Command -> ACK(received):  {latency_1:.1f}ms")

		if "ack_completed" in results["timing"] and results["command_sent"]:
			latency_2 = (results["timing"]["ack_completed"] - results["timing"]["command_sent"]) * 1000
			print(f"  Command -> ACK(completed): {latency_2:.1f}ms")

	if results["errors"]:
		print(f"\nErrors: {len(results['errors'])}")
		for error in results["errors"]:
			print(f"  - {error}")

	# Final status
	print("\n" + "=" * 70)
	if results["ack_completed_received"]:
		print("✅ TEST PASSED - Reset command processed successfully!")
	elif results["ack_received_received"]:
		print("⚠️  TEST PARTIAL - ACK(received) but not ACK(completed)")
		print("   Python may still be processing the reset")
	elif results["command_sent"]:
		print("❌ TEST FAILED - No acknowledgments received from Python")
		print("   Check if main.py is running and listening on port 9000")
	else:
		print("❌ TEST FAILED - Could not send command")

	print("=" * 70 + "\n")

	return results


def main():
	"""Main entry point"""
	try:
		results = test_reset_command()

		# Exit with appropriate code
		if results["ack_completed_received"]:
			sys.exit(0)  # Success
		elif results["command_sent"]:
			sys.exit(1)  # Command sent but no full response
		else:
			sys.exit(2)  # Failed to send

	except KeyboardInterrupt:
		print("\n\n❌ Test interrupted by user")
		sys.exit(3)
	except Exception as e:
		print(f"\n\n❌ Unexpected error: {e}")
		import traceback
		traceback.print_exc()
		sys.exit(4)


if __name__ == "__main__":
	main()
