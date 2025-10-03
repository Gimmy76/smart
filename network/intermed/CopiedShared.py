#  This file should always be an exact copy of Shared.py of network module

import os
from mininet.log import info

# Intermed Imports
from .OvsIntermediateMininet import *
from .OvsIntermediate import *
from . import OvsIntermediateConstants as consts


class GlobalsHolder:
    def __init__(self, config):
        self.net = None
        self.cli = None
        self.max_host_bw = 3.1
        self.max_switch_bw = 9.1
        self.max_server_bw = (self.max_host_bw - 0.1) * 3 + 0.1
        self.network_spec = {}
        self.network_dir = os.path.dirname(os.path.abspath(__file__))

        self.tcp_flows = {}
        self.tcp_flow_directory = f'{self.network_dir}/tcp'
        self.tcp_flow_server_file = f'{self.tcp_flow_directory}/TcpServer.py'
        self.tcp_flow_client_file = f'{self.tcp_flow_directory}/TcpClient.py'
        self.tcp_receivers = []

        self.ddos_flooding_attacks = {}
        self.ditg_flows = {}
        self.ditg_directory = '/home/mininet-user/D-ITG-2.8.1-r1023-src/D-ITG-2.8.1-r1023/bin'
        self.ditg_receivers = []
        self.mhddos_start_path = '/home/mininet-user/MHDDoS/start.py'
        self.tmp_dir = os.path.dirname(os.path.abspath(__file__)) + "/../reinforcement/tmp"
        self.servers = ['hs']
        if not (config['servers'] is None or config['servers'] == '' or config['servers'] == '[]'):
            self.servers = config['servers'].lstrip("[").rstrip("]").split(',')
        self.attackers = []
        if not (config['attackers'] is None or config['attackers'] == '' or config['attackers'] == '[]'):
            self.attackers = config['attackers'].lstrip("[").rstrip("]").split(',')
        self.manual_receivers = config['manuel_receivers']
        self.controlled_switches_list = []
        self.router_switches_list = []
        self.client_hosts_list = []
        self.switch_interface_port_mapping = {}
        self.unified_host_bandwidth = None
        if not (config['unified_host_bandwidth'] is None or config['unified_host_bandwidth'] == ''):
            self.unified_host_bandwidth = float(config['unified_host_bandwidth'])
        self.unified_switch_bandwidth = None
        if not (config['unified_switch_bandwidth'] is None or config['unified_switch_bandwidth'] == ''):
            self.unified_switch_bandwidth = float(config['unified_switch_bandwidth'])

        # Extended OVS
        self.ovs = None
        self.highest_priority = 65535
        self.server_switch_flood_priority = 2
        self.controlled_switch_flood_priority = 0
        self.controlled_switch_arp_priority = 499
        self.non_controlled_switch_arp_priority = 499

        self.s0_switch = "s0"
        self.server_host = self.servers[0]
        self.global_dns = "8.8.8.8"

        self.do_validity_controls()

    def do_validity_controls(self):
        # Server Controls
        if len(self.servers) == 0:
            raise Exception("No server has been set")
        if len(self.servers) > 1:
            raise Exception(
                f"More than one server has been set ({self.servers}), current solution accepts only a single server")
        # Attacker Controls
        if len(self.attackers) == 0:
            raise Exception("No attacker has been set")
        if len(self.attackers) > 1:
            raise Exception(
                f"More than one attacker has been set ({self.attackers}), current solution accepts only a single attacker")

def init(config):
    global GLOBALS
    GLOBALS = GlobalsHolder(config)
    print("--> init called")

def get_host_switch_turn_on_link_command(host_ip, connected_switch, switch_port):
    return f'ovs-ofctl add-flow {connected_switch} ip,priority=2,nw_dst={host_ip},actions=output:{switch_port}'

def get_host_switch_turn_off_link_command(host_ip, connected_switch):
    return f'ovs-ofctl --strict del-flows {connected_switch} ip,priority=2,nw_dst={host_ip}'

def get_current_connected_switch_from_switch_dict(src_switch):
    global GLOBALS
    for dst_switch in GLOBALS.network_spec['switches'][src_switch]['connections'].keys():
        if GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['connected']:
            return dst_switch

def turn_down_link(src_switch, src_int, dst_switch, dst_int):
    info(f"*** Deactivate link {src_switch}({src_int}) --> {dst_switch}({dst_int})  ***\n")
    info(GLOBALS.net[src_switch].cmd(f'ifconfig {src_int} down'))
    info(GLOBALS.net[dst_switch].cmd(f'ifconfig {dst_int} down'))

