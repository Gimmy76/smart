import random
import numpy as np
from matplotlib.pyplot import cm
import csv
from decimal import Decimal
from Configuration import Configuration
from Environment import Environment
from HttpClient import HttpClient
from CmdManager import CmdManager
from DdqnAgent import DoubleDeepQNetwork
import matplotlib.pyplot as plt
import shutil
import argparse

def copy_cic_step_file(config, new_file_name):
    new_file_full_path = f"{config.cic_folder}/{new_file_name}"
    original_file_full_path = f"{config.cic_output_file_path}"
    shutil.copyfile(original_file_full_path, new_file_full_path)

def get_supported_attack_types():
    # return ["ICMP", "NESTEA", "SYN"] # TODO: Uncomment when using Scapy-Flooding
    # return ["ICMP", "TCP", "UDP", "SYN"] # TDOO: Uncomment if random attack type
    return ["ICMP", "TCP", "UDP", "SYN", "HTTP", "POST", "STRESS"]  # TODO: currently just TCP attacks => DONE

def get_available_attack_types(config):
    if config.predefined_attack_types is not None:
        return config.predefined_attack_types
    return get_supported_attack_types()

def get_attack_type(config):
    available_attacks = get_available_attack_types(config)
    attack_type_index = random.randint(0, len(available_attacks) - 1)
    return available_attacks[attack_type_index]

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

SWITCHES_BW_HEADERS = None

def save_file_with_headers(filepath, data, headers, fmt='%.18e'):
    with open(filepath, 'w') as result_file:
        wr = csv.writer(result_file)
        wr.writerow(headers)
        np.savetxt(result_file, data, delimiter=',', fmt=fmt)

def save_file_as_properties(filename, data):
    with open(filename, 'w') as file:
        file.write(f"[Properties]\n")
        for entry in data:
            label = entry["label"]
            fmt = entry["fmt"]
            value = entry["value"]
            formatted_value = fmt % value
            file.write(f"{label}={formatted_value}\n")

def convert_to_episode_date(size, data_list):
    np_array = np.zeros((size))
    for i in range(len(data_list)):
        np_array[i] = data_list[i]
    return np_array

def global_build_config_file(config: Configuration, env: Environment, ddqn_agent: DoubleDeepQNetwork):
    data_dict = [
        {"label": "episodes", "fmt": "%i", "value": env.episodes},
        {"label": "steps", "fmt": "%i", "value": env.steps},
        {"label": "step_duration", "fmt": "%i", "value": env.step_duration},
        {"label": "transmission_time", "fmt": "%i", "value": env.transmission_time},
        {"label": "attack_types", "fmt": "%s", "value": f"[{','.join(get_available_attack_types(config))}]"},
        {"label": "gamma", "fmt": "%.18e", "value": ddqn_agent.gamma},
        {"label": "epsilon_decay", "fmt": "%.18e", "value": ddqn_agent.epsilon_decay},
        {"label": "learning_rate", "fmt": "%.18e", "value": ddqn_agent.learning_rate},
        {"label": "batch_size", "fmt": "%i", "value": ddqn_agent.batch_size},
        {"label": "experience_replay_size", "fmt": "%i", "value": ddqn_agent.experience_reply_size},
        {"label": "update_target_each", "fmt": "%i", "value": ddqn_agent.update_target_each},
        {"label": "epoch_count", "fmt": "%i", "value": ddqn_agent.epoch_count}
        ]
    save_file_as_properties(f"{config.configs_folder}/Global-Config.properties", data_dict)


def generate_warning_file_if_necessary(config, file_name, new_state):
    headers = get_basic_metrics_headers()
    headers.remove("bandwidth") # Cuz bandwidth is "Dec" type
    warnings = ""
    for host in new_state['host'].keys():
        for header in headers:
            if(np.isnan(new_state['host'][host][header])):
                warnings = warnings + f"\nISNAN: new_state['host'][{host}][{header}]={new_state['host'][host][header]}"
            elif (np.isinf(new_state['host'][host][header])):
                warnings = warnings + f"\nISINF: new_state['host'][{host}][{header}]={new_state['host'][host][header]}"
            elif (new_state['host'][host][header] < 0):
                warnings = warnings + f"\nNEGATIVE: new_state['host'][{host}][{header}]={new_state['host'][host][header]}"
    if len(warnings) > 0:
        warning_file = f"{config.current_train_folder}/{file_name}"
        f = open(warning_file, 'w')
        f.write(warnings)
        f.close()

