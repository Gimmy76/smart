#!/usr/bin/env python3

import sys
import os
import json

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=== Testing Network Module Host Grouping ===")

try:
    # Import Shared module
    import Shared as shared

    # Create a mock configuration
    config = {
        'servers': '[hs]',
        'attackers': '[h5]',
        'manuel_receivers': True,
        'unified_host_bandwidth': None,
        'unified_switch_bandwidth': None,
        'hosts_topo_file': 'hosts-topology-10hosts-2_3_2_3'
    }

    # Initialize the shared globals
    shared.init(config)

    # First test: loading groups from a JSON file
    # Create a test JSON file
    test_groups = {
        "group_0": {
            "hosts": ["h5"],
            "type": "attacker",
            "switch": "s102"
        },
        "group_1": {
            "hosts": ["h1", "h2"],
            "type": "normal",
            "switch": "s101"
        },
        "group_2": {
            "hosts": ["h3", "h4"],
            "type": "normal",
            "switch": "s102"
        }
    }

    tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../reinforcement/tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    json_path = os.path.join(tmp_dir, 'test_groups.json')

    with open(json_path, 'w') as f:
        json.dump(test_groups, f, indent=2)

    print(f"Created test groups file at: {json_path}")

    # Import and initialize the HostGrouper
    from HostGrouping import HostGrouper
    host_grouper = HostGrouper(shared.GLOBALS)

    # Load groups from file
    loaded_groups = host_grouper.create_host_groups(json_path)
    print(f"Loaded {len(loaded_groups)} groups from file")

    # Verify the groups loaded correctly
    match = True
    for group_name, group_info in test_groups.items():
        if group_name not in loaded_groups:
            match = False
            print(f"Group {group_name} missing from loaded groups")
        elif sorted(group_info['hosts']) != sorted(loaded_groups[group_name]['hosts']):
            match = False
            print(f"Group {group_name} hosts don't match")
            print(f"Expected: {group_info['hosts']}")
            print(f"Actual: {loaded_groups[group_name]['hosts']}")

    if match:
        print("Groups loaded correctly from file")
    else:
        print("Groups don't match after loading from file")

    # Second test: calculating groups dynamically
    # First clear the host_groups_json_path to force dynamic calculation
    shared.GLOBALS.host_groups_json_path = None

    # Populate the necessary data structures in GLOBALS for grouping
    shared.GLOBALS.client_hosts_list = ["h1", "h2", "h3", "h4", "h5", "h6"]
    shared.GLOBALS.host_default_switch_relation = {
        "h1": {"default_path_switch": "s101"},
        "h2": {"default_path_switch": "s101"},
        "h3": {"default_path_switch": "s102"},
        "h4": {"default_path_switch": "s102"},
        "h5": {"default_path_switch": "s102"},
        "h6": {"default_path_switch": "s103"}
    }
    shared.GLOBALS.controlled_switches_list = ["s101", "s102", "s103", "s104"]

    # Calculate groups dynamically
    try:
        dynamic_groups = host_grouper._calculate_host_groups()
        print(f"Calculated {len(dynamic_groups)} groups dynamically")

        # Print the groups
        for group_name, group_info in dynamic_groups.items():
            print(f"Group {group_name}:")
            print(f"  Type: {group_info['type']}")
            print(f"  Switch: {group_info['switch']}")
            print(f"  Hosts: {group_info['hosts']}")

        # Check if host_to_group_map was created
        if hasattr(shared.GLOBALS, 'host_to_group_map') and shared.GLOBALS.host_to_group_map:
            print("Host-to-group mapping created:")
            for host, group in shared.GLOBALS.host_to_group_map.items():
                print(f"  Host {host} -> Group {group}")
        else:
            print("ERROR: Host-to-group mapping not created")
    except Exception as e:
        print(f"Error during dynamic group calculation: {str(e)}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"Error during test: {str(e)}")
    import traceback
    traceback.print_exc()

print("=== Test completed ===")