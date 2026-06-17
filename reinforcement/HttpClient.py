import requests

class HttpClient():

    def __init__(self, configuration):
        print("(Reinforcement) HttpClient.__init__()")
        self.api_link = configuration.api_link

    def get_switches_interfaces(self):
        try:
            resp = requests.get(f'{self.api_link}/get-switches-interfaces', timeout=10)
            return resp.json()
        except Exception as e:
            print(f'(HTTP) WARNING: get_switches_interfaces failed: {e}')
            return []

    def start_tcp_flow(self, source_host, destination_host, duration_ms):
        try:
            return requests.get(f'{self.api_link}/start-tcp-flow/{source_host}/{destination_host}/{duration_ms}', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: start_tcp_flow failed: {e}')
            r = requests.models.Response(); r._content = b'{}'; r.status_code = 200; return r

    def stop_all_tcp_flows(self):
        try:
            return requests.get(f'{self.api_link}/stop-all-tcp-flows', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: stop_all_tcp_flows failed: {e}')
            r = requests.models.Response(); r._content = b'{}'; r.status_code = 200; return r

    def start_mhddos_attack(self, attacker_host, victim_host, attack_type):
        return requests.get(f'{self.api_link}/start-mhddos/{attacker_host}/{victim_host}/{attack_type}')

    def stop_mhddos_attack(self, attacker_host, victim_host):
        return requests.get(f'{self.api_link}/stop-mhddos/{attacker_host}/{victim_host}')

    def reset_tcp_receivers(self):
        try:
            return requests.get(f'{self.api_link}/reset-tcp-receivers', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: reset_tcp_receivers failed: {e}')
            r = requests.models.Response(); r._content = b'{}'; r.status_code = 200; return r

    def stop_tcp_receivers(self):
        try:
            return requests.get(f'{self.api_link}/stop-tcp-receivers', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: stop_tcp_receivers failed: {e}')
            r = requests.models.Response(); r._content = b'{}'; r.status_code = 200; return r

    def get_host_interface_statistics(self, host):
        return requests.get(f'{self.api_link}/get-host-interface-statistics/{host}')

    def get_ip_by_host_name(self, host):
        return requests.get(f'{self.api_link}/host-ip/{host}')

    def get_host_status_connected(self, host):
        return requests.get(f'{self.api_link}/host-status-connected/{host}')

    def get_host_bw(self, host):
        try:
            resp = requests.get(f'{self.api_link}/get-host-bw/{host}', timeout=10)
            if resp.status_code != 200 or not resp.content:
                raise ValueError(f'Invalid host_bw response: status={resp.status_code}')
            resp.json()
            return resp
        except Exception as e:
            print(f'(HTTP) WARNING: get_host_bw failed: {e}')
            r = requests.models.Response()
            r._content = b'{"bw": "0"}'
            r.status_code = 200
            return r

    def increase_host_bw(self, host, change):
        return requests.get(f'{self.api_link}/increase-host-bw/{host}/{change}')

    def decrease_host_bw(self, host, change):
        return requests.get(f'{self.api_link}/decrease-host-bw/{host}/{change}')

    def get_switch_status_connected(self, src_switch):
        return requests.get(f'{self.api_link}/get_switch-status-connected/{src_switch}')

    def get_switch_bw(self, src_switch, dst_switch):
        try:
            return requests.get(f'{self.api_link}/get_switch_bw/{src_switch}/{dst_switch}', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: get_switch_bw failed: {e}')
            r = requests.models.Response()
            r._content = b'{"bw": "0.1"}'
            r.status_code = 200
            return r

    def decrease_switch_bw(self, src_switch, dst_switch, change):
        try:
            return requests.get(f'{self.api_link}/decrease-switch-bw/{src_switch}/{dst_switch}/{change}', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: decrease_switch_bw failed: {e}')
            r = requests.models.Response(); r._content = b'{}'; r.status_code = 200; return r

    def increase_switch_bw(self, src_switch, dst_switch, change):
        try:
            return requests.get(f'{self.api_link}/increase-switch-bw/{src_switch}/{dst_switch}/{change}', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: increase_switch_bw failed: {e}')
            r = requests.models.Response(); r._content = b'{}'; r.status_code = 200; return r

    def get_dst_switches(self, src_switch):
        try:
            return requests.get(f'{self.api_link}/get_dst_switches/{src_switch}', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: get_dst_switches failed: {e}')
            r = requests.models.Response()
            r._content = b'{"dst_switches": []}'
            r.status_code = 200
            return r

    def get_link_information(self, src_switch, dst_switch):
        try:
            return requests.get(f'{self.api_link}/get_link_information/{src_switch}/{dst_switch}', timeout=10)
        except requests.exceptions.RequestException as e:
            print(f'(HTTP) WARNING: get_link_information failed: {e}')
            r = requests.models.Response()
            r._content = b'{"tx_bytes": 0, "rx_bytes": 0, "bw": "0.1"}'
            r.status_code = 200
            return r

    def get_host_path(self, host_name):
        return requests.get(f'{self.api_link}/get_host_path/{host_name}')

    def redirect_switch_flow(self, host_name, dst_switch):
        return requests.get(f'{self.api_link}/redirect_switch_flow/{host_name}/{dst_switch}')
