#!/usr/bin/env python3

import json
import os

class HostGrouper:
    """
    Utility class for creating host groups in the network module.
    This is a duplicate of the logic in the reinforcement module,
    but adapted for the network context.
    """
    
    def __init__(self, network_globals):
        """
        Initialize the HostGrouper with network globals.
        
        Args:
            network_globals: The global variables object from the network module
        """
        self.globals = network_globals
        
    def create_host_groups(self, json_path=None):
        """
        Create host groups based on controlled switches.
        
        If json_path is provided, load groups from the JSON file.
        Otherwise, calculate groups dynamically.
        
        Args:
            json_path: Path to a JSON file containing host groups
            
        Returns:
            A dictionary of host groups
        """
        if json_path and os.path.exists(json_path):
            print(f"Loading host groups from {json_path}")
            return self._load_host_groups_from_json(json_path)
        
        print("Calculating host groups dynamically")
        return self._calculate_host_groups()
    
    def _load_host_groups_from_json(self, json_path):
        """
        Load host groups from a JSON file.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            A dictionary of host groups
        """
        with open(json_path, 'r') as f:
            host_groups = json.load(f)
        
        # Create host-to-group mapping for easy reference
        host_to_group_map = {}
        for group_name, group_info in host_groups.items():
            for host in group_info['hosts']:
                host_to_group_map[host] = group_name
        
        # Store the mapping in the globals
        self.globals.host_to_group_map = host_to_group_map
        
        print(f"Loaded {len(host_groups)} host groups from {json_path}")
        return host_groups
    
    def _calculate_host_groups(self):
        """
        Calculate host groups dynamically.
        
        This is a duplicate of the logic in the reinforcement module,
        but adapted for the network context.
        
        Returns:
            A dictionary of host groups
        """
        # Initialize host groups
        host_groups = {}
        group_id = 0
        
        # Get the lists of hosts
        normal_hosts = [h for h in self.globals.client_hosts_list if h not in self.globals.attackers]
        attacker_hosts = self.globals.attackers
        controlled_switches = self.globals.controlled_switches_list
        
        # Debug output
        print(f"Creating host groups with {len(self.globals.client_hosts_list)} client hosts")
        print(f"Normal hosts: {normal_hosts}")
        print(f"Attacker hosts: {attacker_hosts}")
        print(f"Controlled switches: {controlled_switches}")
        
        # Safety check: If no hosts are available, create a placeholder group
        if not self.globals.client_hosts_list:
            print("WARNING: No client hosts found when creating groups")
            # Create a placeholder group for each controlled switch
            for switch in controlled_switches:
                host_groups[f"group_{group_id}"] = {
                    'hosts': [],
                    'type': 'placeholder',
                    'switch': switch
                }
                group_id += 1
            return host_groups
        
        # Step 1: Group hosts by their default controlled switch
        hosts_by_switch = {}
        for host in normal_hosts:
            if host not in self.globals.host_default_switch_relation:
                print(f"WARNING: Host {host} not found in host_default_switch_relation")
                continue
            
            default_switch = self.globals.host_default_switch_relation[host]['default_path_switch']
            print(f"Host {host} has default switch {default_switch}")
            
            # Initialize the lists if this is the first host for this switch
            if default_switch not in hosts_by_switch:
                hosts_by_switch[default_switch] = {'normal': [], 'attackers': []}
            
            hosts_by_switch[default_switch]['normal'].append(host)
        
        # Also group attackers by their default switch
        for host in attacker_hosts:
            if host not in self.globals.host_default_switch_relation:
                print(f"WARNING: Attacker {host} not found in host_default_switch_relation")
                continue
            
            default_switch = self.globals.host_default_switch_relation[host]['default_path_switch']
            
            # Initialize the lists if this is the first host for this switch
            if default_switch not in hosts_by_switch:
                hosts_by_switch[default_switch] = {'normal': [], 'attackers': []}
            
            hosts_by_switch[default_switch]['attackers'].append(host)
        
        # Step 2: Now create the actual groups
        for switch, hosts in hosts_by_switch.items():
            # Create a separate group for attackers if any
            if hosts['attackers']:
                host_groups[f"group_{group_id}"] = {
                    'hosts': hosts['attackers'],
                    'type': 'attacker',
                    'switch': switch
                }
                group_id += 1
            
            # Create 1-2 groups for normal hosts
            normal_hosts = hosts['normal']
            if normal_hosts:
                if len(normal_hosts) <= 4:  # For small number of hosts, just one group
                    host_groups[f"group_{group_id}"] = {
                        'hosts': normal_hosts,
                        'type': 'normal',
                        'switch': switch
                    }
                    group_id += 1
                else:  # Split into two groups
                    mid = len(normal_hosts) // 2
                    # First group
                    host_groups[f"group_{group_id}"] = {
                        'hosts': normal_hosts[:mid],
                        'type': 'normal',
                        'switch': switch
                    }
                    group_id += 1
                    # Second group
                    host_groups[f"group_{group_id}"] = {
                        'hosts': normal_hosts[mid:],
                        'type': 'normal',
                        'switch': switch
                    }
                    group_id += 1
        
        # Create host-to-group mapping for easy reference
        host_to_group_map = {}
        for group_name, group_info in host_groups.items():
            for host in group_info['hosts']:
                host_to_group_map[host] = group_name
        
        # Store the mapping in the globals
        self.globals.host_to_group_map = host_to_group_map
        
        # Print debug information
        print(f"Created {len(host_groups)} host groups")
        print("Host Groups created:")
        for group_name, group_info in host_groups.items():
            print(f"  {group_name}: {group_info['type']} hosts on {group_info['switch']}: {group_info['hosts']}")
        
        return host_groups