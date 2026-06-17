import time
import os
import signal
import subprocess
import requests

class CmdManager:
    def __init__(self, config):
        print("(Reinforcement) CmdManager.__init__()")
        self.config = config
        self.network_subprocess = None
        self.tshark_sniffing_subprocess = None

    def start_network_in_background(self, servers, attackers, hosts_topo_file_name):
        self._pre_cleanup()

        cmd = self.config.network_command
        iid = os.getenv("INSTANCE_ID", "0")
        tnum = os.getenv("TRIAL_NUM", "0")
        path_prefix = f"sudo -E INSTANCE_ID={iid} TRIAL_NUM={tnum} /home/giovanni/run_entrypoint.sh "
        cmd = path_prefix + cmd
        cmd = cmd.replace('[SERVERS]', f'{servers}')\
            .replace('[ATTACKERS]', f'{attackers}')\
            .replace('[HOST_BW]', '3.1')\
            .replace('[HOSTS_FILE]', hosts_topo_file_name)

        if hasattr(self.config, 'num_controlled_switches'):
            cmd += f' --num-controlled-switches {self.config.num_controlled_switches}'
        if hasattr(self.config, 'switch_grouping_file_path') and self.config.switch_grouping_file_path:
            cmd += f' --switch-groups-json {self.config.switch_grouping_file_path}'

        print(f"(Reinforcement) ----> Executing {cmd}")

        iid = os.getenv("INSTANCE_ID", "0")
        _log_dir = os.path.dirname(os.path.abspath(__file__)) + f"/tmp_{iid}"
        os.makedirs(_log_dir, exist_ok=True)
        _stdout_file = open(f"{_log_dir}/network_stdout.log", 'a', encoding='utf-8')
        _stderr_file = open(f"{_log_dir}/network_stderr.log", 'a', encoding='utf-8')

        self.network_subprocess = subprocess.Popen(
            cmd, shell=True, stdin=subprocess.PIPE,
            stdout=_stdout_file, stderr=_stderr_file,
            preexec_fn=os.setsid)

        print("(Reinforcement) --> Waiting for network to start...")
        for retry in range(20):
            if self.network_subprocess.poll() is not None:
                break
            time.sleep(1)
        if self.network_subprocess.poll() is not None:
            print(f"(Reinforcement) ERROR: network process exited with code {self.network_subprocess.poll()}")
            try:
                with open(f"{_log_dir}/network_stderr.log", 'r') as _f:
                    print("".join(_f.readlines()[-30:]))
            except Exception:
                pass
            raise RuntimeError("Network subprocess exited before startup")

        self._wait_for_flask_ready()
        self._wait_for_hosts_ready()
        print("(Reinforcement) --> Network started")

    def _pre_cleanup(self):
        """Cleanup isolato al singolo trial usando INSTANCE_ID e TRIAL_NUM."""
        instance_id = os.getenv('INSTANCE_ID', '0')
        trial_num = int(os.getenv('TRIAL_NUM', '0'))
        suffix = f"_{instance_id}"
        flask_port = 5000 + trial_num

        print(f"(Reinforcement) --> _pre_cleanup instance='{instance_id}' porta={flask_port}")

        # 1. Libera la porta Flask di questo trial specifico
        try:
            subprocess.run(
                f"sudo fuser -k {flask_port}/tcp 2>/dev/null || true",
                shell=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass

        # 2. Aspetta che la porta sia libera
        for _attempt in range(15):
            result = subprocess.run(
                f"sudo fuser {flask_port}/tcp 2>/dev/null",
                shell=True, capture_output=True, text=True)
            if not result.stdout.strip():
                print(f"(Reinforcement) --> Porta {flask_port} libera")
                break
            print(f"(Reinforcement) --> Porta {flask_port} ancora occupata, aspetto...")
            time.sleep(2)

        # 3. Rimuovi SOLO i bridge OVS di questa istanza
        if suffix:
            try:
                subprocess.run(
                    f"for br in $(sudo ovs-vsctl list-br 2>/dev/null | grep -E '{suffix}($|-)'); do "
                    f"sudo ovs-vsctl --if-exists del-br $br 2>/dev/null; done",
                    shell=True, timeout=20)
                print(f"(Reinforcement) --> OVS bridges cleaned for suffix '{suffix}'")
            except subprocess.TimeoutExpired:
                pass

        # 4. Rimuovi interfacce veth orfane di questa istanza
        if suffix:
            try:
                subprocess.run(
                    f"for iface in $(ip -o link show 2>/dev/null "
                    f"| awk -F': ' '{{print $2}}' | cut -d'@' -f1 "
                    f"| grep -E '{suffix}(-eth|$)'); do "
                    f"sudo ip link delete \"$iface\" 2>/dev/null || true; done",
                    shell=True, timeout=20)
                print(f"(Reinforcement) --> veth interfaces cleaned for suffix '{suffix}'")
            except subprocess.TimeoutExpired:
                pass

        time.sleep(2)
        print("(Reinforcement) --> _pre_cleanup done")

    def _wait_for_hosts_ready(self, max_retries=90, retry_interval=2):
        """Aspetta che il primo host abbia un IP valido."""
        import os
        instance_id = os.getenv('INSTANCE_ID', '0')
        first_host = f'h1_{instance_id}'
        url = f"{self.config.api_link}/host-ip/{first_host}"
        print(f"(Reinforcement) --> Waiting for host {first_host} to get IP...")
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(url, timeout=5)
                ip = resp.text.strip()
                if (resp.status_code == 200
                        and ip
                        and ip != 'UNKNOWN'
                        and len(ip) <= 15
                        and all(c.isdigit() or c == '.' for c in ip)):
                    print(f"(Reinforcement) --> Host {first_host} has IP {ip} (attempt {attempt})")
                    time.sleep(3)
                    return
            except Exception as e:
                pass
            if attempt % 10 == 0:
                print(f"(Reinforcement) --> Waiting for host IP... ({attempt}/{max_retries})")
            time.sleep(retry_interval)
        print(f"(Reinforcement) WARNING: hosts not ready after {max_retries * retry_interval}s. Continuing anyway.")

    def _wait_for_flask_ready(self, max_retries=60, retry_interval=3):
        url = f"{self.config.api_link}/"
        for attempt in range(1, max_retries + 1):
            try:
                if requests.get(url, timeout=2).status_code == 200:
                    print(f"(Reinforcement) --> Flask ready (attempt {attempt})")
                    return
            except Exception as e:
                if attempt % 10 == 0:
                    print(f"(Reinforcement) --> Flask not ready: {e} ({attempt}/{max_retries})")
            time.sleep(retry_interval)
        print("(Reinforcement) WARNING: Flask not ready after all retries.")

    def stop_network(self):
        try:
            pgid = os.getpgid(self.network_subprocess.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                self.network_subprocess.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
                self.network_subprocess.wait(timeout=5)
        except Exception as e:
            print(f"(Reinforcement) WARNING: stop_network error: {e}")
        time.sleep(2)
        try:
            self._pre_cleanup()
        except Exception as e:
            print(f"(Reinforcement) WARNING: post-stop cleanup error: {e}")
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
        if os.path.exists(file_path):
            print(f"(Reinforcement) --> File '{file_path}' exists. Size: {os.path.getsize(file_path)} bytes")
            return True
        print(f"(Reinforcement) --> File '{file_path}' does not exist.")
        return False

    def stop_tshark_sniffing(self):
        os.killpg(os.getpgid(self.tshark_sniffing_subprocess.pid), signal.SIGTERM)
        time.sleep(2)
        source_path = self.config.tshark_overriden_pcap_file_path
        destination_path = self.config.tshark_pcap_file_path
        if self.config.tshark_should_override_pcap_file_path and self.file_exists_and_size(source_path):
            print(f"(Reinforcement) --> Copying file {source_path} ==> {destination_path}")
            p = subprocess.Popen(f'cp {source_path} {destination_path}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
            p.wait()
        if not self.file_exists_and_size(destination_path):
            print(f"(Reinforcement) <-- TShark sniffing stopped with error!")
            return False
        print("(Reinforcement) <-- TShark sniffing stopped")
        return True

    def run_network_metrics_calculator(self, server_ip, server_port, hosts_ips, duration_s, packet_bytes, output_file=None):
        print('(Reinforcement) --> Running NetMetricsCalculator started')
        try:
            os.remove(self.config.net_metrics_result_file_path)
        except FileNotFoundError:
            pass
        out_path = output_file if output_file else self.config.net_metrics_result_file_path
        cmd = self.config.net_metrics_command\
            .replace('[SERVER_IP]', server_ip)\
            .replace('[SERVER_PORT]', str(server_port))\
            .replace('[HOSTS_IPS]', str(hosts_ips).replace('\'', '').replace(' ', ''))\
            .replace('[DURATION]', str(duration_s))\
            .replace('[BYTES]', str(packet_bytes))\
            .replace(self.config.net_metrics_result_file_path, out_path)
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