def save_fig_episode_switches_bw(config, env, episode, switches_bw_variables, SWITCHES_BW_HEADERS):
    fig6 = plt.figure(f"Episode {episode} Switches BW")
    color = iter(cm.rainbow(np.linspace(0, 1, len(SWITCHES_BW_HEADERS))))
    for i in range(len(SWITCHES_BW_HEADERS)):
        switch_label = SWITCHES_BW_HEADERS[i]
        c = next(color)
        plt.plot(range(1, len(switches_bw_variables['data'][:,i]) + 1), switches_bw_variables['data'][:,i],
                 label=switch_label, c=c)
    # plt.legend()
    plt.legend(loc='center left', bbox_to_anchor=(1, 0))
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("BW")
    plt.title(f"Episode {episode} Switches BW")
    # fig6.savefig(f"{config.figures_folder}/Episode {episode} - Switches BW")
    fig6.savefig(f"{config.figures_folder}/Episode {episode} - Switches BW", bbox_inches='tight')

def save_fig_episode_hosts_bw(config, env, episode, episode_hosts_bw, attack_types):
    fig5 = plt.figure(f"Episode {episode} Hosts BW")
    for host in env.hosts:
        host_label = f'{host}'
        if host in env.servers:
            host_label = f'{host_label} (server)'
        elif host in env.attacker_hosts:
            host_label = f'{host_label} (attacker {attack_types[host]})'
        plt.plot(range(1, len(episode_hosts_bw[host]['data']) + 1), episode_hosts_bw[host]['data'], label=host_label)
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("BW")
    plt.title(f"Episode {episode} Hosts BW")
    fig5.savefig(f"{config.figures_folder}/Episode {episode} - Hosts BW")

def save_fig_episode_rewards(config, env, episode, episode_rewards):
    fig1 = plt.figure(f"Episode {episode} Reward")
    plt.plot(range(1, len(episode_rewards) + 1), episode_rewards, color='b', label='rewards')
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("Reward")
    plt.title(f"Episode {episode} Reward")
    fig1.savefig(f"{config.figures_folder}/Episode {episode} - Reward.png")

def save_fig_episode_loss(config, env, episode, ddqn_agent):
    fig1 = plt.figure(f"Episode {episode} Loss Function")
    plt.plot(range(1, len(ddqn_agent.episode_loss) + 1), ddqn_agent.episode_loss, color='r', label='loss function')
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("Loss function")
    plt.title(f"Episode {episode} Loss Function")
    fig1.savefig(f"{config.figures_folder}/Episode {episode} - Loss Function.png")

def save_fig_episode_pkt_loss(config, env, episode, episode_avg_packet_loss):
    fig3_1 = plt.figure(f"Episode {episode} PKT loss")
    plt.plot(range(1, len(episode_avg_packet_loss) + 1), [100 * x for x in episode_avg_packet_loss], color='b',
             label='pkt loss')
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("PKT loss")
    plt.title(f"Episode {episode} PKT loss")
    fig3_1.savefig(f"{config.figures_folder}/Episode {episode} - PKT loss.png")

def save_fig_episode_avg_real_delay(config, env, episode, episode_avg_real_delays):
    fig3_2 = plt.figure(f"Episode {episode} AVG delay")
    plt.plot(range(1, len(episode_avg_real_delays) + 1), episode_avg_real_delays, color='r', label='avg delay')
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("AVG delay")
    plt.title(f"Episode {episode} AVG delay")
    fig3_2.savefig(f"{config.figures_folder}/Episode {episode} - AVG delay.png")

def save_fig_episode_avg_latency(config, env, episode, episode_avg_latencys):
    fig3_3 = plt.figure(f"Episode {episode} AVG latency")
    plt.plot(range(1, len(episode_avg_latencys) + 1), episode_avg_latencys, color='g', label='avg latency')
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("AVG latency")
    plt.title(f"Episode {episode} AVG latency")
    fig3_3.savefig(f"{config.figures_folder}/Episode {episode} - AVG latency.png")

def save_fig_episode_avg_jitter(config, env, episode, episode_avg_jitters):
    fig3_4 = plt.figure(f"Episode {episode} AVG jitter")
    plt.plot(range(1, len(episode_avg_jitters) + 1), episode_avg_jitters, color='m', label='avg jitter')
    plt.legend()
    plt.xlim((1, env.steps))
    plt.xlabel("Steps")
    plt.ylabel("AVG jitter")
    plt.title(f"Episode {episode} AVG jitter")
    fig3_4.savefig(f"{config.figures_folder}/Episode {episode} - AVG jitter.png")

