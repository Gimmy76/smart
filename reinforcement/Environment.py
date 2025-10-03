import os
import random
import csv
import time
from collections import deque

import numpy as np
import json

from scipy.stats import alpha

from Configuration import Configuration
from HttpClient import HttpClient
from CmdManager import CmdManager
from SwitchGrouping import SwitchGrouper
from decimal import Decimal
from Util import Util

import tensorflow as tf

class Environment():

    def __init__(self, config, pre_set_attackers):
        print("(Reinforcement) Environment.__init__()")
        self.episodes = config.episodes
        self.steps = config.steps
        self.step_duration = 55  # seconds
        self.attack_duration = 30  # seconds
        self.tshark_processing_duration = 15  # seconds
        self.transmission_time = self.step_duration - self.tshark_processing_duration  # = 40 seconds
        self.after_attack_duration = (
                                             self.step_duration - self.attack_duration) - self.tshark_processing_duration  # = 10 seconds
        self.tmp_dir = os.path.dirname(os.path.abspath(__file__)) + "/tmp"
        self.nbr_non_server_hosts = len(config.client_hosts_list)
        self.nbr_of_servers = 1
        self.nbr_hosts = self.nbr_non_server_hosts + self.nbr_of_servers
        self.hosts = []
        self.hosts_ips = {}
        self.normal_hosts_ips_array = []
        self.non_server_hosts_ordered = []
        self.interfaces = []
        self.servers = []
        h = sorted(config.client_hosts_list)
        h.remove(pre_set_attackers[0])
        self.default_normal_hosts = h
        self.normal_hosts = []
        self.attacker_hosts = []
        self.pre_set_attackers = pre_set_attackers
        self.victim_servers = []
        self.nbr_of_attackers = 1
        self.nbr_normal_hosts = self.nbr_hosts - (self.nbr_of_attackers + self.nbr_of_servers)
        self.router_switches_list = config.router_switches_list

        # Add hosts_raw_topo attribute
        self.hosts_raw_topo = config.hosts_raw_topo if hasattr(config, 'hosts_raw_topo') else {}

        # FROM CONFIG
        self.host_default_switch_relation = config.host_default_switch_relation
        self.router_to_host_relation = config.router_to_host_relation
        self.router_to_controlled_switch_relation = config.router_to_controlled_switch_relation
        self.host_to_router_relation = config.host_to_router_relation

        self.host_groups = {}
        self.host_to_group_map = {}
        self.switch_connections = {}
        self.switch_groups = []
        self.switch_to_switch_groups_map = {}

        # RL ENV
        #   # State
        self.nbr_controlled_switches = config.num_controlled_switches
        self.nbr_routing_switches = len(config.router_switches_list)
        self.nbr_central_switch = 1
        self.NBR_HOST_STATE_METRICS = 12
        self.nbr_of_network_metrics = 4
        self.arr_shape_data_per_routing_switch = (
            self.nbr_routing_switches, 1)  # vector of bw between routing and controlled switches
        self.arr_shape_data_per_host = (self.nbr_hosts, self.NBR_HOST_STATE_METRICS)
        self.arr_shape_data_per_host_for_path = (
            self.nbr_hosts - 1, self.nbr_controlled_switches)  # array of binary values for activated pathes
        self.arr_shape_data_per_host_for_network_metrics = (self.nbr_normal_hosts, self.nbr_of_network_metrics)
        # TODO: Uncomment if link_congestion
        # self.arr_shape_data_per_controlled_switch_for_s0 = (self.nbr_controlled_switches, 2)
        self.arr_shape_data_per_controlled_switch_for_s0 = (self.nbr_controlled_switches, 1)
        # TODO: Uncomment if link_congestion
        # self.arr_shape_data_per_controlled_switch_for_each_others = (int((self.nbr_controlled_switches-1) * self.nbr_controlled_switches / 2.0), 2)
        # self.arr_shape_data_per_controlled_switch_for_each_others = (
        #     int((self.nbr_controlled_switches - 1) * self.nbr_controlled_switches / 2.0), 1)

        self.routing_switches = []
        # Identify controlled switches from the host_default_switch_relation
        unique_controlled_switches = set()
        for host, relation in self.host_default_switch_relation.items():
            unique_controlled_switches.add(relation['default_path_switch'])

        self.controlled_switches = sorted(list(unique_controlled_switches))

        self.host_groups = self.create_host_groups(save_to_file=True)

        # NEW STATE
        self.nbr_of_controlled_switches_in_group = 4
        self.nbr_of_host_function_inputs = 14 + self.nbr_of_controlled_switches_in_group
        self.nbr_of_group_function_inputs = self.nbr_of_host_function_inputs * 4 + 1  # 4x for min/max/mean/std + utilization
        self.nbr_of_controlled_switches_function_inputs = (self.nbr_of_controlled_switches_in_group - 1) + self.nbr_of_servers

        # self.INPUT_SHAPE = int(
        #     self.nbr_non_server_hosts * self.nbr_of_host_function_inputs + self.nbr_of_controlled_switches_function_inputs)

        # NEW ACTIONS
        self.nbr_of_host_actions = 4
        self.nbr_of_group_actions = 4
        self.nbr_of_switch_actions = 2 * (self.nbr_controlled_switches + (
                self.nbr_controlled_switches * (self.nbr_of_controlled_switches_in_group - 1) / 2.0))

        # NN Functions
        # self.hi_model_input_size = self.nbr_of_host_function_inputs
        # self.hi_model_output_size = (self.nbr_of_host_function_inputs + self.nbr_of_host_actions) * 2
        # self.hoi_model_input_size = self.hi_model_input_size + self.hi_model_output_size + (
        #         self.nbr_of_controlled_switches_function_inputs * self.nbr_controlled_switches)
        # self.hoi_model_output_size = self.nbr_of_host_actions
        self.gi_model_input_size = self.nbr_of_group_function_inputs
        self.gi_model_output_size = (self.gi_model_input_size + self.nbr_of_group_actions) * 2
        self.goi_model_output_size = self.nbr_of_group_actions
        self.controlled_switches_layer_input = self.nbr_of_controlled_switches_function_inputs * self.nbr_controlled_switches
        self.s_model_input_size = self.gi_model_output_size + self.controlled_switches_layer_input
        # 2 for increase and decres, self.nbr_controlled_switches for controlled<->s0
        # (self.nbr_controlled_switches * (self.nbr_controlled_switches - 1) / 2.0) for controlled <-> controlled
        self.s_model_output_size = self.nbr_of_switch_actions

        #   # Actions
        self.NBR_POSSIBLE_HOST_REDIRECTIONS = self.nbr_of_host_actions
        self.NBR_POSSIBLE_CONTROLLED_SWITCH_BW_ACTIONS = 2
        self.DECREASE_BW = 0
        self.INCREASE_BW = 1
        self.OUTPUT_SHAPE = int((self.NBR_POSSIBLE_HOST_REDIRECTIONS * len(self.host_groups.keys())) \
                                + (self.NBR_POSSIBLE_CONTROLLED_SWITCH_BW_ACTIONS * self.nbr_controlled_switches) \
                                + (self.NBR_POSSIBLE_CONTROLLED_SWITCH_BW_ACTIONS * (
                (self.nbr_controlled_switches * (self.nbr_of_controlled_switches_in_group - 1)) / 2)) \
                                + 1)
        self.ACTIONS = []
        self.MAX_DO_NOTHING_ACTION_BEFORE_PENALTY = 5
        self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER = 0

        # Bandwidth
        self.MIN_BW = 0.01
        self.MAX_BW = 3.1
        self.MAX_SWITCH_BW = 9.1
        self.DECREASING_FACTOR = 0.3
        self.INCREASING_FACTOR = 0.3

        # Reward related factors
        self.alpha_packet_loss = 0  # nullifying alpha 0.05
        self.beta_delay = 1  # concentrating on delay 0.45
        self.tolerable_PKT_loss_percentage = 0.01
        self.tolerable_delay_ms = 2.0  # TODO: Check 29
        self.tolerable_latency_s = 0.0002  # TODO: Check 29
        self.tolerable_jitter_s = 0.0002  # TODO: Check 29
        self.max_PKT_loss_percentage = 0.8
        self.max_delay_ms = 2000  # TODO: Check 29 # originally 400
        self.max_latency_s = 2.5  # TODO: Check 29
        self.max_jitter_s = 2.5  # TODO: Check 29

        # Episode scope variables
        self.last_recorded_delay = 0.0
        self.last_recorded_latency = 0.0
        self.latency_tracker = ValuesTracker()
        self.last_recorded_jitter = 0.0
        self.jitter_tracker = ValuesTracker()
        self.before_last_recorded_delay = 0.0
        self.last_recorded_tx = {}
        self.host_last_recorded_interface_data = {}

        # Adding weights to past and new experiences in reward
        self.alpha_weight = 0.2

        # for reward third approach

        self.MIN_LATENCY_IMPROVEMENT = 0.002  # Minimal improvement in seconds
        self.MIN_JITTER_IMPROVEMENT = 0.002  # Minimal improvement in seconds

        # TODO: Future improvement (composite action)
        # self.DECREASE_BW = 0
        # self.STAY_BW = 1
        # self.INCREASE_BW = 2

        # Logging
        self.episode_actions_text_list = []

        # Other
        self.switch_grouping_file_path = config.switch_grouping_file_path

    def get_switch_groups_and_connections(self):
        """
        Extracts valid connections between switches from the network topology.
        
        Returns:
            A dictionary mapping from source switch to a list of directly connected switches.
        """
        connections = {}
        switch_grouper = SwitchGrouper(self.controlled_switches)
        switch_groups = switch_grouper.get_switch_groups()
        switch_grouper.save_switch_groups(self.switch_grouping_file_path, switch_groups)
        
        # Initialize connections dictionary for all controlled switches
        for switch in self.controlled_switches:
            connections[switch] = {}
            connections[switch]['switch_neighbors'] = switch_groups['switch_neighbors'][switch]
            connections[switch]['switch_neighbors_next'] = switch_groups['switch_neighbors_next'][switch]
        print(f"Switch connections: {connections}")
        return (switch_groups["groups"] , connections)

    def create_host_groups(self, save_to_file=True):
        """
        Creates groups of hosts based on controlled switches.
        Keeps attackers in a separate group.
        Saves the grouping data as JSON in the tmp directory.
        Returns a dictionary of host groups.
        """
        # Initialize host groups
        host_groups = {}
        group_id = 0

        # Debug output to help diagnose the issue
        print(f"DEBUG: Normal hosts: {self.default_normal_hosts}")
        print(f"DEBUG: Attacker hosts: {self.pre_set_attackers}")
        print(f"DEBUG: Controlled switches: {self.controlled_switches}")
        
        # Step 1: Group hosts by their default controlled switch
        hosts_by_switch = {}
        for host in self.default_normal_hosts:
            if host not in self.host_default_switch_relation:
                raise Exception(f"Host {host} not found in host_default_switch_relation. Please check host configuration.")

            default_switch = self.host_default_switch_relation[host]['default_path_switch']
            print(f"DEBUG: Host {host} has default switch {default_switch}")

            # Initialize the lists if this is the first host for this switch
            if default_switch not in hosts_by_switch:
                hosts_by_switch[default_switch] = {'normal': [], 'attackers': []}

            hosts_by_switch[default_switch]['normal'].append(host)

        # Also group attackers by their default switch
        for host in self.pre_set_attackers:
            if host not in self.host_default_switch_relation:
                raise Exception(f"Attacker {host} not found in host_default_switch_relation. Please check host configuration.")

            default_switch = self.host_default_switch_relation[host]['default_path_switch']

            # Initialize the lists if this is the first host for this switch
            if default_switch not in hosts_by_switch:
                hosts_by_switch[default_switch] = {'normal': [], 'attackers': []}

            hosts_by_switch[default_switch]['attackers'].append(host)

        print(f"DEBUG: Hosts by switch: {hosts_by_switch}")

        # Check if any hosts were assigned to switches
        if not hosts_by_switch:
            raise Exception("No hosts could be assigned to switches. Please check switch configuration.")

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

        # Verify that at least one group was created
        if not host_groups:
            raise Exception("No host groups could be created. Please check host and switch configuration.")

        # Create host-to-group mapping for easy reference
        host_to_group_map = {}
        for group_name, group_info in host_groups.items():
            for host in group_info['hosts']:
                host_to_group_map[host] = group_name

        # Print debug information
        print(f"DEBUG: Created {len(host_groups)} host groups")
        print("Host Groups created:")
        for group_name, group_info in host_groups.items():
            print(f"  {group_name}: {group_info['type']} hosts on {group_info['switch']}: {group_info['hosts']}")

        self.host_to_group_map = host_to_group_map
        
        # Save to file if requested
        if save_to_file:
            self._save_host_groups_to_json(host_groups)
            
        return host_groups

    def _save_host_groups_to_json(self, host_groups):
        """
        Saves the host groups to a JSON file in the tmp directory.
        Returns the path to the saved file.
        """
        import json
        import os
        
        # Create tmp directory if it doesn't exist
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        # File path
        json_path = os.path.join(self.tmp_dir, 'host_groups.json')
        
        # Save to file
        with open(json_path, 'w') as f:
            json.dump(host_groups, f, indent=2)
        
        print(f"Host groups saved to {json_path}")
        
        return json_path


    def update_hosts(self):
        self.hosts = []
        for i in range(1, self.nbr_hosts):
            self.hosts.append(f'h{i}')
        self.hosts.append(f'hs')
        print(f"(Reinforcement) ==> environment.hosts = {self.hosts}")

    def update_hosts_ips(self, http_client):
        self.hosts_ips = {}
        self.normal_hosts_ips_array = []
        for host in self.hosts:
            self.hosts_ips[host] = http_client.get_ip_by_host_name(host).text
            if (host not in self.servers) and (host not in self.attacker_hosts):
                self.normal_hosts_ips_array.append(self.hosts_ips[host])
        print(f"(Reinforcement) ==> environment.hosts_ips = {self.hosts_ips}")

    def update_interfaces(self, interfaces):
        self.interfaces = interfaces
        print(f"(Reinforcement) ==> environment.interfaces = {self.interfaces}")

    def transform_state_to_group_based_representation(self, state):
        """
        Transform the host-based state representation to a group-based representation.
        Computes min, max, mean, and standard deviation for each group's metrics.
        Also includes switch utilization metrics.

        Args:
            state: The original state dictionary with per-host metrics

        Returns:
            A numpy array where each row represents a group and columns represent
            statistical metrics (min, max, mean, std) for each original metric plus utilization
        """
        # First, get the host-based state representation
        host_state_array = self.transform_state_to_multi_input_vector_for_hosts(state)

        # Get the number of metrics per host
        metrics_per_host = host_state_array.shape[1]

        # Calculate switch utilization metrics
        grouped_metrics = self.calculate_grouped_metrics(state)
        switch_utilization = grouped_metrics['switch_utilization']

        # Initialize the group-based state array
        # For each group we'll have: (min, max, mean, std) for each metric + utilization
        group_count = len(self.host_groups)

        group_state_array = np.zeros((group_count, metrics_per_host * 4 + 1))  # +1 for utilization

        # For each group, compute statistics
        group_idx = 0
        for group_name, group_info in self.host_groups.items():
            hosts = group_info['hosts']
            controlled_switch = group_info['switch']

            # Collect metrics for all hosts in this group
            host_indices = []
            for host in hosts:
                if host in self.non_server_hosts_ordered:
                    host_indices.append(self.non_server_hosts_ordered.index(host))

            # TODO: is there any way that a group can be empty if conditions are respected
            # if not host_indices:  # Skip if no hosts in this group
            #     # Still include the utilization metric
            #     group_state_array[group_idx, -1] = switch_utilization.get(controlled_switch, 0.0)
            #     group_idx += 1
            #     continue

            # Extract metrics for hosts in this group
            group_metrics = host_state_array[host_indices, :]

            # Compute statistics for each metric
            for metric_idx in range(metrics_per_host):
                metric_values = group_metrics[:, metric_idx]

                # Handle the case of a single host in the group
                if len(metric_values) == 1:
                    min_val = max_val = mean_val = metric_values[0]
                    std_val = 0.0
                else:
                    min_val = np.min(metric_values)
                    max_val = np.max(metric_values)
                    mean_val = np.mean(metric_values)
                    std_val = np.std(metric_values)

                # Store statistics in the group state array
                group_state_array[group_idx, metric_idx * 4] = min_val  # min
                group_state_array[group_idx, metric_idx * 4 + 1] = max_val  # max
                group_state_array[group_idx, metric_idx * 4 + 2] = mean_val  # mean
                group_state_array[group_idx, metric_idx * 4 + 3] = std_val  # std

            # Add utilization metric at the end
            utilization = switch_utilization.get(controlled_switch, 0.0)
            group_state_array[group_idx, -1] = utilization
            group_idx += 1

        print("Group-based state representation:")
        for group_idx, (group_name, group_info) in enumerate(self.host_groups.items()):
            print(f"  Group {group_name} stats:")
            for metric_idx in range(metrics_per_host):
                print(f"    Metric {metric_idx}: min={group_state_array[group_idx, metric_idx * 4]:.4f}, "
                      f"max={group_state_array[group_idx, metric_idx * 4 + 1]:.4f}, "
                      f"mean={group_state_array[group_idx, metric_idx * 4 + 2]:.4f}, "
                      f"std={group_state_array[group_idx, metric_idx * 4 + 3]:.4f}")

        return group_state_array.astype(np.float64)

    def perform_setup(self, http_client, pre_set_attackers):
        self.servers = []
        self.normal_hosts = []
        self.attacker_hosts = []
        self.victim_servers = []

        self.server_election()
        self.attacker_election(pre_set_attackers)

        self.routing_switches = []
        for i in range(1, self.nbr_routing_switches + 1):
            self.routing_switches.append(f's{i}')

        print(f"Identified controlled switches: {self.controlled_switches}")
        print(f"Total controlled switches: {self.nbr_controlled_switches}")

        # First populate non_server_hosts_ordered with normal hosts
        self.non_server_hosts_ordered = self.normal_hosts.copy()

        self.host_groups_json_path = os.path.join(self.tmp_dir, 'host_groups.json')

        # Also set the path in the config object for the network module to use
        if hasattr(self, 'config'):
            self.config.host_groups_json_path = self.host_groups_json_path

        # Now extend non_server_hosts_ordered to include attackers
        self.non_server_hosts_ordered.extend(self.attacker_hosts)

        # Get switch connections from the topology
        self.switch_groups, self.switch_connections = self.get_switch_groups_and_connections()
        self.switch_to_switch_groups_map = {}
        for switch_group in self.switch_groups:
            for switch in switch_group:
                self.switch_to_switch_groups_map[switch] = switch_group

        # Create actions list
        self.ACTIONS = []

        # Add group-based actions
        for group_name, group_info in self.host_groups.items():
            controlled_switch = group_info['switch']

            # Add self redirection in order to "undo" a redirection
            self.ACTIONS.append(Util.group_action(group_name, controlled_switch))
            # Add redirect actions for each group to each controlled switch
            # Only create redirect actions for switches that are connected
            for dst_switch in self.switch_connections[controlled_switch]['switch_neighbors']:
                self.ACTIONS.append(Util.group_action(group_name, dst_switch))

        for src_switch in self.controlled_switches:
            for bw_action in range(self.NBR_POSSIBLE_CONTROLLED_SWITCH_BW_ACTIONS):
                self.ACTIONS.append(Util.bw_action(src_switch, 's0', bw_action))
        for src_switch in self.controlled_switches:
            for dst_switch in self.switch_connections[src_switch]['switch_neighbors_next']:
                for bw_action in range(self.NBR_POSSIBLE_CONTROLLED_SWITCH_BW_ACTIONS):
                    self.ACTIONS.append(Util.bw_action(src_switch, dst_switch, bw_action))

        # Add "do nothing" action
        self.ACTIONS.append(Util.nothing_action())

        # Recalculate output shape based on actual number of actions
        self.OUTPUT_SHAPE = len(self.ACTIONS)

        print("Actions:")
        group_actions = [a for a in self.ACTIONS if a.startswith("group_action")]
        print(f"  Group-based actions ({len(group_actions)}):")
        for action in group_actions:
            print(f"    {action}")
        bandwidth_actions = [a for a in self.ACTIONS if a.startswith("bw")]
        print(f"  Bandwidth actions ({len(bandwidth_actions)}):")
        for action in bandwidth_actions:
            print(f"    {action}")
        print(f"  Do-Nothing action:\n    NOTHING")

        if (not self.OUTPUT_SHAPE == len(self.ACTIONS)):
            raise Exception(f"Output shape is {self.OUTPUT_SHAPE} but possible actions are {len(self.ACTIONS)}")

        print(f'(Reinforcement) ==> environment.ACTIONS = {self.ACTIONS}')

        self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER = 0
        self.last_recorded_delay = 0.0
        self.last_recorded_latency = 0.0
        self.latency_tracker.clear()
        self.last_recorded_jitter = 0.0
        self.jitter_tracker.clear()
        self.before_last_recorded_delay = 0.0
        self.last_recorded_tx = {}
        self.last_recorded_rx = {}
        self.host_last_recorded_interface_data = {}
        self.episode_actions_text_list = []

    def server_election(self):
        server = 'hs'
        self.servers.append(server)
        for host in self.hosts:
            if host not in self.servers:
                self.normal_hosts.append(host)

    def attacker_election(self, pre_set_attackers):
        found_attackers = 0
        # If attacker is set manually
        if len(pre_set_attackers) == self.nbr_of_attackers:
            for attacker in pre_set_attackers:
                if attacker not in self.attacker_hosts:
                    self.attacker_hosts.append(attacker)
                    self.normal_hosts.remove(attacker)
                    found_attackers = found_attackers + 1

                    victim_server_index = random.randint(0, len(self.servers) - 1)
                    victim_server = self.servers[victim_server_index]

                    if victim_server not in self.victim_servers:
                        self.victim_servers.append(victim_server)

                    print(f'(Reinforcement) ==> Setting attacker {attacker}')
        else:
            while found_attackers < self.nbr_of_attackers:

                attacker_index = random.randint(0, len(self.normal_hosts)-1)
                attacker = self.normal_hosts[attacker_index]

                if attacker not in self.attacker_hosts:
                    self.attacker_hosts.append(attacker)
                    self.normal_hosts.remove(attacker)
                    found_attackers = found_attackers + 1

                    victim_server_index = random.randint(0, len(self.servers) - 1)
                    victim_server = self.servers[victim_server_index]

                    if victim_server not in self.victim_servers:
                        self.victim_servers.append(victim_server)

                    print(f'(Reinforcement) ==> electing attacker {attacker}')

    def get_tshark_interfaces_ids(self, cmd):
        tshark_interfaces = cmd.get_tshark_interfaces()
        tshark_interfaces_ids = ''
        for i in range(len(tshark_interfaces)):
            tshark_interface_components = tshark_interfaces[i].split('.')
            if len(tshark_interface_components) == 2:
                for j in range(len(self.interfaces)):
                    if self.interfaces[j] == tshark_interface_components[1].strip():
                        print(
                            f'(Reinforcement) ==> interface {self.interfaces[j]} has id {tshark_interface_components[0]}')
                        tshark_interfaces_ids = f'{tshark_interfaces_ids} -i {tshark_interface_components[0]}'
        return tshark_interfaces_ids

    def read_cic_flow_file(self, config):
        print(f'(Reinforcement) ==> Started reading PCAP file {config.cic_output_file_path}')
        data = []
        with open(config.cic_output_file_path, 'r', newline='') as csvfile:
            csv_reader = csv.DictReader(csvfile, delimiter=',')
            for row in csv_reader:
                data.append(row)
        print(f'(Reinforcement) <== Ended reading PCAP file')
        return data

    def read_network_metrics_file(self, config):
        print(f'(Reinforcement) ==> Started reading Network metrics file {config.net_metrics_result_file_path}')
        data = {}
        with open(config.net_metrics_result_file_path) as json_file:
            data = json.load(json_file)
        print(f'(Reinforcement) <== Ended reading Network metrics file')
        return data

    def print_state_error_message(self, message, curent_attempt, max_attempts, retry_delay):
        if curent_attempt < max_attempts:
            print(f"(Reinforcement) ==> {message}. Will retry to get state in {retry_delay} seconds...")
        else:
            print(f"(Reinforcement) ==> {message}. All attempts failed.")

    def get_state(self, config, cmd, http_client, tshark_interfaces_ids, sender_receiver_relation,
                  attacker_victim_relation, attack_types):
        max_state_attempts = 3
        current_state_attempt = 0
        retry_delay = 2  # seconds
        state_success = False
        while current_state_attempt < max_state_attempts and not state_success:
            current_state_attempt += 1
            if current_state_attempt > 1:
                print(
                    f'(Reinforcement) ==> Attempt {current_state_attempt}/{max_state_attempts} will start after {retry_delay} seconds...')
                time.sleep(retry_delay)  # Wait for the specified delay before retrying
            print(f"(Reinforcement) ==> Starting Attempt {current_state_attempt}/{max_state_attempts}")
            http_client.reset_tcp_receivers()
            time.sleep(2)

            cmd.start_tshark_sniffing(tshark_interfaces_ids)

            # Start hosts sending
            for host in sender_receiver_relation:
                server = sender_receiver_relation[host]
                print(f'(Reinforcement) ==> Host {host} sending to server {server}')
                http_client.start_tcp_flow(host, server, self.transmission_time * 1000)
            time.sleep(1)
            # Start attacks
            for attacker in attacker_victim_relation:
                victim_server = attacker_victim_relation[attacker]
                attack_type = attack_types[attacker]
                print(
                    f'(Reinforcement) ==> attacker {attacker} is attacking victim {victim_server} with {attack_type} attack')
                # http_client.start_ddos_flooding_attack(attacker, victim_server, attack_type) # TODO: Uncomment when using Scapy-Flooding
                if os.getenv("DISABLE_ATTACK") and os.getenv("DISABLE_ATTACK").lower() == "true":
                    print(f'(Reinforcement) ==> WARNING: attack is disabled')
                else:
                    http_client.start_mhddos_attack(attacker, victim_server, attack_type)

            time.sleep(self.attack_duration)

            # End attacks
            for attacker in attacker_victim_relation:
                # http_client.stop_ddos_flooding_attack(attacker, attacker_victim_relation[attacker]) # TODO: Uncomment when using Scapy-Flooding
                if not (os.getenv("DISABLE_ATTACK") and os.getenv("DISABLE_ATTACK").lower() == "true"):
                    http_client.stop_mhddos_attack(attacker, attacker_victim_relation[attacker])

            time.sleep(self.after_attack_duration)

            http_client.stop_all_tcp_flows()

            # End hosts sending

            time.sleep(self.tshark_processing_duration)

            tshark_success = cmd.stop_tshark_sniffing()

            if not tshark_success:
                self.print_state_error_message("Failed to save file of tshark", current_state_attempt,
                                               max_state_attempts, retry_delay)
                continue

            http_client.stop_tcp_receivers()

            # Set the maximum number of retries and the delay between each retry (in seconds)
            max_cic_attempts = 3
            current_cic_attempt = 0  # Initialize the attempt counter

            cic_read_with_success = False
            # Loop to attempt file generation up to the maximum number of retries
            while current_cic_attempt < max_cic_attempts:
                current_cic_attempt += 1  # Increment the attempt counter
                print(
                    f"(Reinforcement) ==> Attempt {current_cic_attempt}/{max_cic_attempts} to generate CSV file by CIC...")

                # Call the function responsible for generating the file
                cmd.run_cic()

                # Check if the file has been successfully generated
                if os.path.exists(config.cic_output_file_path):
                    cic_read_with_success = True
                    break  # Exit the loop if the file exists

                # If the file is not found and attempts remain, wait before retrying
                if current_cic_attempt < max_cic_attempts:
                    print(f"(Reinforcement) ==> File not found. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)  # Wait for the specified delay before retrying
                else:
                    # Log a message if all attempts are exhausted and the file is not generated
                    print(
                        f"(Reinforcement) ==> Failed to generate the file after maximum attempts ({max_cic_attempts} times).")

            if not cic_read_with_success:
                self.print_state_error_message("Failed to generate CIC file", current_state_attempt, max_state_attempts,
                                               retry_delay)
                continue

            metrics_calculater_success = cmd.run_network_metrics_calculator(self.hosts_ips[self.servers[0]], 80,
                                                                            self.normal_hosts_ips_array,
                                                                            self.transmission_time, 512)
            if not metrics_calculater_success:
                self.print_state_error_message("Failed to calculate network metrics", current_state_attempt,
                                               max_state_attempts, retry_delay)
                continue

            cic_data = self.read_cic_flow_file(config)

            network_metrics = self.read_network_metrics_file(config)

            state_success = True

        if not state_success:
            print(f'(Reinforcement) ==> Failed to get state.')
            raise Exception(f"Failed to get state.")

        data_per_host = {}

        for host in self.hosts:  # All hosts (normal hosts, attackers and servers)
            host_data = {'tx_bytes': 0, 'rx_bytes': 0, 'bandwidth': 0,
                         'tx_packets': 0, 'rx_packets': 0, 'tx_packets_len': 0, 'rx_packets_len': 0,
                         'delivered_pkts': 0.0, 'loss_pct': 0.0, 'is_connected': 0,
                         'pkts_s': 0.0, 'bytes_s': 0.0,
                         'non_server_data': {
                             'switches_along_the_path': [],
                             'network_metrics': {}
                         }
                         }
            host_data['is_connected'] = 1 if http_client.get_host_status_connected(host).text == "True" else 0
            switch_interface_statistics = http_client.get_host_interface_statistics(host).text.replace("{", "").replace(
                "}", "").split(",")

            host_data['bandwidth'] = Decimal(http_client.get_host_bw(host).json()['bw'])

            if host not in self.host_last_recorded_interface_data.keys():
                self.host_last_recorded_interface_data[host] = {'tx_bytes': 0, 'rx_bytes': 0}
            for stat in switch_interface_statistics:
                item = stat.strip().split('=')
                key = item[0]
                value = item[1]
                if key == 'rx_bytes':
                    old_tx_bytes = self.host_last_recorded_interface_data[host]['tx_bytes']
                    host_data['tx_bytes'] = int(value) - old_tx_bytes
                    self.host_last_recorded_interface_data[host]['tx_bytes'] = int(value)
                elif key == 'tx_bytes':
                    old_rx_bytes = self.host_last_recorded_interface_data[host]['rx_bytes']
                    host_data['rx_bytes'] = int(value) - old_rx_bytes
                    self.host_last_recorded_interface_data[host]['rx_bytes'] = int(value)
            host_ip = self.hosts_ips[host]
            fwd_host_flow_count = 0  # Counter for flows sent (forwarder) from host/attacker
            for cic_line in cic_data:
                line_pkts_s = float(cic_line['Flow Pkts/s'])
                line_bytes_s = float(cic_line['Flow Byts/s'])
                if (cic_line['Dst Port'] in ['0', '80', '8999']) and line_pkts_s >= 0 and line_bytes_s >= 0 \
                        and (not np.isinf(line_pkts_s)) and (not np.isinf(line_bytes_s)):
                    if cic_line['Src IP'] == host_ip:
                        fwd_host_flow_count = fwd_host_flow_count + 1
                        host_data['tx_packets'] = host_data['tx_packets'] + int(float(cic_line['Tot Fwd Pkts']))
                        host_data['rx_packets'] = host_data['rx_packets'] + int(float(cic_line['Tot Bwd Pkts']))
                        host_data['tx_packets_len'] = host_data['tx_packets_len'] + int(
                            float(cic_line['TotLen Fwd Pkts']))
                        host_data['rx_packets_len'] = host_data['rx_packets_len'] + int(
                            float(cic_line['TotLen Bwd Pkts']))
                        # percentage of transmitted PKTS to total NBR PKTS
                        tx_packets_to_all = float(cic_line['Tot Fwd Pkts']) / (
                                float(cic_line['Tot Fwd Pkts']) + float(cic_line['Tot Bwd Pkts']))
                        host_data['delivered_pkts'] = host_data['delivered_pkts'] + (
                                float(cic_line['ACK Flag Cnt']) * tx_packets_to_all)
                    elif cic_line['Dst IP'] == host_ip:
                        # When the host is the Destination, his fwd packets are flow's bwd packets
                        host_data['tx_packets'] = host_data['tx_packets'] + int(float(cic_line['Tot Bwd Pkts']))
                        host_data['rx_packets'] = host_data['rx_packets'] + int(float(cic_line['Tot Fwd Pkts']))
                        host_data['tx_packets_len'] = host_data['tx_packets_len'] + int(
                            float(cic_line['TotLen Bwd Pkts']))
                        host_data['rx_packets_len'] = host_data['rx_packets_len'] + int(
                            float(cic_line['TotLen Fwd Pkts']))
                        rx_packets_to_all = float(cic_line['Tot Bwd Pkts']) / (
                                float(cic_line['Tot Fwd Pkts']) + float(cic_line['Tot Bwd Pkts']))
                        host_data['delivered_pkts'] = host_data['delivered_pkts'] + (
                                float(cic_line['ACK Flag Cnt']) * rx_packets_to_all)
            if fwd_host_flow_count > 0:
                # Only if the current host is a sender (normal host/attacker)
                dur = self.transmission_time if host in self.normal_hosts else self.attack_duration
                host_data['pkts_s'] = host_data['tx_packets'] / dur
                host_data['bytes_s'] = host_data['tx_bytes'] / dur
                host_data['loss_pct'] = ((host_data['tx_packets'] - host_data['delivered_pkts']) / host_data[
                    'tx_packets']) if host_data['tx_packets'] < 0 else 0
                if host_data['loss_pct'] <= 0:
                    host_data['loss_pct'] = 0.001

            if host not in self.servers:
                switches_along_the_path = http_client.get_host_path(host).json()['current']
                host_data['non_server_data']['switches_along_the_path'] = switches_along_the_path
                if host not in self.attacker_hosts:
                    host_network_metrics = network_metrics[self.hosts_ips[host]]
                    host_data['non_server_data']['network_metrics'] = host_network_metrics
            data_per_host[host] = host_data

        for server in self.servers:
            data_per_host[server]['pkts_s'] = data_per_host[server]['rx_packets'] / (
                    self.attack_duration + self.after_attack_duration)
            data_per_host[server]['bytes_s'] = data_per_host[server]['rx_bytes'] / (
                    self.attack_duration + self.after_attack_duration)
            data_per_host[server]['loss_pct'] = ((data_per_host[server]['rx_packets'] - data_per_host[server][
                'delivered_pkts']) / data_per_host[server]['rx_packets']) if data_per_host[server]['rx_packets'] < 0 else 0
            if data_per_host[server]['loss_pct'] <= 0:
                data_per_host[server]['loss_pct'] = 0.001

        data_per_routing_switch = {}
        for src_switch in self.routing_switches:
            data_per_routing_switch[src_switch] = {}
            dst_switches_connected = http_client.get_switch_status_connected(src_switch).json()
            for dst_switch in dst_switches_connected.keys():
                switch_bw = Decimal(http_client.get_switch_bw(src_switch, dst_switch).json()['bw'])
                data_per_routing_switch[src_switch][dst_switch] = {'bw': switch_bw}

        data_per_controlled_switches = {}
        for src_switch in self.controlled_switches:
            dst_switches = http_client.get_dst_switches(src_switch).json()['dst_switches']
            data_per_controlled_switches[src_switch] = {}
            for dst_switch in dst_switches:
                link_information = http_client.get_link_information(src_switch, dst_switch).json()
                switch_bw = Decimal(link_information['bw'])
                # TODO: Commented after removing link_congestion
                # key = f'{src_switch}_{dst_switch}'
                # last_recorded_tx = 0
                # last_recorded_rx = 0
                # if key in self.last_recorded_tx.keys():
                #     last_recorded_tx = self.last_recorded_tx[key]
                # if key in self.last_recorded_rx.keys():
                #     last_recorded_rx = self.last_recorded_rx[key]

                # current_switch_tx_bytes = link_information['tx_bytes'] - last_recorded_tx
                # current_switch_rx_bytes = link_information['rx_bytes'] - last_recorded_rx
                # self.last_recorded_tx[key] = link_information['tx_bytes']
                # self.last_recorded_rx[key] = link_information['rx_bytes']
                # link_congestion = ((current_switch_tx_bytes+current_switch_rx_bytes ) * 8) / (self.transmission_time * switch_bw * (1000000))
                # data_per_controlled_switches[src_switch][dst_switch] = {'bw': switch_bw, 'link_congestion': link_congestion}
                data_per_controlled_switches[src_switch][dst_switch] = {'bw': float(switch_bw)}

        # Create the state dictionary
        state = {'host': data_per_host,
                 'routing': data_per_routing_switch,
                 'controlled': data_per_controlled_switches}

        return state

    def fixed_normalization(self, features_transposed, current_range, normed_range):
        # Source https://stackoverflow.com/questions/50346017/how-to-normalize-input-data-for-models-in-tensorflow
        current_min, current_max = tf.expand_dims(current_range[:, 0], 1), tf.expand_dims(current_range[:, 1], 1)
        normed_min, normed_max = tf.expand_dims(normed_range[:, 0], 1), tf.expand_dims(normed_range[:, 1], 1)
        x_normed = (features_transposed - current_min) / (current_max - current_min)
        x_normed = x_normed * (normed_max - normed_min) + normed_min
        return x_normed

    def normalize_state_vector_for_single_host(self, host, host_state_vector):

        # Attacker normalization params
        min_duration_s = self.attack_duration
        max_tx_bytes = 400000000.0
        max_rx_bytes = 400000000.0
        max_tx_packets = max_tx_bytes
        max_rx_packets = max_rx_bytes
        max_pkts_s = max(max_tx_packets, max_rx_packets) / min_duration_s
        max_bytes_s = max_pkts_s
        is_attacker = (host in self.attacker_hosts)

        if not is_attacker:
            # Normal host normalization params
            min_duration_s = self.transmission_time
            max_tx_bytes = 25000000
            max_rx_bytes = 25000000
            max_tx_packets = max_tx_bytes / 512  # mean packet size to be 512
            max_rx_packets = max_rx_bytes / 512  # mean packet size to be 512
            max_pkts_s = max(max_tx_packets, max_rx_packets) / min_duration_s
            max_bytes_s = max_pkts_s * 512
        feature_ranges = np.array([[0.0, max_tx_bytes],  # tx_bytes
                                   [0.0, max_rx_bytes],  # rx_bytes
                                   [0.0, max_tx_packets],  # tx_packets
                                   [0.0, max_rx_packets],  # rx_packets
                                   [self.MIN_BW, self.MAX_BW * 6],  # bandwidth
                                   [0.0, max_rx_packets],  # delivered_pkts
                                   [0.0, 1.0],  # loss_pct
                                   [0.0, max_pkts_s],  # pkts_s
                                   [0.0, max_bytes_s],  # bytes_s
                                   [0.0, 30.0],  # latency
                                   [0.0, 30.0],  # avg_packet_transmission_time_s
                                   [0.0, 4000000.0],  # throughput_bps
                                   [0.0, 30.0], # jitter,
                                   [self.MIN_BW, self.MAX_BW * 6],  # Router switch bw,
                                   [0.0, 1.0],  # pass through switch 1
                                   [0.0, 1.0],  # pass through switch 2
                                   [0.0, 1.0],  # pass through switch 3
                                   [0.0, 1.0]  # pass through switch 4
                                   ])
        features = self.fixed_normalization(tf.transpose(host_state_vector), feature_ranges, np.array([[0.0, 1.0]]))
        if np.max(features) > 1:
            print("============> Original state vector")
            print(host_state_vector)
            print("============> Normalized features")
            print(features)
            raise Exception(f"normalization problem in (normalize_state_vector_for_single_host) for host {host}")
        return tf.transpose(features)

    def transform_state_to_multi_input_vector_for_hosts(self, state):
        # Returns array of size nbr_of_non_server_hosts x 18

        # Contains, for each host:
        # - tx_bytes
        # - rx_bytes
        # - tx_packets
        # - rx_packets
        # - bandwidth
        # - delivered_pkts
        # - loss_pct
        # - pkts_s
        # - bytes_s
        # - latency
        # - avg_packet_transmission_time_s
        # - throughput_bps
        # - jitter
        # - Connected router switch BW to direct interfacing controlled switch
        # - [4 columns of size NBR of controlled switches]:
        #   - 1 if the host passes through the controlled switch, 0 if not
        #
        # Considering that controlled switches are 4, size of the resulting vector is: 14 + 4
        hosts_state_array = np.zeros((self.nbr_non_server_hosts, self.nbr_of_host_function_inputs))
        for host in self.non_server_hosts_ordered:
            host_index = self.non_server_hosts_ordered.index(host)
            data_per_host = state['host'][host]
            metric_index = 0
            host_state_vector = np.zeros((1, self.nbr_of_host_function_inputs))
            # ################ Normal host metrics
            host_state_vector[0, 0] = data_per_host['tx_bytes']
            host_state_vector[0, 1] = data_per_host['rx_bytes']
            host_state_vector[0, 2] = data_per_host['tx_packets']
            host_state_vector[0, 3] = data_per_host['rx_packets']
            host_state_vector[0, 4] = data_per_host['bandwidth']
            host_state_vector[0, 5] = data_per_host['delivered_pkts']
            host_state_vector[0, 6] = data_per_host['loss_pct']
            host_state_vector[0, 7] = data_per_host['pkts_s']
            host_state_vector[0, 8] = data_per_host['bytes_s']
            if 'non_server_data' in data_per_host and 'avg_latency_s' in data_per_host['non_server_data']['network_metrics']:
                host_state_vector[0, 9] = data_per_host['non_server_data']['network_metrics']['avg_latency_s']
            if 'non_server_data' in data_per_host and 'avg_packet_transmission_time_s' in data_per_host['non_server_data']['network_metrics']:
                host_state_vector[0, 10] = data_per_host['non_server_data']['network_metrics']['avg_packet_transmission_time_s']
            if 'non_server_data' in data_per_host and 'throughput_bps' in data_per_host['non_server_data']['network_metrics']:
                host_state_vector[0, 11] = data_per_host['non_server_data']['network_metrics']['throughput_bps']
            if 'non_server_data' in data_per_host and 'avg_jitter_s' in data_per_host['non_server_data']['network_metrics']:
                host_state_vector[0, 12] = data_per_host['non_server_data']['network_metrics']['avg_jitter_s']
            # else, the 4 elements would automatically be zeros
            # ################ Router metric
            router = self.host_to_router_relation[host]['router']
            interfacing_controlled_switch = self.router_to_controlled_switch_relation[router]['controlled_switch']
            host_state_vector[0, 13] = state['routing'][router][interfacing_controlled_switch]['bw']
            # ################ Path metric
            starting_metric_index = 14
            connected_controlled_switch = ''
            if 'non_server_data' in data_per_host:
                connected_controlled_switch = data_per_host['non_server_data']['switches_along_the_path'][0]
            host_group_name = self.host_to_group_map[host]
            host_group_default_switch = self.host_groups[host_group_name]['switch']
            controlled_switches = self.switch_to_switch_groups_map[host_group_default_switch]
            for j, other_switch in enumerate(controlled_switches):
                if connected_controlled_switch == other_switch:
                    host_state_vector[0, starting_metric_index + j] = 1
                # else, already zero
            # Normalize
            hosts_state_array[host_index, :] = self.normalize_state_vector_for_single_host(host, host_state_vector)[0, :]
            # Continue to next host...
        return hosts_state_array.astype(np.float64)

    def normalize_state_vector_for_single_switch(self, controlled_switch, switch_state_vector):
        feature_ranges = np.array([[self.MIN_BW, self.MAX_SWITCH_BW],
                                   [self.MIN_BW, self.MAX_SWITCH_BW],
                                   [self.MIN_BW, self.MAX_SWITCH_BW],
                                   [self.MIN_BW, self.MAX_SWITCH_BW],
                                   ])
        features = self.fixed_normalization(tf.transpose(switch_state_vector), feature_ranges, np.array([[0.0, 1.0]]))
        print(np.max(features))
        if np.max(features) > 1:
            print(features)
            raise Exception("normalization problem in (normalize_state_vector_for_single_switch)")
        return tf.transpose(features)

    def transform_state_to_multi_input_vector_for_switches(self, state):
        # Returns array of size n x 4

        # Contains the bandwidth between each controlled switch and S0 (index 0),
        #   and other controlled switches (index 1 to 3)
        # Example of the result:
        #           0               1               2               3
        # 0     s101<->s0       s101<->s102     s101<->s103     s101<->s104
        # 1     s102<->s0       s102<->s101     s102<->s103     s102<->s104
        # 2     s103<->s0       s103<->s101     s103<->s102     s103<->s104
        # 3     s104<->s0       s104<->s101     s104<->s102     s104<->s103
        switches_state_array = np.zeros((self.nbr_controlled_switches, self.nbr_of_controlled_switches_function_inputs))
        for switch_index, controlled_switch in enumerate(self.controlled_switches):
            data_per_switch = state['controlled'][controlled_switch]
            switch_state_vector = np.zeros((1, self.nbr_of_controlled_switches_function_inputs))
            switch_state_vector[0] = data_per_switch['s0']['bw']
            for other_switch_index, dst_switch in enumerate(self.switch_connections[controlled_switch]['switch_neighbors_next']):
                switch_state_vector[0, other_switch_index + 1] = data_per_switch[dst_switch]['bw']
            switches_state_array[switch_index, :] = tf.transpose(self.normalize_state_vector_for_single_switch(controlled_switch, switch_state_vector))[0, :]
        return switches_state_array.astype(np.float64)

    def calculate_grouped_metrics(self, state):
        """
        Computes additional metrics per group, including traffic load utilization
        for each controlled switch.

        Args:
            state: The original state dictionary

        Returns:
            Dictionary with additional metrics per controlled switch
        """
        switch_utilization = {}

        # Calculate traffic load for each controlled switch
        for controlled_switch in self.controlled_switches:
            # Get all host groups connected to this switch
            groups_on_switch = [g for g_name, g in self.host_groups.items()
                                if g['switch'] == controlled_switch]

            total_traffic_bits = 0.0

            # Sum traffic from all hosts in all groups on this switch
            for group in groups_on_switch:
                for host in group['hosts']:
                    if host in state.get('host', {}):
                        # Get bytes_s from host and convert to bits/s (multiply by 8)
                        bytes_s = state['host'][host].get('bytes_s', 0)
                        bits_s = float(bytes_s) * 8
                        total_traffic_bits += bits_s

            # Get maximum bandwidth for the controlled switch (Mbps)
            max_bandwidth_mbps = 0.0

            # Find the connection to s0 (server switch)
            if controlled_switch in state.get('controlled', {}) and 's0' in state['controlled'][controlled_switch]:
                # Get bandwidth in Mbps and convert to bits/s
                max_bandwidth_str = state['controlled'][controlled_switch]['s0']['bw']
                max_bandwidth_mbps = float(max_bandwidth_str)

            # Convert max bandwidth from Mbps to bps
            max_bandwidth_bps = max_bandwidth_mbps * 1_000_000  # 1 Mbps = 1,000,000 bps

            # Calculate utilization (as a value between 0 and 1)
            if max_bandwidth_bps > 0:
                utilization = total_traffic_bits / max_bandwidth_bps
            else:
                utilization = 0.0

            # Cap utilization at 1.0 (100%)
            utilization = min(utilization, 1.0)

            # Store the calculated utilization
            switch_utilization[controlled_switch] = utilization

        print("Switch utilization metrics:")
        for switch, utilization in switch_utilization.items():
            print(f"  {switch}: {utilization:.4f}")

        return {
            'switch_utilization': switch_utilization
        }

    def transform_state_dict_to_normalized_vector(self, state):
        """
        Transforms state dictionary to a normalized vector
        representation suitable for the neural network.

        Now uses group-based representation instead of per-host.
        """
        # Get switch-based metrics directly without computing host metrics
        switch_metrics = self.transform_state_to_multi_input_vector_for_switches(state)

        # Get the new group-based representation for host metrics
        group_metrics = self.transform_state_to_group_based_representation(state)

        # Return the new state as [group_metrics, switch_metrics]
        return [group_metrics, switch_metrics]

    def apply_action_controlled_switches(self, config, cmd, http_client, tshark_interfaces_ids,
                                         sender_receiver_relation,
                                         attacker_victim_relation, attack_types, action, is_predicted):
        """
        Apply the selected action based on group-based approach.

        Args:
            config: Configuration object
            cmd: Command manager object
            http_client: HTTP client object
            tshark_interfaces_ids: TShark interface IDs
            sender_receiver_relation: Dictionary mapping senders to receivers
            attacker_victim_relation: Dictionary mapping attackers to victims
            attack_types: Dictionary mapping attackers to attack types
            action: The action to be applied
            is_predicted: Whether the action was predicted by the model

        Returns:
            Tuple of (new_state, reward, done, avg_PKT_loss_percentage,
                     avg_real_delay, avg_latency, avg_jitter)
        """

        predicted_or_random_label = "predicted" if is_predicted else "random"
        ACTION = self.ACTIONS[action]
        print(f"(Reinforcement) ==> Applying {predicted_or_random_label} action: {action} <==> {ACTION}")
        action_can_be_taken = False
        self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER = 0
        ACTIONS_splitted = ACTION.split(':')
        bw_increase = 0
        path_length_increase = 0

        action_message = "none"

        # Identify if the action is a group action
        if ACTIONS_splitted[0] == "group_action":
            group_name = ACTIONS_splitted[1]
            action_type = ACTIONS_splitted[2]
            target = ACTIONS_splitted[3]

            # Ensure the group exists
            if group_name not in self.host_groups:
                action_message = f"Action {predicted_or_random_label}: {action} cannot be taken - group {group_name} does not exist"
                action_can_be_taken = False
            else:
                group_info = self.host_groups[group_name]
                group_hosts = group_info['hosts']
                group_switch = group_info['switch']

                if action_type == "redirect":
                    # Apply redirect to all hosts in the group
                    action_can_be_taken = True
                    hosts_already_in_path_count = 0
                    for host in group_hosts:
                        host_path_response = http_client.get_host_path(host).json()
                        default_switch = host_path_response['default']
                        current_path = host_path_response['current']

                        path_length_before_redirection = 1 if default_switch in current_path else (
                                1 + len(current_path))

                        if target in current_path:
                            hosts_already_in_path_count += 1
                            print(f"(Reinforcement) ==>   WARNING: host {host} already passes through {current_path}!")
                            continue  # Skip if already on this path
                        else:
                            http_client.redirect_switch_flow(host, target)
                            new_host_path_response = http_client.get_host_path(host).json()
                            new_current_path = new_host_path_response['current']
                            path_length_after_redirection = 1 if default_switch in new_current_path else (
                                    1 + len(new_current_path))
                            path_length_increase += (
                                    path_length_after_redirection - path_length_before_redirection) if path_length_after_redirection > path_length_before_redirection else 0
                    if hosts_already_in_path_count == len(group_hosts):
                        action_can_be_taken = False
                        action_message = f"Action {predicted_or_random_label}: {action} cannot be taken - all hosts in group are already directed through the target switch"
                    else:
                        action_message = f"Applying {predicted_or_random_label} group action: {action} => REDIRECT GROUP: {group_name} ==> {target} ==> Applied"

                elif action_type == "bw_increase" or action_type == "bw_decrease":
                    # Fall back to simple bw action instead of using group-based bandwidth control
                    # This avoids duplication with individual bw actions
                    controlled_switch = group_switch
                    dst_switch = target  # Usually 's0'
                    action_number = 1 if action_type == "bw_increase" else 0  # 1 for increase, 0 for decrease
                    
                    # Use the existing bw action logic
                    bw_action = f"bw:{controlled_switch}:{dst_switch}:{action_number}"
                    
                    # Find this action in the ACTIONS list and use its index
                    if bw_action in self.ACTIONS:
                        action_index = self.ACTIONS.index(bw_action)
                        # Recursively call apply_action_controlled_switches with the simple bw action
                        return self.apply_action_controlled_switches(
                            config, cmd, http_client, tshark_interfaces_ids,
                            sender_receiver_relation, attacker_victim_relation, 
                            attack_types, action_index, is_predicted
                        )
                    else:
                        action_can_be_taken = False
                        action_message = f"Action {predicted_or_random_label}: {action} cannot be taken - bw action not found"

        # Handle original individual host actions for backward compatibility
        elif ACTIONS_splitted[0] == "bw":
            # Original bandwidth control logic
            src_switch = ACTIONS_splitted[1]
            dst_switch = ACTIONS_splitted[2]
            action_number = int(ACTIONS_splitted[3])
            switch_bw = Decimal(http_client.get_switch_bw(src_switch, dst_switch).json()['bw'])
            print(f"(Reinforcement) ==> link {src_switch}<->{dst_switch} has BW={switch_bw}")

            if action_number == self.DECREASE_BW and switch_bw - Decimal(self.DECREASING_FACTOR) >= Decimal(
                    f'{self.MIN_BW}'):
                http_client.decrease_switch_bw(src_switch, dst_switch, self.DECREASING_FACTOR)
                action_can_be_taken = True
                action_message = f"Applying {predicted_or_random_label} action: {action} => DECREASE_BW: {src_switch} ==> {dst_switch} ==> Applied"
                print(f"(Reinforcement) ==> {action_message}")
            elif action_number == self.INCREASE_BW and switch_bw + Decimal(self.INCREASING_FACTOR) <= Decimal(
                    f'{self.MAX_SWITCH_BW}'):
                http_client.increase_switch_bw(src_switch, dst_switch, self.INCREASING_FACTOR)
                action_can_be_taken = True
                bw_increase = self.INCREASING_FACTOR
                action_message = f"Applying {predicted_or_random_label} action: {action} => INCREASE_BW: {src_switch} ==> {dst_switch} ==> Applied"
                print(f"(Reinforcement) ==> {action_message}")
            elif action_number == self.DECREASE_BW or action_number == self.INCREASE_BW:
                action_can_be_taken = False
                action_message = f"Action {predicted_or_random_label}: {action} cannot be taken because link {src_switch}<->{dst_switch} has already BW={switch_bw}"
                print(f"(Reinforcement) ==> {action_message}")
            else:
                raise Exception(f"Unknown action number {action_number}=int({ACTIONS_splitted[3]})!!")

        elif ACTIONS_splitted[0] == "redirect":
            # Original redirect logic
            host_name = ACTIONS_splitted[1]
            dst_switch = ACTIONS_splitted[3]
            host_path_response = http_client.get_host_path(host_name).json()
            default_switch = host_path_response['default']
            current_path = host_path_response['current']
            path_length_before_redirection = 1 if default_switch in current_path else (1 + len(current_path))

            if dst_switch in current_path:
                action_can_be_taken = False
                action_message = f"Action {predicted_or_random_label}: {action} cannot be taken for {host_name} as {dst_switch} is already in the path"
            else:
                action_can_be_taken = True
                http_client.redirect_switch_flow(host_name, dst_switch)
                new_host_path_response = http_client.get_host_path(host_name).json()
                new_current_path = new_host_path_response['current']
                path_length_after_redirection = 1 if default_switch in new_current_path else (1 + len(new_current_path))
                path_length_increase = (
                        path_length_after_redirection - path_length_before_redirection) if path_length_after_redirection > path_length_before_redirection else 0
                action_message = f"Applying {predicted_or_random_label} action: {action} => REDIRECT: {host_name} ==> {dst_switch} ==> Applied"
            print(f"(Reinforcement) ==> {action_message}")

        elif ACTIONS_splitted[0] == Util.nothing_action():
            self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER += 1
            action_message = f"Applying {predicted_or_random_label} action: {action} => DO Nothing"
            print(f"(Reinforcement) ==> {action_message}")
        else:
            action_can_be_taken = False
            raise Exception(f"(Reinforcement) ==> Action {ACTION} was not recognized!")

        new_state = self.get_state(config, cmd, http_client, tshark_interfaces_ids, sender_receiver_relation,
                                   attacker_victim_relation, attack_types)

        reward, done, avg_packet_loss, avg_real_delays, avg_latency, avg_jitter = self.calculate_reward(new_state,
                                                                                                        action_can_be_taken,
                                                                                                        bw_increase,
                                                                                                        path_length_increase)
        self.episode_actions_text_list.append([ACTION, action_message])
        return (new_state, reward, done, avg_packet_loss, avg_real_delays, avg_latency, avg_jitter)
    def calculate_loss(self, state):
        print("(Reinforcement) ==> Calculating loss")
        total_loss_pct = 0
        for host in self.normal_hosts:
            total_loss_pct = total_loss_pct + state['host'][host]['loss_pct']
        avg_PKT_loss_percentage = total_loss_pct / self.nbr_normal_hosts
        print(f'(Reinforcement) ====> Calculated avg_loss = {avg_PKT_loss_percentage} %')
        return avg_PKT_loss_percentage

    def calculate_delay(self, state):
        print("(Reinforcement) ==> Calculating delay")
        sum_real_delay = 0
        transmission_time_ms = (self.transmission_time * 1000)
        for host in self.normal_hosts:
            host_delay = 0
            if state['host'][host]['delivered_pkts'] == 0:
                host_delay = transmission_time_ms
            else:
                host_delay = (transmission_time_ms / state['host'][host]['delivered_pkts'])
            print(f'(Reinforcement) ====> Host {host} has real delay of {host_delay} ms')
            sum_real_delay = sum_real_delay + host_delay

        max_real_delay = self.max_delay_ms  # transmission_time_ms 30000 ms => 600 ms
        avg_real_delay = sum_real_delay / self.nbr_normal_hosts  # ms (for packet)
        print(f'(Reinforcement) ====> Calculated avg_real_delay = {avg_real_delay} ms')

        return avg_real_delay

    def calculate_throughput(self, state):
        print("(Reinforcement) ==> Calculating throughput")
        sum_throughput = 0
        for host in self.normal_hosts:
            host_throughput = state['host'][host]['non_server_data']['network_metrics']['throughput_bps']
            print(f'(Reinforcement) ====> Host {host} has throughput of {host_throughput} bps')
            sum_throughput = sum_throughput + host_throughput
        avg_throughput = sum_throughput / self.nbr_normal_hosts
        print(f'(Reinforcement) ====> Calculated avg_throughput = {avg_throughput} bps')
        return avg_throughput

    def calculate_latency(self, state):
        print("(Reinforcement) ==> Calculating latency")
        sum_latency = 0
        for host in self.normal_hosts:
            host_latency = state['host'][host]['non_server_data']['network_metrics']['avg_latency_s']
            print(f'(Reinforcement) ====> Host {host} has latency of {host_latency} s')
            sum_latency = sum_latency + host_latency
        avg_latency = sum_latency / self.nbr_normal_hosts
        print(f'(Reinforcement) ====> Calculated avg_latency = {avg_latency} s')
        return avg_latency

    def calculate_jitter(self, state):
        print("(Reinforcement) ==> Calculating jitter")
        sum_jitter = 0
        for host in self.normal_hosts:
            host_jitter = state['host'][host]['non_server_data']['network_metrics']['avg_jitter_s']
            print(f'(Reinforcement) ====> Host {host} has jitter of {host_jitter} s')
            sum_jitter = sum_jitter + host_jitter
        avg_jitter = sum_jitter / self.nbr_normal_hosts
        print(f'(Reinforcement) ====> Calculated avg_jitter = {avg_jitter} s')
        return avg_jitter

    def calculate_real_delay_reward(self, action_can_be_taken, avg_real_delay):
        done = False
        if avg_real_delay >= self.max_delay_ms:
            reward = -3  # -2.5 (original value)
            done = True
        elif avg_real_delay <= self.tolerable_delay_ms:
            reward = 3  # +2.5 (original value)
            done = True
        elif self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER > self.MAX_DO_NOTHING_ACTION_BEFORE_PENALTY:
            reward = -0.5  # -0.5 (original value)
            done = False
        elif not action_can_be_taken:
            reward = -2
            done = False
        else:
            if avg_real_delay - 0.2 >= self.last_recorded_delay:
                reward = -1
            elif avg_real_delay + 0.2 <= self.last_recorded_delay:
                reward = 1
            else:
                reward = -0.1
            done = False
        self.last_recorded_delay = avg_real_delay
        return reward, done

    def get_min_change_value(self, old_value, new_value):
        percentage = 0.05
        return percentage * (np.abs(old_value + new_value) / 2.0)

    def calculate_latency_reward(self, action_can_be_taken, avg_latency):
        done = False
        weighted_latency = avg_latency
        if avg_latency >= self.max_latency_s:
            reward = -3  # -2.5 (original value)
            done = True
        elif avg_latency <= self.tolerable_latency_s:
            reward = 3  # +2.5 (original value)
            done = True
        elif self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER > self.MAX_DO_NOTHING_ACTION_BEFORE_PENALTY:
            reward = -0.5  # -0.5 (original value)
            done = False
        elif not action_can_be_taken:
            reward = -1
            done = False
        else:
            # Reward proportional to improvement in latency

            # Deprecated: using values tracker, replaced by weighting
            # change = self.latency_tracker.get_average() - avg_latency

            # New: using weighted latency: latency = (alpha)(previous latency) + (1-alpha)(measured latency)
            weighted_latency = self.alpha_weight * self.last_recorded_latency + (1 - self.alpha_weight) * avg_latency
            change = self.last_recorded_latency - weighted_latency
            reward= np.sign(change) * np.log2(np.abs(change) + 1)
            done = False
        self.last_recorded_latency = weighted_latency
        self.latency_tracker.add_value(weighted_latency)
        print(f"(Reinforcement) =====> Calculated latency reward as {reward} (done=>{done})")
        return reward, done

    def calculate_jitter_reward(self, action_can_be_taken, avg_jitter):
        done = False
        weighted_jitter = avg_jitter
        if avg_jitter >= self.max_jitter_s:
            reward = -3  # -2.5 (original value)
            done = True
        elif avg_jitter <= self.tolerable_jitter_s:
            reward = 3  # +2.5 (original value)
            done = True
        elif self.DO_NOTHING_ACTION_SUCCESSIVE_COUNTER > self.MAX_DO_NOTHING_ACTION_BEFORE_PENALTY:
            reward = -0.5  # -0.5 (original value)
            done = False
        elif not action_can_be_taken:
            reward = -1
            done = False
        else:
            # Reward proportional to improvement in jitter

            # Deprecated: using values tracker, replaced by weighting
            # change = self.jitter_tracker.get_average() - avg_jitter

            # New: using weighted jitter: jitter = (alpha)(previous jitter) + (1-alpha)(measured jitter)
            weighted_jitter = self.alpha_weight * self.last_recorded_jitter + (1 - self.alpha_weight) * avg_jitter
            change = self.last_recorded_jitter - weighted_jitter
            reward = np.sign(change) * np.log2(np.abs(change) + 1)
            done = False
        self.last_recorded_jitter = weighted_jitter
        self.jitter_tracker.add_value(avg_jitter)
        print(f"(Reinforcement) =====> Calculated jitter reward as {reward} (done=>{done})")
        return reward, done



    def calculate_reward(self, state, action_can_be_taken, bw_increase, path_length_increase):
        print("(Reinforcement) ==> Calculating reward")

        avg_PKT_loss_percentage = self.calculate_loss(state)
        avg_real_delay = self.calculate_delay(state)
        avg_throughput = self.calculate_throughput(state)
        avg_latency = self.calculate_latency(state)
        avg_jitter = self.calculate_jitter(state)

        # TODO: clean if delay not needed at all
        # r1, d1 = self.calculate_real_delay_reward(action_can_be_taken, avg_real_delay)
        r1 = 0
        d1 = False
        r2, d2 = self.calculate_latency_reward(action_can_be_taken, avg_latency)
        r3, d3 = self.calculate_jitter_reward(action_can_be_taken, avg_jitter)

        reward = r1 + r2 + r3
        # TODO: Set to False in order to calibrate the system
        # Apply penalty only if the action used resources but was ineffective

        # done = False
        done = d1 or d2 or d3

        if not done:
            #reward -= bw_increase/(self.INCREASING_FACTOR *10)
            #reward -= path_length_increase * 0.1
            reward -= bw_increase
            reward -= path_length_increase * self.INCREASING_FACTOR

        print(f"(Reinforcement) <-----> result after calculating reward = {reward} (done={done})")
        return reward, done, avg_PKT_loss_percentage, avg_real_delay, avg_latency, avg_jitter

    def reset(self):
        print("----> Environment reset")
        #self.currentState = np.zeros(self.INPUT_SHAPE)
        # return self.currentState

class ValuesTracker:
    def __init__(self, max_values=3):
        self.values = deque(maxlen=max_values)

    def add_value(self, value):
        self.values.append(value)

    def get_average(self):
        if len(self.values) == 0:
            return 0.0  # Return 0 if no values are present
        return np.mean(list(self.values))

    def clear(self):
        self.values.clear()