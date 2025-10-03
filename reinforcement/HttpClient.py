import requests

class HttpClient():

    def __init__(self, configuration):
        print("(Reinforcement) HttpClient.__init__()")
        self.api_link = configuration.api_link

    def get_switches_interfaces(self):
        return requests.get(f'{self.api_link}/get-switches-interfaces').json()

    def start_ditg_flow(self, source_host, destination_host, duration_ms):
        return requests.get(f'{self.api_link}/start-ditg-flow/{source_host}/{destination_host}/{duration_ms}')

    def start_tcp_flow(self, source_host, destination_host, duration_ms):
        return requests.get(f'{self.api_link}/start-tcp-flow/{source_host}/{destination_host}/{duration_ms}')

    def stop_all_ditg_flows(self):
        return requests.get(f'{self.api_link}/stop-all-ditg-flows')

    def stop_all_tcp_flows(self):
        return requests.get(f'{self.api_link}/stop-all-tcp-flows')

    def start_ddos_flooding_attack(self, attacker_host, victim_host, attack_type):
        return requests.get(f'{self.api_link}/start-ddos-flooding/{attacker_host}/{victim_host}/{attack_type}')

    def stop_ddos_flooding_attack(self, attacker_host, victim_host):
        return requests.get(f'{self.api_link}/stop-ddos-flooding/{attacker_host}/{victim_host}')

    def start_mhddos_attack(self, attacker_host, victim_host, attack_type):
        """
        Start an MHDDoS attack from attacker_host to victim_host
        
        Supported attack_type values:
        - TCP: TCP flood attack
        - HTTP: HTTP GET flood attack
        - POST: HTTP POST flood attack 
        - STRESS: TCP connection stress test
        """
        return requests.get(f'{self.api_link}/start-mhddos/{attacker_host}/{victim_host}/{attack_type}')

    def stop_mhddos_attack(self, attacker_host, victim_host):
        return requests.get(f'{self.api_link}/stop-mhddos/{attacker_host}/{victim_host}')

    def reset_ditg_receivers(self):
        return requests.get(f'{self.api_link}/reset-ditg-receivers')

    def reset_tcp_receivers(self):
        return requests.get(f'{self.api_link}/reset-tcp-receivers')

    def stop_tcp_receivers(self):
        return requests.get(f'{self.api_link}/stop-tcp-receivers')

    def get_host_interface_statistics(self, host):
        return requests.get(f'{self.api_link}/get-host-interface-statistics/{host}')

    def get_ip_by_host_name(self, host):
        return requests.get(f'{self.api_link}/host-ip/{host}')

    def get_host_status_connected(self, host):
        return requests.get(f'{self.api_link}/host-status-connected/{host}')

    def get_host_bw(self, host):
        return requests.get(f'{self.api_link}/get-host-bw/{host}')

    def increase_host_bw(self, host, change):
        return requests.get(f'{self.api_link}/increase-host-bw/{host}/{change}')

    def decrease_host_bw(self, host, change):
        return requests.get(f'{self.api_link}/decrease-host-bw/{host}/{change}')

    def get_switch_status_connected(self, src_switch):
        return requests.get(f'{self.api_link}/get_switch-status-connected/{src_switch}')

    def get_switch_bw(self, src_switch, dst_switch):
        return requests.get(f'{self.api_link}/get_switch_bw/{src_switch}/{dst_switch}')
    def decrease_switch_bw(self, src_switch, dst_switch, change):
        return requests.get(f'{self.api_link}/decrease-switch-bw/{src_switch}/{dst_switch}/{change}')
    def increase_switch_bw(self, src_switch, dst_switch, change):
        return requests.get(f'{self.api_link}/increase-switch-bw/{src_switch}/{dst_switch}/{change}')
    def get_dst_switches(self, src_switch):
        return requests.get(f'{self.api_link}/get_dst_switches/{src_switch}')

    def get_link_information(self, src_switch, dst_switch):
        return requests.get(f'{self.api_link}/get_link_information/{src_switch}/{dst_switch}')

    def get_host_path(self, host_name):
        return requests.get(f'{self.api_link}/get_host_path/{host_name}')

    def redirect_switch_flow(self, host_name, dst_switch):
        return requests.get(f'{self.api_link}/redirect_switch_flow/{host_name}/{dst_switch}')