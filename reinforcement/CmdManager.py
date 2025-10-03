import time
import os
import signal
import subprocess

class CmdManager:
    def __init__(self, config):
        print("(Reinforcement) CmdManager.__init__()")
        self.config = config
        self.network_subprocess = None
        self.tshark_sniffing_subprocess = None

    def start_network_in_background(self, servers, attackers, hosts_topo_file_name):
        import os
        
        cmd = self.config.network_command
        cmd = cmd.replace('[SERVERS]', f'{servers}')\
            .replace('[ATTACKERS]', f'{attackers}')\
            .replace('[HOST_BW]', '3.1')\
            .replace('[HOSTS_FILE]', hosts_topo_file_name)
        
        # Add number of controlled switches parameter
        if hasattr(self.config, 'num_controlled_switches'):
            cmd += f' --num-controlled-switches {self.config.num_controlled_switches}'
        
        # Add host groups JSON path if available
        if hasattr(self.config, 'switch_grouping_file_path') and self.config.switch_grouping_file_path:
            cmd += f' --switch-groups-json {self.config.switch_grouping_file_path}'
        
        print(f"(Reinforcement) ----> Executing {cmd}")
        
        # Start subprocess with the modified environment
        self.network_subprocess = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
        print("(Reinforcement) --> Waiting for network to start...")
        MN_WAIT_S = os.getenv('MN_WAIT_S')
        if MN_WAIT_S is None:
            time.sleep(15)
        else:
            time.sleep(int(MN_WAIT_S))
        print("(Reinforcement) --> Network started")

    def stop_network(self):
        self.network_subprocess.communicate(input="exit\n".encode('ascii'), timeout=60)
        print(f"(Reinforcement) ----> Executing exit")
        time.sleep(4)
        print("(Reinforcement) <-- Network stopped")

    def get_tshark_interfaces(self):
        print(f"(Reinforcement) ----> Executing {self.config.tshark_interfaces_command}")
        return subprocess.Popen(self.config.tshark_interfaces_command, shell=True, stdout=subprocess.PIPE).stdout.read().decode("ascii").split('\n')

    def start_tshark_sniffing(self, interfaces_ids):
        try:
            os.remove(self.config.tshark_pcap_file_path)
            if self.config.tshark_should_override_pcap_file_path:
                os.remove(self.config.tshark_overriden_pcap_file_path)
        except FileNotFoundError:
            pass
        path = self.config.tshark_pcap_file_path
        if self.config.tshark_should_override_pcap_file_path:
            path = self.config.tshark_overriden_pcap_file_path
        cmd = self.config.tshark_sniffing_command\
            .replace('[INTERFACES]', interfaces_ids).replace('[FILE_PATH]', path)
        print(f"(Reinforcement) ----> Executing {cmd}")
        self.tshark_sniffing_subprocess = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, preexec_fn=os.setsid)
        time.sleep(2)
        print("(Reinforcement) --> TShark sniffing started")

    def file_exists_and_size(self, file_path):
        """Check if a file exists and print its size."""
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"(Reinforcement) --> File '{file_path}' exists. Size: {file_size} bytes")
            return True
        else:
            print(f"(Reinforcement) --> File '{file_path}' does not exist.")
            return False
    def stop_tshark_sniffing(self):
        os.killpg(os.getpgid(self.tshark_sniffing_subprocess.pid), signal.SIGTERM)
        time.sleep(2)
        # Paths
        source_path = self.config.tshark_overriden_pcap_file_path
        destination_path = self.config.tshark_pcap_file_path

        if self.config.tshark_should_override_pcap_file_path and self.file_exists_and_size(source_path):
            print(f"(Reinforcement) --> Copying file {self.config.tshark_overriden_pcap_file_path} ==> {self.config.tshark_pcap_file_path}")
            p = subprocess.Popen(f'cp {self.config.tshark_overriden_pcap_file_path} {self.config.tshark_pcap_file_path}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
            ret = p.wait()
            print(f"(Reinforcement) ----> Out: {out.decode('ascii')}")
            print(f"(Reinforcement) ----> Error: {err.decode('ascii')}")
            print(f"(Reinforcement) ----> Exit code: {ret}")
            # Verify destination file after copy
        if not self.file_exists_and_size(destination_path):
            print(f"Destination File {destination_path} was not found!")
            print(f"(Reinforcement) <-- TShark sniffing stopped with error!")
            return False
        print("(Reinforcement) <-- TShark sniffing stopped")
        return True

    def run_cic(self):
        print('(Reinforcement) --> Running CIC started')
        try:
            os.remove(self.config.cic_output_file_path)
        except FileNotFoundError:
            pass
        print(f"(Reinforcement) ----> Executing {self.config.cic_command}")
        out, err = subprocess.Popen(self.config.cic_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        print(f"(Reinforcement) ----> Out: {out.decode('ascii')}")
        print(f"(Reinforcement) ----> Error: {err.decode('ascii')}")
        print('(Reinforcement) <-- Running CIC finished')

    def read_ditg_logs(self):
        print('(Reinforcement) --> Running DITG ITGDec started')
        print(f"(Reinforcement) ----> Executing {self.config.ditg_logs_command}")
        subprocess.Popen(self.config.ditg_logs_command, shell=True, stdin=subprocess.PIPE).communicate()
        print('(Reinforcement) <-- Running DITG ITGDec ended')

    def run_network_metrics_calculator(self, server_ip, server_port, hosts_ips, duration_s, packet_bytes):
        print('(Reinforcement) --> Running NetMetricsCalculator started')
        try:
            os.remove(self.config.net_metrics_result_file_path)
        except FileNotFoundError:
            pass
        cmd = self.config.net_metrics_command.replace('[SERVER_IP]', server_ip)\
            .replace('[SERVER_PORT]', str(server_port))\
            .replace('[HOSTS_IPS]', str(hosts_ips).replace('\'', '').replace(' ', ''))\
            .replace('[DURATION]', str(duration_s))\
            .replace('[BYTES]', str(packet_bytes))
        print(f"(Reinforcement) ----> Executing {cmd}")
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        ret = p.wait()
        print(f"(Reinforcement) ----> Out: {out.decode('iso-8859-1')}")
        print(f"(Reinforcement) ----> Error: {err.decode('iso-8859-1')}")
        print(f"(Reinforcement) ----> Exit code: {ret}")
        if ret > 0:
            print('(Reinforcement) <-- Running NetMetricsCalculator ended with error')
            return False
        print('(Reinforcement) <-- Running NetMetricsCalculator ended')
        return True
