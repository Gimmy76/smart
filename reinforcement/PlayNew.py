#!/usr/bin/env python3

import argparse
import numpy as np
import random
import json
import time
import csv
from datetime import datetime
from Configuration import Configuration
from HttpClient import HttpClient
from CmdManager import CmdManager
from Environment import Environment
from DdqnAgent import DoubleDeepQNetwork
from decimal import Decimal

import os
from tensorflow.keras.models import load_model

def create_console_parser():
    parser = argparse.ArgumentParser(description="Play with trained model",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-a", "--attackers", help="Attacker hosts names. E.g: [h1]", required=False, default="[h5]")
    parser.add_argument("-s", "--steps", help="Number of steps. E.g: 10", required=False, default="10")
    parser.add_argument("-m", "--model-path", help="Path to trained model directory", required=True)
    parser.add_argument("-htf", "--hosts-topo-file", help="Hosts topology file. E.g: hosts-topology-6hosts", 
                        required=False, default="hosts-toplogy-6hosts")
    parser.add_argument("-pat", "--predefined-attack-types",
                        help="When given, only the provided list of attack types would be used. E.g: [ICMP, TCP, UDP, SYN, HTTP, POST, STRESS]",
                        required=False, default="")
    parser.add_argument("-r", "--report", help="Generate detailed report", action="store_true", default=True)
    parser.add_argument("-csv", "--save-csv", help="Save detailed CSV statistics", action="store_true", default=True)
    
    return parser

def get_supported_attack_types():
    return ["ICMP", "TCP", "UDP", "SYN", "HTTP", "POST", "STRESS"]

def get_available_attack_types(config):
    if config.predefined_attack_types is not None:
        return config.predefined_attack_types
    return get_supported_attack_types()

def get_attack_type(config):
    available_attacks = get_available_attack_types(config)
    attack_type_index = random.randint(0, len(available_attacks) - 1)
    return available_attacks[attack_type_index]

def parse_input_arguments(parser_vars):
    print("(Play) ==> Parsing input arguments")
    
    pre_set_attackers = []
    if not (parser_vars['attackers'] is None or parser_vars['attackers'] == '' or parser_vars['attackers'] == '[]'):
        pre_set_attackers = parser_vars['attackers'].lstrip("[").rstrip("]").split(',')
    
    hosts_topo_file_name = 'hosts-toplogy-6hosts.json'
    if not ('hosts_topo_file' not in parser_vars or parser_vars['hosts_topo_file'] is None or parser_vars['hosts_topo_file'] == ''):
        hosts_topo_file_name = parser_vars['hosts_topo_file']
        if not hosts_topo_file_name.lower().endswith(".json"):
            hosts_topo_file_name += ".json"
    
    steps = 10
    if not ('steps' not in parser_vars or parser_vars['steps'] is None or parser_vars['steps'] == ''):
        steps = int(parser_vars['steps'])
    
    model_path = parser_vars['model_path']
    
    # Parse predefined attack types
    predefined_attack_types = None
    if not ('predefined_attack_types' not in parser_vars or parser_vars['predefined_attack_types'] is None or parser_vars['predefined_attack_types'] == ''):
        predefined_attack_types_string = parser_vars['predefined_attack_types']
        predefined_attack_types_list = predefined_attack_types_string.strip('[]').split(', ')
        if len(predefined_attack_types_list) > 0:
            predefined_attack_types = predefined_attack_types_list
    
    print(f'(Play) ==================> Steps: {steps}')
    print(f'(Play) ==================> Model path: {model_path}')
    
    return pre_set_attackers, hosts_topo_file_name, steps, model_path, predefined_attack_types, parser_vars.get('report', True), parser_vars.get('save_csv', True)

def get_basic_metrics_headers():
    headers = ["tx_bytes",
               "rx_bytes",
               "bandwidth",
               "tx_packets",
               "rx_packets",
               "tx_packets_len",
               "rx_packets_len",
               "delivered_pkts",
               "loss_pct",
               "is_connected",
               "pkts_s",
               "bytes_s"]
    return headers

def get_network_metrics_headers():
    headers = ["avg_latency_s",
               "avg_packet_transmission_time_s",
               "throughput_bps",
               "avg_jitter_s"]
    return headers

def save_file_with_headers(filepath, data, headers, fmt='%.18e'):
    with open(filepath, 'w') as result_file:
        wr = csv.writer(result_file)
        wr.writerow(headers)
        np.savetxt(result_file, data, delimiter=',', fmt=fmt)

def generate_test_report(test_config, results, report_path):
    """Generate a comprehensive test report"""
    
    # Calculate summary statistics
    total_steps = len(results)
    avg_reward = np.mean([step['reward'] for step in results])
    avg_packet_loss = np.mean([step['packet_loss'] for step in results])
    avg_latency = np.mean([step['latency'] for step in results])
    avg_jitter = np.mean([step['jitter'] for step in results])
    
    # Count action types
    action_counts = {}
    for step in results:
        action_type = step['action'].split(':')[0]
        action_counts[action_type] = action_counts.get(action_type, 0) + 1
    
    # Generate report
    report = {
        "test_metadata": {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_duration": test_config['end_time'] - test_config['start_time'],
            "model_path": test_config['model_path'],
            "attackers": test_config['attackers'],
            "attack_types": test_config['attack_types'],
            "hosts_topology": test_config['hosts_topology'],
            "total_steps": total_steps
        },
        "network_performance": {
            "average_reward": avg_reward,
            "average_packet_loss": avg_packet_loss,
            "average_latency": avg_latency,
            "average_jitter": avg_jitter,
            "latency_range": [min([s['latency'] for s in results]), max([s['latency'] for s in results])],
            "jitter_range": [min([s['jitter'] for s in results]), max([s['jitter'] for s in results])]
        },
        "model_decisions": {
            "action_distribution": action_counts,
            "total_actions": sum(action_counts.values()),
            "predicted_actions": sum([1 for s in results if s['is_predicted']])
        },
        "step_by_step_results": results
    }
    
    # Save JSON report
    with open(f"{report_path}.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate text summary
    with open(f"{report_path}.txt", 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("TEST EXECUTION REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Test Timestamp: {report['test_metadata']['timestamp']}\n")
        f.write(f"Test Duration: {report['test_metadata']['test_duration']:.2f} seconds\n")
        f.write(f"Model Path: {report['test_metadata']['model_path']}\n")
        f.write(f"Attackers: {', '.join(report['test_metadata']['attackers'])}\n")
        f.write(f"Attack Types: {', '.join(report['test_metadata']['attack_types']) if report['test_metadata']['attack_types'] else 'Random'}\n")
        f.write(f"Hosts Topology: {report['test_metadata']['hosts_topology']}\n")
        f.write(f"Total Steps: {report['test_metadata']['total_steps']}\n\n")
        
        f.write("NETWORK PERFORMANCE SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Average Reward: {report['network_performance']['average_reward']:.4f}\n")
        f.write(f"Average Packet Loss: {report['network_performance']['average_packet_loss']:.4f}\n")
        f.write(f"Average Latency: {report['network_performance']['average_latency']:.4f}s\n")
        f.write(f"Average Jitter: {report['network_performance']['average_jitter']:.4f}s\n")
        f.write(f"Latency Range: {report['network_performance']['latency_range'][0]:.4f}s - {report['network_performance']['latency_range'][1]:.4f}s\n")
        f.write(f"Jitter Range: {report['network_performance']['jitter_range'][0]:.4f}s - {report['network_performance']['jitter_range'][1]:.4f}s\n\n")
        
        f.write("MODEL DECISION ANALYSIS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Actions Taken: {report['model_decisions']['total_actions']}\n")
        f.write(f"Predicted Actions: {report['model_decisions']['predicted_actions']}\n")
        f.write("Action Distribution:\n")
        for action_type, count in report['model_decisions']['action_distribution'].items():
            percentage = (count / report['model_decisions']['total_actions']) * 100
            f.write(f"  - {action_type}: {count} ({percentage:.1f}%)\n")
        
        f.write("\nSTEP-BY-STEP RESULTS\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Step':<6} {'Action':<20} {'Reward':<10} {'Latency':<10} {'Jitter':<10} {'Loss':<10}\n")
        f.write("-" * 80 + "\n")
        for step in results:
            f.write(f"{step['step']:<6} {step['action']:<20} {step['reward']:<10.4f} {step['latency']:<10.4f} {step['jitter']:<10.4f} {step['packet_loss']:<10.4f}\n")
    
    print(f"\n(Play) ==> Report generated:")
    print(f"  - JSON: {report_path}.json")
    print(f"  - Text: {report_path}.txt")
    
    return report

def save_csv_statistics(config, env, steps, results_folder, attacker_state_variables, server_state_variables, 
                       normal_host_state_variables, switches_bw_variables, episode_actions_text_list, 
                       attack_types, SWITCHES_BW_HEADERS):
    """Save detailed CSV statistics similar to training"""
    
    print(f"(Play) ==> Saving CSV statistics to {results_folder}")
    
    # Save normal host CSV files
    for normal_host in env.normal_hosts:
        headers = get_basic_metrics_headers() + get_network_metrics_headers() + ["current_path"]
        save_file_with_headers(
            f"{results_folder}/{normal_host_state_variables[normal_host]['filename']}", 
            normal_host_state_variables[normal_host]['data'], 
            headers, 
            fmt='%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%s'
        )
    
    # Save server CSV files
    for server in env.servers:
        save_file_with_headers(
            f"{results_folder}/{server_state_variables[server]['filename']}", 
            server_state_variables[server]['data'], 
            get_basic_metrics_headers()
        )
    
    # Save attacker CSV files
    for attacker in env.attacker_hosts:
        headers = get_basic_metrics_headers() + ["current_path"]
        save_file_with_headers(
            f"{results_folder}/{attacker_state_variables[attacker]['filename']}", 
            attacker_state_variables[attacker]['data'], 
            headers, 
            fmt='%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%s'
        )
    
    # Save switches bandwidth CSV
    save_file_with_headers(
        f"{results_folder}/{switches_bw_variables['filename']}", 
        switches_bw_variables['data'], 
        SWITCHES_BW_HEADERS
    )
    
    # Save actions CSV
    save_file_with_headers(
        f"{results_folder}/Actions.csv", 
        episode_actions_text_list, 
        ["Action", "Message"], 
        fmt='%s'
    )
    
    print(f"(Play) ==> CSV statistics saved successfully")

def play_with_trained_model(config, model_path, steps, pre_set_attackers, generate_report=True, save_csv=True):
    print("--> Started playing function")
    
    # Create results folder if saving CSV
    results_folder = None
    if save_csv:
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        results_folder = f"results/play_{timestamp}"
        os.makedirs(results_folder, exist_ok=True)
        print(f"(Play) ==> CSV results will be saved to: {results_folder}")
    
    # Test configuration for report
    test_config = {
        'start_time': time.time(),
        'model_path': model_path,
        'attackers': pre_set_attackers,
        'attack_types': config.predefined_attack_types,
        'hosts_topology': config.hosts_topo_file_name,
        'steps': steps
    }
    
    # Results storage for report
    step_results = []
    
    # Initialize components following Main.py pattern
    env = Environment(config, pre_set_attackers)
    cmd = CmdManager(config)
    http_client = HttpClient(config)
    
    # Set up the environment
    env.update_hosts()
    env.perform_setup(http_client, pre_set_attackers)
    
    # Load the model directly
    print(f"(Play) ==> Loading model from {model_path}")
    try:
        loaded_model = load_model(model_path)
        print(f"(Play) ==> Model loaded successfully")
        
        # Create a simple agent that uses the loaded model
        agent = DoubleDeepQNetwork(config, env, http_client, False, False)
    except Exception as e:
        print(f"(Play) ==> Error loading model: {str(e)}")
        return
    
    # Start the network
    cmd.start_network_in_background(env.servers, env.attacker_hosts, config.hosts_topo_file_name)
    
    # Get initial network state
    env.update_hosts_ips(http_client)
    env.update_interfaces(http_client.get_switches_interfaces())
    tshark_interfaces_ids = env.get_tshark_interfaces_ids(cmd)
    
    # Set up communication patterns
    sender_receiver_relation = {}
    for host in env.normal_hosts:
        server_index = random.randint(0, len(env.servers) - 1)
        server = env.servers[server_index]
        sender_receiver_relation[host] = server
    
    attacker_victim_relation = {}
    attack_types = {}
    for attacker in env.attacker_hosts:
        victim_server_index = random.randint(0, len(env.victim_servers) - 1)
        victim_server = env.victim_servers[victim_server_index]
        attacker_victim_relation[attacker] = victim_server
        attack_types[attacker] = get_attack_type(config)
    
    # Initialize CSV data collection arrays (similar to Main.py)
    SWITCHES_BW_HEADERS = None
    attacker_state_variables = {}
    server_state_variables = {}
    normal_host_state_variables = {}
    episode_actions_text_list = []
    
    if save_csv:
        # Initialize data collection arrays for CSV saving
        for attacker in env.attacker_hosts:
            cols = env.NBR_HOST_STATE_METRICS + 1
            attacker_state_variables[attacker] = {
                'filename': f'attacker_{attacker}_attackType_{attack_types[attacker]}.csv',
                'data': np.empty((steps, cols), dtype=object)
            }
            attacker_state_variables[attacker]['data'][:, 0:(cols - 1)] = 0.0
            attacker_state_variables[attacker]['data'][:, (cols - 1)] = ""
        
        for server in env.servers:
            attacker_suffix = ""
            for attacker in env.attacker_hosts:
                if attacker_victim_relation[attacker] == server:
                    attacker_suffix = f"{attacker_suffix}_attacker_{attacker}_type_{attack_types[attacker]}"
            server_state_variables[server] = {
                'filename': f'server_{server}{attacker_suffix}.csv',
                'data': np.zeros((steps, env.NBR_HOST_STATE_METRICS))
            }
        
        for host in env.normal_hosts:
            cols = env.NBR_HOST_STATE_METRICS + env.nbr_of_network_metrics + 1
            normal_host_state_variables[host] = {
                'filename': f'host_{host}.csv',
                'data': np.empty((steps, cols), dtype=object)
            }
            normal_host_state_variables[host]['data'][:, 0:(cols - 1)] = 0.0
            normal_host_state_variables[host]['data'][:, (cols - 1)] = ""
        
        switches_bw_variables = {
            'filename': f'switches_bw.csv',
            'data': np.zeros((steps, env.nbr_routing_switches + (env.nbr_controlled_switches * env.nbr_controlled_switches)))
        }
    
    # Get initial state
    print(f'(Play) ====================> Getting initial state')
    current_state = env.get_state(config, cmd, http_client, tshark_interfaces_ids, 
                                  sender_receiver_relation, attacker_victim_relation, attack_types)
    
    # Initialize tracking variables
    env.last_recorded_delay = env.calculate_delay(current_state)
    env.last_recorded_latency = env.calculate_latency(current_state)
    env.latency_tracker.add_value(env.last_recorded_latency)
    env.last_recorded_jitter = env.calculate_jitter(current_state)
    env.jitter_tracker.add_value(env.last_recorded_jitter)
    env.before_last_recorded_delay = env.last_recorded_delay
    
    print(f'(Play) ====================> Starting play loop for {steps} steps')
    
    # Play loop
    for step in range(1, steps + 1):
        print(f'(Play) ====================> Step {step} Started')
        
        # Transform state and select action
        state_vector = env.transform_state_dict_to_normalized_vector(current_state)
        action, is_predicted = agent.action(step, state_vector)
        
        # Check if action is valid
        if action >= len(env.ACTIONS):
            print(f"(Play) ==> WARNING: Action {action} out of range, using NOTHING action")
            action = len(env.ACTIONS) - 1  # Use NOTHING action
        
        print(f'(Play) ====================> Selected action: {env.ACTIONS[action]} (is_predicted: {is_predicted})')
        
        # Apply action and get new state
        new_state, reward, done, avg_packet_loss, avg_real_delays, avg_latency, avg_jitter = env.apply_action_controlled_switches(
            config, cmd, http_client, tshark_interfaces_ids,
            sender_receiver_relation, attacker_victim_relation, attack_types, action, is_predicted)
        
        print(f'(Play) ====================> Reward: {reward}')
        print(f'(Play) ====================> Avg Packet Loss: {avg_packet_loss}')
        print(f'(Play) ====================> Avg Latency: {avg_latency}')
        print(f'(Play) ====================> Avg Jitter: {avg_jitter}')
        
        # Store results for report
        if generate_report:
            step_result = {
                'step': step,
                'action': env.ACTIONS[action],
                'is_predicted': is_predicted,
                'reward': reward,
                'packet_loss': avg_packet_loss,
                'latency': avg_latency,
                'jitter': avg_jitter,
                'delay': avg_real_delays
            }
            step_results.append(step_result)
        
        # Collect CSV data (similar to Main.py)
        if save_csv:
            step_index = step - 1
            
            # Fill attacker state variables
            for attacker in env.attacker_hosts:
                arr = np.zeros(env.NBR_HOST_STATE_METRICS)
                i = 0
                for header in get_basic_metrics_headers():
                    arr[i] = new_state['host'][attacker][header]
                    i = i + 1
                attacker_state_variables[attacker]['data'][step_index, 0:env.NBR_HOST_STATE_METRICS] = arr
                attacker_state_variables[attacker]['data'][step_index, env.NBR_HOST_STATE_METRICS] = str(http_client.get_host_path(attacker).json()['current'])
            
            # Fill server state variables
            for server in env.servers:
                arr = np.zeros(env.NBR_HOST_STATE_METRICS)
                i = 0
                for header in get_basic_metrics_headers():
                    arr[i] = new_state['host'][server][header]
                    i = i + 1
                server_state_variables[server]['data'][step_index, 0:env.NBR_HOST_STATE_METRICS] = arr
            
            # Fill normal host state variables
            for normal_host in env.normal_hosts:
                arr = np.zeros(env.NBR_HOST_STATE_METRICS)
                i = 0
                for header in get_basic_metrics_headers():
                    arr[i] = new_state['host'][normal_host][header]
                    i = i + 1
                normal_host_state_variables[normal_host]['data'][step_index, 0:env.NBR_HOST_STATE_METRICS] = arr
                arr = np.zeros(env.nbr_of_network_metrics)
                i = 0
                for header in get_network_metrics_headers():
                    arr[i] = new_state['host'][normal_host]['non_server_data']['network_metrics'][header]
                    i = i + 1
                normal_host_state_variables[normal_host]['data'][step_index, env.NBR_HOST_STATE_METRICS:(env.NBR_HOST_STATE_METRICS + env.nbr_of_network_metrics)] = arr
                normal_host_state_variables[normal_host]['data'][step_index, env.NBR_HOST_STATE_METRICS + env.nbr_of_network_metrics] = str(http_client.get_host_path(normal_host).json()['current'])
            
            # Fill switches bandwidth variables
            if SWITCHES_BW_HEADERS is None:
                SWITCHES_BW_HEADERS = []
                for src_switch in new_state['routing'].keys():
                    for dst_switch in new_state['routing'][src_switch].keys():
                        SWITCHES_BW_HEADERS.append(f"{src_switch} -> {dst_switch}")
                for src_switch in new_state['controlled'].keys():
                    for dst_switch in new_state['controlled'][src_switch].keys():
                        SWITCHES_BW_HEADERS.append(f"{src_switch} -> {dst_switch}")
            
            arr = np.zeros(env.nbr_routing_switches + (env.nbr_controlled_switches * env.nbr_controlled_switches))
            i = 0
            for src_switch in new_state['routing'].keys():
                for dst_switch in new_state['routing'][src_switch].keys():
                    arr[i] = new_state['routing'][src_switch][dst_switch]['bw']
                    i = i + 1
            for src_switch in new_state['controlled'].keys():
                for dst_switch in new_state['controlled'][src_switch].keys():
                    arr[i] = new_state['controlled'][src_switch][dst_switch]['bw']
                    i = i + 1
            switches_bw_variables['data'][step_index, :] = arr
        
        # Update current state
        current_state = new_state
        
        print(f'(Play) <==================== Step {step} Ended')
        
        if done:
            print(f'(Play) ====================> Episode terminated early due to done flag')
            break
    
    # Clean up
    cmd.stop_network()
    print(f'(Play) <================== Play session completed')
    
    # Save CSV statistics if requested
    if save_csv:
        save_csv_statistics(config, env, steps, results_folder, attacker_state_variables, 
                           server_state_variables, normal_host_state_variables, switches_bw_variables, 
                           env.episode_actions_text_list, attack_types, SWITCHES_BW_HEADERS)
    
    # Generate report if requested
    if generate_report:
        test_config['end_time'] = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"play_test_report_{timestamp}"
        generate_test_report(test_config, step_results, report_path)

def main():
    parser = create_console_parser()
    parser_vars = vars(parser.parse_args())
    
    pre_set_attackers, hosts_topo_file_name, steps, model_path, predefined_attack_types, generate_report, save_csv = parse_input_arguments(parser_vars)
    
    # Create configuration with all required parameters
    config = Configuration(hosts_topo_file_name, episodes=1, steps=steps, epsilon_decay=0.999, predefined_attack_types=predefined_attack_types)
    config.is_play = True
    config.model_full_path = model_path

    # Verify model path exists
    if not os.path.exists(model_path):
        print(f"Error: Model path '{model_path}' does not exist!")
        return
    
    # Run the play session
    play_with_trained_model(config, model_path, steps, pre_set_attackers, generate_report, save_csv)

if __name__ == '__main__':
    print('(Play) ================> Starting Enhanced Play Script with CSV Support')
    main()
    print('(Play) ================> Enhanced Play Script Completed')