def create_console_parser():
    parser = argparse.ArgumentParser(description="Main",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-a", "--attackers", help="Attacker hosts names. E.g: [h1]", required=False)
    parser.add_argument("-e", "--episodes", help="Number of episodes. E.g: 50", required=False)
    parser.add_argument("-s", "--steps", help="Number of steps. E.g: 100", required=False)
    parser.add_argument("-ed", "--epsilon-decay", help="Epsilon decay. E.g: 0.999", required=False)
    parser.add_argument("-c", "--controlled", action="store_true",
                        help="Whether to control action taking")
    parser.add_argument("-pfa", "--prefilled-actions", action="store_true",
                        help="Whether to use prefilled actions, from file 'prefilled-actions.txt'")
    parser.add_argument("-htf", "--hosts-topo-file",
                        help="When given, the provided JSON file in the 'input-data' folder will be used. E.g: hosts-topology-6hosts",
                        required=False, default="hosts-toplogy-6hosts")
    parser.add_argument("-pat", "--predefined-attack-types",
                        help="When given, only the provided list of attack types would be used. E.g: [ICMP, TCP, UDP, SYN, HTTP, POST, STRESS]",
                        required=False, default="")
    return parser

def parse_vars_from_parser(parser_vars):
    print(f"(Reinforcement) ==> Parsing input arguments")
    is_controlled = parser_vars['controlled']
    is_prefilled_actions = parser_vars['prefilled_actions']
    if is_controlled and is_prefilled_actions:
        raise Exception("Please use either '--controlled' flag or '--prefilled-actions' flag, but not both!")
    pre_set_attackers = []
    if not (parser_vars['attackers'] is None or parser_vars['attackers'] == '' or parser_vars['attackers'] == '[]'):
        pre_set_attackers = parser_vars['attackers'].lstrip("[").rstrip("]").split(',')
    if is_controlled:
        print('(Reinforcement) ================> Main Started with "controlled actions"')
    elif is_prefilled_actions:
        print('(Reinforcement) ================> Main Started with "prefilled actions"')
    else:
        print('(Reinforcement) ================> Main Started')
    hosts_topo_file_name = 'hosts-toplogy-6hosts.json'
    if not ('hosts_topo_file' not in parser_vars or parser_vars['hosts_topo_file'] is None or parser_vars['hosts_topo_file'] == ''):
        hosts_topo_file_name = parser_vars['hosts_topo_file']
        if not hosts_topo_file_name.lower().endswith(".json"):
            hosts_topo_file_name += ".json"
    episodes = 50
    if not ('episodes' not in parser_vars or parser_vars['episodes'] is None or parser_vars['episodes'] == ''):
        episodes = int(parser_vars['episodes'])
        print(f'(Reinforcement) ==================> Episodes: {episodes}')
    steps = 100
    if not ('steps' not in parser_vars or parser_vars['steps'] is None or parser_vars['steps'] == ''):
        steps = int(parser_vars['steps'])
        print(f'(Reinforcement) ==================> Steps: {steps}')
    epsilon_decay = 0.999
    if not ('epsilon_decay' not in parser_vars or parser_vars['epsilon_decay'] is None or parser_vars['epsilon_decay'] == ''):
        epsilon_decay = float(parser_vars['epsilon_decay'])
        if epsilon_decay >= 1 or epsilon_decay <= 0.1:
            raise Exception("Epsilon decay must be in the range ]0.1, 1[!")
        print(f'(Reinforcement) ==================> Epsilon decay: {epsilon_decay}')
    predefined_attack_types = None
    if not ('predefined_attack_types' not in parser_vars or parser_vars['predefined_attack_types'] is None or parser_vars['predefined_attack_types'] == ''):
        predefined_attack_types_string = parser_vars['predefined_attack_types']
        predefined_attack_types_list = predefined_attack_types_string.strip('[]').split(', ')
        if len(predefined_attack_types_list) > 0:
            supported_attack_types = get_supported_attack_types()
            for attack_type in predefined_attack_types_list:
                if attack_type not in supported_attack_types:
                    raise Exception(f"Attack type {attack_type} is not yet supported. Supported attack types are: {supported_attack_types}")
            predefined_attack_types = predefined_attack_types_list
            print(f'(Reinforcement) ==================> Attack types used: {predefined_attack_types_list}')
    return is_controlled, is_prefilled_actions, pre_set_attackers, hosts_topo_file_name, episodes, steps, epsilon_decay, predefined_attack_types

if __name__ == '__main__':

    ############################################# Start INPUT

    parser = create_console_parser()

    parser_vars = vars(parser.parse_args())

    is_controlled, is_prefilled_actions, pre_set_attackers, hosts_topo_file_name, episodes, steps, epsilon_decay, predefined_attack_types = parse_vars_from_parser(parser_vars)

    ############################################# End INPUT

    config = Configuration(hosts_topo_file_name, episodes, steps, epsilon_decay, predefined_attack_types)
    env = Environment(config, pre_set_attackers)
    cmd = CmdManager(config)
    http_client = HttpClient(config)
    tot_rewards = 0
    total_rewards_per_episode = []
    epsilons = []
    ddqn_agent = DoubleDeepQNetwork(config, env, http_client, is_controlled, is_prefilled_actions)

    global_vars_to_print = {
        "max_attacker": {},
        "max_host": {},
        "max_server": {},
    }
    for header in get_basic_metrics_headers():
        global_vars_to_print["max_attacker"][header] = 0
        global_vars_to_print["max_host"][header] = 0
        global_vars_to_print["max_server"][header] = 0

    for header in get_network_metrics_headers():
        global_vars_to_print["max_host"][header] = 0

    global_build_config_file(config, env, ddqn_agent)

    for episode in range(1, env.episodes + 1):
        # Start episodes >>>>>>>>>>>>>>>>>>>
        # Init episode
        tot_rewards = 0
        episode_index = episode - 1
        current_state = env.reset()

        episode_rewards = []
        ddqn_agent.episode_loss = []
        ddqn_agent.episode_loss = []
        episode_avg_packet_loss = []
        episode_avg_real_delays = []
        episode_avg_latencys = []
        episode_avg_jitters = []

        print(f'(Reinforcement) ==================> Episode {episode} Started')
        env.update_hosts()

        env.perform_setup(http_client, pre_set_attackers)

        ddqn_agent.set_actions(env.ACTIONS)

        cmd.start_network_in_background(env.servers, env.attacker_hosts, config.hosts_topo_file_name)

        env.update_hosts_ips(http_client)

        env.update_interfaces(http_client.get_switches_interfaces())

        tshark_interfaces_ids = env.get_tshark_interfaces_ids(cmd)

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

        # variables for each host

        attacker_state_variables = {}
        for attacker in env.attacker_hosts:
            cols = env.NBR_HOST_STATE_METRICS + 1
            attacker_state_variables[attacker] = {
                'filename': f'attacker_{attacker}_attackType_{attack_types[attacker]}.csv',
                'data': np.empty((env.steps, cols), dtype=object)
            }
            attacker_state_variables[attacker]['data'][:, 0:(cols - 1)] = 0.0
            attacker_state_variables[attacker]['data'][:, (cols - 1)] = ""
        server_state_variables = {}
        for server in env.servers:
            attacker_suffix = ""
            for attacker in env.attacker_hosts:
                if attacker_victim_relation[attacker] == server:
                    attacker_suffix = f"{attacker_suffix}_attacker_{attacker}_type_{attack_types[attacker]}"
            server_state_variables[server] = {
                'filename': f'server_{server}{attacker_suffix}.csv',
                'data': np.zeros((env.steps, env.NBR_HOST_STATE_METRICS))
            }
        normal_host_state_variables = {}
        for host in env.normal_hosts:
            cols = env.NBR_HOST_STATE_METRICS + env.nbr_of_network_metrics + 1
            normal_host_state_variables[host] = {
                'filename': f'host_{host}.csv',
                'data': np.empty((env.steps, cols), dtype=object)
            }
            normal_host_state_variables[host]['data'][:, 0:(cols - 1)] = 0.0
            normal_host_state_variables[host]['data'][:, (cols - 1)] = ""

        switches_bw_variables = {
            'filename': f'switches_bw.csv',
            'data': np.zeros((env.steps, env.nbr_routing_switches + (env.nbr_controlled_switches * env.nbr_controlled_switches)))
        }

        episode_hosts_bw = {}
        for host in env.hosts:
            episode_hosts_bw[host] = {'data': []}

        print(f'(Reinforcement) ====================> Init Step Started')

        new_state = env.get_state(config, cmd, http_client, tshark_interfaces_ids, sender_receiver_relation,
                                  attacker_victim_relation, attack_types)
        current_state = new_state
        env.last_recorded_delay = env.calculate_delay(current_state)
        env.last_recorded_latency = env.calculate_latency(current_state)
        env.latency_tracker.add_value(env.last_recorded_latency)
        env.last_recorded_jitter = env.calculate_jitter(current_state)
        env.jitter_tracker.add_value(env.last_recorded_jitter)
        env.before_last_recorded_delay = env.last_recorded_delay

        for i in range(1, 1):
            print(f'(Reinforcement) ====================> Init Step Started - Additional {i}')
            new_state = env.get_state(config, cmd, http_client, tshark_interfaces_ids, sender_receiver_relation,
                                      attacker_victim_relation, attack_types)
            current_state = new_state
            print(f'(Reinforcement) <==================== Init Step Ended - Additional {i}')
        print(current_state)

        print(f'(Reinforcement) <==================== Init Step Ended')

        for step in range(1, env.steps + 1):
            # >>>>>>>>>>>> start steps

            print(f'(Reinforcement) ====================> Step {step} (of episode {episode}) Started')

            action, is_predicted = ddqn_agent.action(step, env.transform_state_dict_to_normalized_vector(current_state))

            new_state, reward, done, avg_packet_loss, avg_real_delays, avg_latency, avg_jitter = env.apply_action_controlled_switches(
                config, cmd, http_client, tshark_interfaces_ids, sender_receiver_relation, attacker_victim_relation,
                attack_types, action, is_predicted)

            episode_avg_packet_loss.append(avg_packet_loss)
            episode_avg_real_delays.append(avg_real_delays)
            episode_avg_latencys.append(avg_latency)
            episode_avg_jitters.append(avg_jitter)
            print(new_state)

            generate_warning_file_if_necessary(config, f"Episode {episode} - Step {step} - Warning.txt", new_state)

            tot_rewards += reward
            episode_rewards.append(reward)

            ddqn_agent.store(env.transform_state_dict_to_normalized_vector(current_state), action,
                             reward, env.transform_state_dict_to_normalized_vector(new_state), done)

            current_state = new_state

            # Experience Replay
            if len(ddqn_agent.experience_replay_memory) > ddqn_agent.batch_size:
                ddqn_agent.experience_replay(ddqn_agent.batch_size)
            else:
                ddqn_agent.episode_loss.append(1)

            if done or (step % ddqn_agent.update_target_each == 0):
                ddqn_agent.update_target_from_model()

            do_break = False
            if done or step == env.steps:
                total_rewards_per_episode.append(tot_rewards)
                epsilons.append(ddqn_agent.epsilon)
                do_break = True

            step_index = step - 1
            #############################################################################################################
            # filling state information of each host in each step in order to be saved in a csv file after each episode #
            #############################################################################################################
            for attacker in env.attacker_hosts:
                arr = np.zeros(env.NBR_HOST_STATE_METRICS)
                i = 0
                for header in get_basic_metrics_headers():
                    arr[i] = new_state['host'][attacker][header]
                    i = i + 1
                attacker_state_variables[attacker]['data'][step_index, 0:env.NBR_HOST_STATE_METRICS] = arr
                ####################new_state['host']#####################
                for header in get_basic_metrics_headers():
                    global_vars_to_print['max_attacker'][header] = max(
                        global_vars_to_print['max_attacker'][header], new_state['host'][attacker][header])
                attacker_state_variables[attacker]['data'][step_index, env.NBR_HOST_STATE_METRICS] = str(http_client.get_host_path(attacker).json()['current'])
            for server in env.servers:
                arr = np.zeros(env.NBR_HOST_STATE_METRICS)
                i = 0
                for header in get_basic_metrics_headers():
                    arr[i] = new_state['host'][server][header]
                    i = i + 1
                server_state_variables[server]['data'][step_index, 0:env.NBR_HOST_STATE_METRICS] = arr
                ####################new_state['host']#####################
                for header in get_basic_metrics_headers():
                    global_vars_to_print['max_server'][header] = max(
                        global_vars_to_print['max_server'][header], new_state['host'][server][header])

            ######################################## normal host state variable##############################
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
                ####################new_state['host']#####################
                for header in get_basic_metrics_headers():
                    global_vars_to_print['max_host'][header] = max(
                        global_vars_to_print['max_host'][header], new_state['host'][normal_host][header])
                for header in get_network_metrics_headers():
                    global_vars_to_print['max_host'][header] = max(
                        global_vars_to_print['max_host'][header], new_state['host'][normal_host]['non_server_data']['network_metrics'][header])
            ######################################## Switches BW variables ##############################
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

            for host in env.hosts:
                episode_hosts_bw[host]['data'].append(Decimal(http_client.get_host_bw(host).json()['bw']))

            copy_cic_step_file(config, f"Episode {episode} - Step {step} - CIC results.csv")

            print(f'(Reinforcement) <==================== Step {step} (of episode {episode}) Ended')

            if do_break:
                break

            # end steps <<<<<<<<<<<<<<<<

        for normal_host in env.normal_hosts:
            headers = get_basic_metrics_headers() + get_network_metrics_headers() + ["current_path"]
            save_file_with_headers(f"{config.data_folder}/Episode {episode} - {normal_host_state_variables[normal_host]['filename']}", normal_host_state_variables[normal_host]['data'], headers, fmt='%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%s')
        for server in env.servers:
            save_file_with_headers(f"{config.data_folder}/Episode {episode} - {server_state_variables[server]['filename']}", server_state_variables[server]['data'], get_basic_metrics_headers())
        for attacker in env.attacker_hosts:
            headers = get_basic_metrics_headers() + ["current_path"]
            save_file_with_headers(f"{config.data_folder}/Episode {episode} - {attacker_state_variables[attacker]['filename']}", attacker_state_variables[attacker]['data'], headers, fmt='%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%.18e,%s')
        save_file_with_headers(f"{config.data_folder}/Episode {episode} - {switches_bw_variables['filename']}", switches_bw_variables['data'], SWITCHES_BW_HEADERS)
        save_file_with_headers(f"{config.data_folder}/Episode {episode} - Actions.csv", env.episode_actions_text_list, ["Action", "Message"], fmt='%s')
        save_file_with_headers(f"{config.rl_stats_folder}/Episode {episode} - Rewards.csv", convert_to_episode_date(env.steps, episode_rewards), ["reward"])
        save_file_with_headers(f"{config.rl_stats_folder}/Episode {episode} - Loss Function.csv", convert_to_episode_date(env.steps, ddqn_agent.episode_loss), ["loss fn"])

        save_fig_episode_rewards(config, env, episode, episode_rewards)
        save_fig_episode_loss(config, env, episode, ddqn_agent)
        save_fig_episode_pkt_loss(config, env, episode, episode_avg_packet_loss)
        save_fig_episode_avg_real_delay(config, env, episode, episode_avg_real_delays)
        save_fig_episode_avg_latency(config, env, episode, episode_avg_latencys)
        save_fig_episode_avg_jitter(config, env, episode, episode_avg_jitters)
        save_fig_episode_hosts_bw(config, env, episode, episode_hosts_bw, attack_types)
        save_fig_episode_switches_bw(config, env, episode, switches_bw_variables, SWITCHES_BW_HEADERS)

        print(f'(Reinforcement) <================== Episode {episode} Ended')

        cmd.stop_network()

        # end episodes <<<<<<<<<<<<<<<<

    ddqn_agent.update_target_from_model()

    ddqn_agent.save_model(f"{config.rl_models_folder}/rl_model")

    fig = plt.figure(f"Results per Episode")
    plt.plot(range(1, env.episodes + 1), total_rewards_per_episode, color='blue', label='Total rewards per episode')
    plt.axhline(y=max(total_rewards_per_episode), color='r', linestyle='-', label='Max total reward')
    eps_graph = [max(total_rewards_per_episode) * x for x in epsilons]
    plt.plot(range(1, env.episodes + 1), eps_graph, color='g', linestyle='-', label='Epsilon')
    plt.legend()
    plt.xlabel("Episode")
    plt.xlim((1, env.episodes))
    plt.ylim((min(total_rewards_per_episode), 1.1 * max(total_rewards_per_episode)))
    plt.title(f"Results per Episode")
    fig.savefig(f"{config.figures_folder}/Last - total rewards and epsilon.png")

    print(global_vars_to_print)

    print('(Reinforcement) ================> Main Ended')