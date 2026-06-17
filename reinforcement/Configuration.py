from datetime import datetime
import os
import json
import os

# =========================================================================================
# =============================== Environment Variables ===================================
# =========================================================================================
PYTHON = os.getenv('PYTHON')
if PYTHON is None:
    PYTHON="python3"
print(f"WARNING: using python at {PYTHON}!")

CUSTOM_THSHARK_FILE = os.getenv('CUSTOM_THSHARK_FILE')
if CUSTOM_THSHARK_FILE is not None:
    print(f"WARNING: tshark will save to {CUSTOM_THSHARK_FILE} before transfering the file to project tmp folder!")

CICDIR = os.getenv('CICDIR')
if CICDIR is not None:
    print(f"WARNING: CIC DIR is set to {CICDIR}!")

NETWORKDIR = os.getenv('NETWORKDIR')
if NETWORKDIR is not None:
    print(f"WARNING: NETWORK DIR is set to {NETWORKDIR}!")
# ==========================================================================================

class Configuration():

    def __init__(self, hosts_topo_file_name, episodes, steps, epsilon_decay, predefined_attack_types):
        print("(Reinforcement) Configuration.__init__()")

        self.is_play = False
        self.instance_id = os.getenv('INSTANCE_ID', '0')
        self.model_full_path = ""
        self.predefined_attack_types = predefined_attack_types # If None, would fallback to full supported set

        # API
        trial_num = int(os.getenv('TRIAL_NUM', '0'))
        port = 5000 + trial_num
        self.api_link = f"http://localhost:{port}"
        print(f"(Reinforcement) API link: {self.api_link}")

        # Network
        self.network_dir = os.getcwd() + "/../network" if NETWORKDIR is None else NETWORKDIR
        self.network_entrypoint = f'{self.network_dir}/EntryPoint.py'
        # self.network_command = f'{PYTHON} {self.network_entrypoint} --servers [SERVERS] --attackers [ATTACKERS] --unified-host-bandwidth=[HOST_BW] --hosts-topo-file [HOSTS_FILE] --manuel-receivers'
        self.network_command = f'{PYTHON} {self.network_entrypoint} --servers [SERVERS] --attackers [ATTACKERS] --hosts-topo-file [HOSTS_FILE] --manuel-receivers'

        # Temp directory
        self.tmp_dir = os.path.dirname(os.path.abspath(__file__)) + f"/tmp_{self.instance_id}"

        self.host_groups_json_path = None

        # TShark Config
        self.tshark_interfaces_command = 'tshark -D'
        self.tshark_pcap_file_name = 'tshark_out.pcap'
        self.tshark_pcap_file_path = f'{self.tmp_dir}/{self.tshark_pcap_file_name}'
        self.tshark_sniffing_command = f'tshark -i s0_{self.instance_id}-eth0 -f "tcp port 80 or icmp" -w [FILE_PATH]'  # Single interface, no duplicates
        self.tshark_overriden_pcap_file_path = CUSTOM_THSHARK_FILE
        self.tshark_should_override_pcap_file_path = (CUSTOM_THSHARK_FILE is not None)

        # CIC Flow Meter Configuration
        self.cic_output_dir = f'{self.tmp_dir}/cic_out'
        self.cic_dir = f"{os.getcwd()}/../../CIC/CICFlowMeter" if CICDIR is None else CICDIR
        self.cic_command = f'gradle --settings-file {self.cic_dir}/settings.gradle exeCMD -Psource="{self.tshark_pcap_file_path}" -Pdestination="{self.cic_output_dir}"'
        self.cic_output_file_path = f'{self.cic_output_dir}/{self.tshark_pcap_file_name}_Flow.csv'

        # DITG logs
        self.ditg_directory = f'{os.getcwd()}/../../D-ITG-2.8.1-r1023-src/D-ITG-2.8.1-r1023/bin'
        self.ditg_logs_file_path = f'{self.tmp_dir}/ITGRecv.log'
        self.ditg_logs_command = f'{self.ditg_directory}/ITGDec {self.ditg_logs_file_path}'

        # Network PCAP metrics calculator
        self.net_metrics_calculator_path = f'{os.getcwd()}/NetMetricsCalculator.py'
        self.net_metrics_result_file_path = f'{self.tmp_dir}/metrics.json'
        self.net_metrics_command = f'{PYTHON} {self.net_metrics_calculator_path} -s [SERVER_IP] -p [SERVER_PORT] -hip [HOSTS_IPS] -t [DURATION] -b [BYTES] -o {self.net_metrics_result_file_path} -pcap {self.tshark_pcap_file_path}'

        # Switch Grouping Folder
        self.switch_grouping_directory = self.tmp_dir
        self.switch_grouping_file_path = f'{self.tmp_dir}/switch_grouping_{self.instance_id}.json'

        # Results folder
        self.results_folder = os.getcwd() + "/results"
        if not os.path.exists(self.results_folder):
            os.makedirs(self.results_folder)
        self.running_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        self.current_train_folder = f"{self.results_folder}/train_{self.running_time}"
        if not os.path.exists(self.current_train_folder):
            os.makedirs(self.current_train_folder)
        # Figures
        self.figures_folder = self.current_train_folder + "/figs"
        if not os.path.exists(self.figures_folder):
            os.makedirs(self.figures_folder)
        print(f"(Reinforcement) ==> All figures will be saved in {self.figures_folder}")

        # information about attacker, server, normal hosts
        self.data_folder = self.current_train_folder + "/data"
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        print(f"(Reinforcement) ==> All data will be saved in {self.data_folder}")

        # CIC results
        self.cic_folder = self.current_train_folder + "/cic"
        if not os.path.exists(self.cic_folder):
            os.makedirs(self.cic_folder)
        print(f"(Reinforcement) ==> All CIC results will be saved in {self.cic_folder}")

        # RL Models
        self.rl_models_folder = self.current_train_folder + "/models"
        if not os.path.exists(self.rl_models_folder):
            os.makedirs(self.rl_models_folder)
        print(f"(Reinforcement) ==> All RL Models will be saved in {self.rl_models_folder}")

        # Prefilled actions file
        self.prefilled_actions_file = os.getcwd() + "/prefilled-actions.txt"
        print(f"(Reinforcement) ==> If actions are prefilled, they will be read from {self.prefilled_actions_file}")

        # Rewards
        self.rl_stats_folder = self.current_train_folder + "/rl_stats"
        if not os.path.exists(self.rl_stats_folder):
            os.makedirs(self.rl_stats_folder)
        print(f"(Reinforcement) ==> All RL Stats (rewards, etc...) will be saved in {self.rl_stats_folder}")

        # Configs
        self.configs_folder = self.current_train_folder + "/configs"
        if not os.path.exists(self.configs_folder):
            os.makedirs(self.configs_folder)

        # Timing folder for CSV with step-by-step durations
        self.timing_folder = self.current_train_folder + "/timing"
        if not os.path.exists(self.timing_folder):
            os.makedirs(self.timing_folder)
        self.timing_csv_path = self.timing_folder + "/timing.csv"
        print(f"(Reinforcement) ==> Timing CSV will be saved to {self.timing_csv_path}")
        print(f"(Reinforcement) ==> All Configs will be saved in {self.configs_folder}")

        # Network Hosts
        self.hosts_topo_file_name = hosts_topo_file_name
        self.hosts_topo_file_directory = f'{os.getcwd()}/../input-data'
        self.hosts_topo_file_path = f'{self.hosts_topo_file_directory}/{self.hosts_topo_file_name}'
        self.client_hosts_list = []
        self.host_default_switch_relation = {}
        self.router_to_host_relation = {}
        self.host_to_router_relation = {}
        self.router_switches_list = []
        self.router_to_controlled_switch_relation = {}
        self.controlled_switch_to_router_relation = {}
        self.read_hosts_topology_file()
        self.num_controlled_switches = len(self.controlled_switch_to_router_relation.keys())

        # Inputs configs
        self.episodes = episodes
        self.steps = steps
        self.epsilon_decay = epsilon_decay

    def read_hosts_topology_file(self):
        print(f"(Reinforcement) ==> Reading hosts from {self.hosts_topo_file_path}")
        with open(self.hosts_topo_file_path) as json_file:
            data = json.load(json_file)
            self.hosts_raw_topo = data

        iid = self.instance_id
        for host in self.hosts_raw_topo:
            if not host.startswith("h"):
                raise Exception(f"Host name ({host}) is not valid, accepted format 'h' + (number), example: 'h76'")
            host_s = f"{host}_{iid}"
            default_switch = f"{self.hosts_raw_topo[host]['default_path_switch']}_{iid}"
            router = f"{self.hosts_raw_topo[host]['router_switch']}_{iid}"
            self.client_hosts_list.append(host_s)
            self.host_default_switch_relation[host_s] = {'default_path_switch': default_switch}
            self.router_to_host_relation[router] = {'host': host_s}
            self.host_to_router_relation[host_s] = {'router': router}
            self.router_switches_list.append(router)
            self.router_to_controlled_switch_relation[router] = {'controlled_switch': default_switch}
            if default_switch in self.controlled_switch_to_router_relation:
                self.controlled_switch_to_router_relation[default_switch]['routers'].append(router)
            else:
                self.controlled_switch_to_router_relation[default_switch] = {'routers': [router]}