def turn_up_link(src_switch, src_int, dst_switch, dst_int):
    info(f"*** Activate link {src_switch}({src_int}) --> {dst_switch}({dst_int})  ***\n")
    info(GLOBALS.net[src_switch].cmd(f'ifconfig {src_int} up'))
    info(GLOBALS.net[dst_switch].cmd(f'ifconfig {dst_int} up'))

def get_interface_name(src, dst):
    return f'{src}-eth{dst.lstrip("s")}'

def get_ovs_flow_rule_with_src_ip_and_dst_ip(ip_src, ip_dst, output_port):
    return f'ip,priority=500,nw_src={ip_src},nw_dst={ip_dst},actions=output:{output_port}'

def get_ovs_flow_rule_with_src_mac(mac_src, output_port):
    return f'priority=500,dl_src={mac_src},actions=output:{output_port}'

def get_ovs_flow_rule_with_in_port_and_src_mac(in_port, mac_src, output_port):
    return f'priority=500,in_port={in_port},dl_src={mac_src},actions=output:{output_port}'

def get_ovs_flow_rule_with_src_ip(ip_src, output_port):
    return f'ip,priority=500,nw_src={ip_src},actions=output:{output_port}'

def get_ovs_flow_rule_with_in_port_and_src_ip(in_port,ip_src, output_port):
    return f'ip,in_port={in_port},priority=65535,nw_src={ip_src},actions=output:{output_port}'

def get_ovs_flow_rule_with_in_port_and_dst_ip(in_port, ip_dst, output_port):
    return f'ip,in_port={in_port},priority=65535,nw_dst={ip_dst},actions=output:{output_port}'

def get_ovs_flow_rule_with_in_port_and_dst_mac(in_port, mac_dst, output_port):
    return f'in_port={in_port},priority=65535,dl_dst={mac_dst},actions=output:{output_port}'

def get_ovs_flow_rule_with_in_port(in_port, output_port):
    return f'in_port={in_port},priority=65535,actions=output:{output_port}'

def get_ovs_flow_rule_with_dst_ip(ip_dst, output_port):
    return f'ip,priority=65535,nw_dst={ip_dst},actions=output:{output_port}'
def get_ovs_flow_rule_with_dst_mac(mac_dst, output_port):
    return f'priority=65535,dl_dst={mac_dst},actions=output:{output_port}'
def get_ovs_flow_rule_with_src_mac_and_dst_mac(mac_src, mac_dst, output_port):
    return f'priority=65535,dl_src={mac_src},dl_dst={mac_dst},actions=output:{output_port}'

def get_ovs_del_flow_rule_with_dst_mac(mac_dst):
    return f'dl_dst={mac_dst}'

def get_ovs_del_flow_rule_with_src_mac_and_dst_mac(mac_src, mac_dst):
    return f'dl_src={mac_src},dl_dst={mac_dst}'

def get_ovs_add_flow_cmd(switch, cmd):
    info(f'{switch} ==> ovs-ofctl add-flow {cmd}\n')
    return f'ovs-ofctl add-flow {switch} {cmd}'
def get_ovs_del_flow_cmd(switch, cmd):
    info(f'{switch} ==> ovs-ofctl del-flows {cmd}\n')
    return f'ovs-ofctl del-flows {switch} {cmd}'

def get_host_status(host_name):
    global GLOBALS
    return GLOBALS.network_spec['hosts'][host_name]


def flood_arp_for_icmp_command(target: str, priority: int):
    return OvsOfctlAddFlowCommand(target, OvsOfctlCommandArguments(priority=priority,
                                                              ether_type=consts.OVS_INSTR_ARGS_ETHER_TYPE_VALUES_ARP,
                                                              net_protocol=consts.OVS_INSTR_ARGS_NET_PROTOCOL_VALUES_ICMP,
                                                              actions=[OvsCommandArgumentActionFlood()]))


def output_arp_for_icmp_from_port_to_port(target: str, priority: int, in_port, out_ports: []):
    return OvsOfctlAddFlowCommand(target, OvsOfctlCommandArguments(priority=priority,
                                                              ether_type=consts.OVS_INSTR_ARGS_ETHER_TYPE_VALUES_ARP,
                                                              net_protocol=consts.OVS_INSTR_ARGS_NET_PROTOCOL_VALUES_ICMP,
                                                              in_port=f"{in_port}",
                                                              actions=[OvsCommandArgumentActionOutput(f"{out_port}") for
                                                                       out_port in out_ports]))


