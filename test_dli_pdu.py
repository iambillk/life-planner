#!/usr/bin/env python3
"""
DLI PDU Connection Test Script
Version: 1.0.0
Last Modified: 2025-01-XX
Author: Billas
Description: Test script to verify DLI PDU connection and functionality

File: /test_dli_pdu.py

CHANGELOG:
- 1.0.0 (2025-01-XX): Initial test script for DLI PDU integration

USAGE:
    python test_dli_pdu.py

NOTES:
- Run this before integrating into the main app
- Requires the DLI PDU to be on the network
- Update IP, username, and password in the script
"""

import sys
import time
from pprint import pprint

# Add parent directory to path so we can import our modules
sys.path.insert(0, '.')

# We need to create a minimal Flask app context for config
from flask import Flask
from config import Config

# Create minimal app for testing
app = Flask(__name__)
app.config.from_object(Config)

def test_dli_pdu():
    """
    Test DLI PDU connection and basic operations.
    """
    print("=" * 60)
    print("DLI PDU CONNECTION TEST")
    print("=" * 60)
    
    # Import within app context
    with app.app_context():
        from modules.ops_center.dli_pdu import DLIPduAPI
        
        # Initialize PDU connection
        print("\n1. Initializing DLI PDU connection...")
        print(f"   Host: {app.config.get('DLI_PDU_HOST')}")
        print(f"   User: {app.config.get('DLI_PDU_USER')}")
        
        pdu = DLIPduAPI()
        
        # Test connection
        print("\n2. Testing connection...")
        if pdu.test_connection():
            print("   ✓ Connection successful!")
        else:
            print("   ✗ Connection failed!")
            print("   Please check:")
            print("   - PDU IP address is correct")
            print("   - PDU is powered on and on the network")
            print("   - REST API is enabled on the PDU")
            print("   - Username and password are correct")
            return False
        
        # Get all outlets
        print("\n3. Getting outlet status...")
        outlets = pdu.get_all_outlets()
        
        if outlets:
            print(f"   ✓ Found {len(outlets)} outlets:")
            print("\n   Outlet Status:")
            print("   " + "-" * 50)
            print("   ID | Name                | State | Locked")
            print("   " + "-" * 50)
            
            for outlet in outlets:
                state_str = "ON " if outlet['physical_state'] else "OFF"
                locked_str = "Yes" if outlet['locked'] else "No"
                print(f"   {outlet['number']:2} | {outlet['name']:20} | {state_str:3} | {locked_str}")
        else:
            print("   ✗ Failed to get outlet status")
        
        # Get power status
        print("\n4. Getting power consumption...")
        power = pdu.get_power_status()
        
        if power:
            print(f"   ✓ Power Status:")
            print(f"     Current: {power['current_amps']:.1f} A")
            print(f"     Maximum: {power['max_amps']} A")
            print(f"     Voltage: {power['voltage']} V")
            print(f"     Watts:   {power['watts']:.0f} W")
            utilization = (power['current_amps'] / power['max_amps']) * 100
            print(f"     Load:    {utilization:.1f}%")
        else:
            print("   ⚠ Power monitoring may not be available on this model")
        
        # Test outlet control (optional - uncomment to test)
        print("\n5. Outlet Control Test")
        print("   (Skipping actual control to avoid disrupting equipment)")
        print("   To test outlet control, uncomment the test section")
        
        """
        # UNCOMMENT TO TEST OUTLET CONTROL
        # WARNING: This will turn outlet 8 off and on!
        test_outlet = 7  # Outlet 8 (0-based index)
        
        print(f"\n   Testing outlet {test_outlet + 1} control...")
        current_state = outlets[test_outlet]['physical_state'] if test_outlet < len(outlets) else False
        print(f"   Current state: {'ON' if current_state else 'OFF'}")
        
        # Turn off
        print("   Turning OFF...")
        if pdu.set_outlet_state(test_outlet, False):
            print("   ✓ Command sent")
            time.sleep(2)
            
            # Turn back on
            print("   Turning ON...")
            if pdu.set_outlet_state(test_outlet, True):
                print("   ✓ Command sent")
            else:
                print("   ✗ Failed to turn on")
        else:
            print("   ✗ Failed to turn off")
        """
        
        # Test AutoPing configuration
        print("\n6. Checking AutoPing configuration...")
        autoping = pdu.get_autoping_config()
        
        if autoping:
            print(f"   ✓ AutoPing is configured")
            # Note: Response format varies by model
        else:
            print("   ⚠ AutoPing not configured or not available")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
        return True

if __name__ == "__main__":
    print("\nDLI PDU Integration Test")
    print("Version 1.0.0")
    print("-" * 60)
    
    # Check if config exists
    try:
        if test_dli_pdu():
            print("\n✓ All tests passed! DLI PDU is ready for integration.")
            print("\nNext steps:")
            print("1. Update the dashboard template to show real outlet controls")
            print("2. Add JavaScript for interactive outlet control")
            print("3. Test with actual equipment (carefully!)")
        else:
            print("\n✗ Tests failed. Please fix issues before integration.")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)