def init_arp_for_controlled_switch(target: str, priority: int, flood_priority: int, server_port: int,
                                   controlled_ports: [int], non_controlled_ports: [int]):
    commands = []
    commands.append(output_arp_for_icmp_from_port_to_port(target=target, priority=priority, in_port=server_port,
                                                          out_ports=non_controlled_ports))
    for port in non_controlled_ports:
        commands.append(output_arp_for_icmp_from_port_to_port(target=target, priority=priority, in_port=port,
                                                              out_ports=[server_port]))
    for port in controlled_ports:
        commands.append(output_arp_for_icmp_from_port_to_port(target=target, priority=priority, in_port=port,
                                                              out_ports=[server_port]))
    commands.append(flood_arp_for_icmp_command(target=target, priority=flood_priority))
    return commands


def init_arp_for_cotnrolled_switches(priority: int, flood_priority: int, switches_info: dict):
    commands = []
    for switch in switches_info.keys():
        server_port = switches_info[switch]["server_port"]
        controlled_ports = switches_info[switch]["controlled_ports"]
        non_controlled_ports = switches_info[switch]["non_controlled_ports"]
        commands.extend(init_arp_for_controlled_switch(target=switch, priority=priority,
                                                       flood_priority=flood_priority, server_port=server_port,
                                                       controlled_ports=controlled_ports,
                                                       non_controlled_ports=non_controlled_ports))
    return commands


def init_arp_for_non_controlled_switches(flood_priority, switches_names: [str]):
    commands = []
    for switch in switches_names:
        commands.append(flood_arp_for_icmp_command(target=switch, priority=flood_priority))
    return commands

def init_flow_for_global_dns_from_server_switch(switch, priority: int, ip_dest: str, interface_name):
    return OvsOfctlAddFlowCommand(switch, OvsOfctlCommandArguments(
        protocol=consts.OVS_PROTOCOL_IP,
        priority=priority,
        ip_destination=ip_dest,
        actions=[
            OvsCommandArgumentActionOutput(f"{GLOBALS.switch_interface_port_mapping[switch][interface_name]}")]))

def init_flow_from_switch_to_direct_host_via_mac(switch, priority: int, host: str):
    return OvsOfctlAddFlowCommand(switch, OvsOfctlCommandArguments(
        priority=priority,
        mac_destination= GLOBALS.network_spec['hosts'][host]['mac'],
        actions=[OvsCommandArgumentActionOutput(
            f"{GLOBALS.switch_interface_port_mapping[switch][GLOBALS.network_spec['hosts'][host]['dst_int']]}")]))

def init_flow_from_server_switch_to_controlled_switch_for_hosts(switch, priority: int):
    commands = []
    for host in GLOBALS.client_hosts_list:
        controlled_switch = GLOBALS.network_spec['hosts'][host]['default_path_switch']
        s0_to_controlled_switch_src_interface = get_interface_name(switch, controlled_switch)

        commands.append(OvsOfctlAddFlowCommand(switch, OvsOfctlCommandArguments(
            priority=priority,
            mac_destination=GLOBALS.network_spec['hosts'][host]['mac'],
            actions=[OvsCommandArgumentActionOutput(
                f"{GLOBALS.switch_interface_port_mapping[switch][s0_to_controlled_switch_src_interface]}")])))
    return commands

def build_switch_info_for_arp():
    global GLOBALS
    s0_swtich = "s0"
    switches_info = {}
    for switch in GLOBALS.controlled_switches_list:
        info = {
            "server_port": 0,
            "controlled_ports": [],
            "non_controlled_ports": []
        }
        ports = GLOBALS.network_spec['switches'][switch]["ports"]
        connections = GLOBALS.network_spec['switches'][switch]["connections"]
        for port_interface in ports:
            port = GLOBALS.switch_interface_port_mapping[switch][port_interface]
            if port_interface == connections[s0_swtich]["src_int"]:
                info["server_port"] = port
            elif port_interface in [connections[index]["src_int"] for index in connections]:
                info["controlled_ports"].append(port)
            else:
                info["non_controlled_ports"].append(port)
        switches_info[switch] = info
    return switches_info