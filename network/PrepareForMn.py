from decimal import Decimal

import intermed.CopiedShared as shared

# Intermed Imports
from intermed.OvsIntermediateMininet import *
from intermed.OvsIntermediate import *
import intermed.OvsIntermediateConstants as consts

class MyLink(object):

    def __init__(self) -> None:
        super().__init__()


class MyNode(object):

    def __init__(self, name) -> None:
        super().__init__()
        self.name = name

    def cmd(self, cmd_content: str):
        return f"Executed {cmd_content}"


class MyTopo(object):

    def __init__(self) -> None:
        super().__init__()

    def addSwitch(self, name):
        return MyNode(name)

    def addHost(self, name, ip=None, cpu=None, mac=None):
        return MyNode(name)

    def addLink(self, src, dst, intfName1=None, intfName2=None, params2=None, bw=None, max_queue_size=None):
        return MyLink()


class MyMininet(object):

    def __init__(self) -> None:
        super().__init__()

    def __getitem__(self, key):
        return MyNode(key)


class NetworkTopo(MyTopo):

    def generate_host_cpu(self, host):
        return 1

    def generate_host_bw(self, host):
        return float(Decimal('3.1'))

    def generate_switch_bw(self, switch, dst, attacker_default_switch=''):
        return float(Decimal('3.1'))

    def build(self, **_opts):
        global GLOBALS
        info("*** Creating switches\n")

        # Server switch
        s0 = self.addSwitch('s0')

        GLOBALS.controlled_switches_list = ['s101', 's102', 's103', 's104']
        GLOBALS.router_switches_list = ['s1', 's2', 's3', 's4', 's5', 's6']
        GLOBALS.client_hosts_list = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        host_default_switch_relation = {
            'h1': {
                'default_path_switch': 's101'
            },
            'h2': {
                'default_path_switch': 's102'
            },
            'h3': {
                'default_path_switch': 's102'
            },
            'h4': {
                'default_path_switch': 's103'
            },
            'h5': {
                'default_path_switch': 's104'
            },
            'h6': {
                'default_path_switch': 's104'
            }
        }
        for switch in GLOBALS.controlled_switches_list:
            switch_node = self.addSwitch(switch)

        for switch in GLOBALS.router_switches_list:
            switch_node = self.addSwitch(switch)

        attacker_default_switch = host_default_switch_relation[GLOBALS.attackers[0]]['default_path_switch']

        s0_bandwidthes = {
            's0-s101': self.generate_switch_bw("s0", 's101', attacker_default_switch),
            's0-s102': self.generate_switch_bw("s0", 's102', attacker_default_switch),
            's0-s103': self.generate_switch_bw("s0", 's103', attacker_default_switch),
            's0-s104': self.generate_switch_bw("s0", 's104', attacker_default_switch)
        }

        switches_bandwidthes = {
            's101-s102': self.generate_switch_bw("s101", 's102'),
            's101-s103': self.generate_switch_bw("s101", 's103'),
            's101-s104': self.generate_switch_bw("s101", 's104'),

            's102-s103': self.generate_switch_bw("s102", 's103'),
            's102-s104': self.generate_switch_bw("s102", 's104'),

            's103-s104': self.generate_switch_bw("s103", 's104'),
        }
        switches_bandwidthes['s102-s101'] = switches_bandwidthes['s101-s102']
        switches_bandwidthes['s103-s101'] = switches_bandwidthes['s101-s103']
        switches_bandwidthes['s104-s101'] = switches_bandwidthes['s101-s104']

        switches_bandwidthes['s103-s102'] = switches_bandwidthes['s102-s103']
        switches_bandwidthes['s104-s102'] = switches_bandwidthes['s102-s104']

        switches_bandwidthes['s104-s103'] = switches_bandwidthes['s103-s104']

        hosts_bandwidthes = {}
        hosts_bandwidthes['hs'] = self.generate_host_bw("hs")
        for host in GLOBALS.client_hosts_list:
            hosts_bandwidthes[host] = self.generate_host_bw(host)

        GLOBALS.network_spec['switches'] = {
            's0': {
                'ports': [
                    's0-eth0',
                    's0-eth101',
                    's0-eth102',
                    's0-eth103',
                    's0-eth104',
                    's0-eth6',
                ],
                'connections': {
                    's101': {
                        'src_int': 's0-eth101',
                        'dst_int': 's101-eth0',
                        'bw': f'{s0_bandwidthes["s0-s101"]}',
                    },
                    's102': {
                        'src_int': 's0-eth102',
                        'dst_int': 's102-eth0',
                        'bw': f'{s0_bandwidthes["s0-s102"]}',
                    },
                    's103': {
                        'src_int': 's0-eth103',
                        'dst_int': 's103-eth0',
                        'bw': f'{s0_bandwidthes["s0-s103"]}',
                    },
                    's104': {
                        'src_int': 's0-eth104',
                        'dst_int': 's104-eth0',
                        'bw': f'{s0_bandwidthes["s0-s104"]}',
                    }
                }
            },
            's101': {
                'ports': [
                    's101-eth0',
                    's101-eth1',
                    's101-eth102',
                    's101-eth103',
                    's101-eth104'
                ],
                'connections': {
                    's0': {
                        'src_int': 's101-eth0',
                        'dst_int': 's0-eth101',
                        'bw': f'{s0_bandwidthes["s0-s101"]}',
                    },
                    's102': {
                        'src_int': 's101-eth102',
                        'dst_int': 's102-eth101',
                        'bw': f'{switches_bandwidthes["s101-s102"]}',
                    },
                    's103': {
                        'src_int': 's101-eth103',
                        'dst_int': 's103-eth101',
                        'bw': f'{switches_bandwidthes["s101-s103"]}',
                    },
                    's104': {
                        'src_int': 's101-eth104',
                        'dst_int': 's104-eth101',
                        'bw': f'{switches_bandwidthes["s101-s104"]}'
                    }
                }
            },
            's102': {
                'ports': [
                    's102-eth0',
                    's102-eth2',
                    's102-eth3',
                    's102-eth101',
                    's102-eth103',
                    's102-eth104'
                ],
                'connections': {
                    's0': {
                        'src_int': 's102-eth0',
                        'dst_int': 's0-eth102',
                        'bw': f'{s0_bandwidthes["s0-s102"]}',
                    },
                    's101': {
                        'src_int': 's102-eth101',
                        'dst_int': 's101-eth102',
                        'bw': f'{switches_bandwidthes["s102-s101"]}',
                    },
                    's103': {
                        'src_int': 's102-eth103',
                        'dst_int': 's103-eth102',
                        'bw': f'{switches_bandwidthes["s102-s103"]}',
                    },
                    's104': {
                        'src_int': 's102-eth104',
                        'dst_int': 's104-eth102',
                        'bw': f'{switches_bandwidthes["s102-s104"]}'
                    }
                }
            },
            's103': {
                'ports': [
                    's103-eth0',
                    's103-eth4',
                    's103-eth101',
                    's103-eth102',
                    's103-eth104'
                ],
                'connections': {
                    's0': {
                        'src_int': 's103-eth0',
                        'dst_int': 's0-eth103',
                        'bw': f'{s0_bandwidthes["s0-s103"]}',
                    },
                    's101': {
                        'src_int': 's103-eth101',
                        'dst_int': 's101-eth103',
                        'bw': f'{switches_bandwidthes["s103-s101"]}',
                    },
                    's102': {
                        'src_int': 's103-eth102',
                        'dst_int': 's102-eth103',
                        'bw': f'{switches_bandwidthes["s103-s102"]}',
                    },
                    's104': {
                        'src_int': 's103-eth104',
                        'dst_int': 's104-eth103',
                        'bw': f'{switches_bandwidthes["s103-s104"]}'
                    }
                }
            },
            's104': {
                'ports': [
                    's104-eth0',
                    's104-eth5',
                    's104-eth6',
                    's104-eth101',
                    's104-eth102',
                    's104-eth103'
                ],
                'connections': {
                    's0': {
                        'src_int': 's104-eth0',
                        'dst_int': 's0-eth104',
                        'bw': f'{s0_bandwidthes["s0-s104"]}',
                    },
                    's101': {
                        'src_int': 's104-eth101',
                        'dst_int': 's101-eth104',
                        'bw': f'{switches_bandwidthes["s104-s101"]}',
                    },
                    's102': {
                        'src_int': 's104-eth102',
                        'dst_int': 's102-eth104',
                        'bw': f'{switches_bandwidthes["s104-s102"]}',
                    },
                    's103': {
                        'src_int': 's104-eth103',
                        'dst_int': 's103-eth104',
                        'bw': f'{switches_bandwidthes["s104-s103"]}',
                    }
                }
            },
            's1': {
                'connections': {
                    's101': {
                        'src_int': 's1-eth101',
                        'dst_int': 's101-eth1',
                        'bw': f'{hosts_bandwidthes["h1"]}',
                        'id': 1,
                        'connected': True,
                    }
                },
                'ports': [
                    's1-eth0',
                    's1-eth101'
                ]
            },
            's2': {
                'connections': {
                    's102': {
                        'src_int': 's2-eth102',
                        'dst_int': 's102-eth2',
                        'bw': f'{hosts_bandwidthes["h2"]}',
                        'id': 2,
                        'connected': True,
                    }
                },
                'ports': [
                    's2-eth0',
                    's2-eth102'
                ]
            },
            's3': {
                'connections': {
                    's102': {
                        'src_int': 's3-eth102',
                        'dst_int': 's102-eth3',
                        'bw': f'{hosts_bandwidthes["h3"]}',
                        'id': 1,
                        'connected': True,
                    }
                },
                'ports': [
                    's3-eth0',
                    's3-eth102'
                ]
            },
            's4': {
                'connections': {
                    's103': {
                        'src_int': 's4-eth103',
                        'dst_int': 's103-eth4',
                        'bw': f'{hosts_bandwidthes["h4"]}',
                        'id': 2,
                        'connected': True,
                    }
                },
                'ports': [
                    's4-eth0',
                    's4-eth103'
                ]
            },
            's5': {
                'connections': {
                    's104': {
                        'src_int': 's5-eth104',
                        'dst_int': 's104-eth5',
                        'bw': f'{hosts_bandwidthes["h5"]}',
                        'id': 3,
                        'connected': True,
                    }
                },
                'ports': [
                    's5-eth0',
                    's5-eth104'
                ]
            },
            's6': {
                'connections': {
                    's104': {
                        'src_int': 's6-eth104',
                        'dst_int': 's104-eth6',
                        'bw': f'{hosts_bandwidthes["h6"]}',
                        'id': 3,
                        'connected': True,
                    }
                },
                'ports': [
                    's6-eth0',
                    's6-eth104'
                ]
            }
        }

        info("*** Creating hosts\n")

        hs = self.addHost('hs', ip="10.0.1.101/16", cpu=self.generate_host_cpu('hs'), mac='00:00:00:00:01:00')
        for i in range(1, len(GLOBALS.client_hosts_list) + 1):
            host = GLOBALS.client_hosts_list[i - 1]
            host_node = self.addHost(host, ip=f"10.0.1.{i}/16", cpu=self.generate_host_cpu(host),
                                     mac=f'00:00:00:00:00:0{i}')

        GLOBALS.network_spec['hosts'] = {
            'hs': {
                'ip': '10.0.1.101',
                'router_switch': 's0',
                'src_int': 'hs-eth0',
                'dst_int': 's0-eth0',
                'connected': True,
                'bw': f'{hosts_bandwidthes["hs"]}',
                'mac': '00:00:00:00:01:00'
            },
            'h1': {
                'ip': '10.0.1.1',
                'src_int': 'h1-eth0',
                'router_switch': 's1',
                'dst_int': 's1-eth0',
                'connected': True,
                'bw': f'{hosts_bandwidthes["h1"]}',
                'mac': '00:00:00:00:00:01',
                'current_path': {
                    's101': True,
                    's102': False,
                    's103': False,
                    's104': False
                },
                'default_path_switch': host_default_switch_relation['h1']['default_path_switch']
            },
            'h2': {
                'ip': '10.0.1.2',
                'src_int': 'h2-eth0',
                'dst_int': 's2-eth0',
                'router_switch': 's2',
                'connected': True,
                'bw': f'{hosts_bandwidthes["h2"]}',
                'mac': '00:00:00:00:00:02',
                'current_path': {
                    's101': False,
                    's102': True,
                    's103': False,
                    's104': False
                },
                'default_path_switch': host_default_switch_relation['h2']['default_path_switch']
            },
            'h3': {
                'ip': '10.0.1.3',
                'src_int': 'h3-eth0',
                'dst_int': 's3-eth0',
                'router_switch': 's3',
                'connected': True,
                'bw': f'{hosts_bandwidthes["h3"]}',
                'mac': '00:00:00:00:00:03',
                'current_path': {
                    's101': False,
                    's102': True,
                    's103': False,
                    's104': False
                },
                'default_path_switch': host_default_switch_relation['h3']['default_path_switch']
            },
            'h4': {
                'ip': '10.0.1.4',
                'src_int': 'h4-eth0',
                'dst_int': 's4-eth0',
                'router_switch': 's4',
                'connected': True,
                'bw': f'{hosts_bandwidthes["h4"]}',
                'mac': '00:00:00:00:00:04',
                'current_path': {
                    's101': False,
                    's102': False,
                    's103': True,
                    's104': False
                },
                'default_path_switch': host_default_switch_relation['h4']['default_path_switch']
            },
            'h5': {
                'ip': '10.0.1.5',
                'src_int': 'h5-eth0',
                'dst_int': 's5-eth0',
                'router_switch': 's5',
                'connected': True,
                'bw': f'{hosts_bandwidthes["h5"]}',
                'mac': '00:00:00:00:00:05',
                'current_path': {
                    's101': False,
                    's102': False,
                    's103': True,
                    's104': False
                },
                'default_path_switch': host_default_switch_relation['h5']['default_path_switch']
            },
            'h6': {
                'ip': '10.0.1.6',
                'src_int': 'h6-eth0',
                'dst_int': 's6-eth0',
                'router_switch': 's6',
                'connected': True,
                'bw': f'{hosts_bandwidthes["h6"]}',
                'mac': '00:00:00:00:00:06',
                'current_path': {
                    's101': False,
                    's102': False,
                    's103': False,
                    's104': True
                },
                'default_path_switch': host_default_switch_relation['h6']['default_path_switch']
            }
        }

        info("*** Creating links\n")

        max_switch_queue_size = 10000000
        max_host_queue_size = 10000000

        for src_switch in GLOBALS.controlled_switches_list:
            info(
                f"*** Init link {src_switch}({GLOBALS.network_spec['switches'][src_switch]['connections']['s0']['src_int']}) --> s0({GLOBALS.network_spec['switches'][src_switch]['connections']['s0']['dst_int']}) with bw = {float(GLOBALS.network_spec['switches'][src_switch]['connections']['s0']['bw'])}  ***\n")
            self.addLink(src_switch, s0,
                         intfName1=GLOBALS.network_spec['switches'][src_switch]['connections']['s0']['src_int'],
                         intfName2=GLOBALS.network_spec['switches'][src_switch]['connections']['s0']['dst_int'],
                         bw=float(GLOBALS.network_spec['switches'][src_switch]['connections']['s0']['bw']),
                         max_queue_size=max_switch_queue_size)

        for src_switch_index in range(len(GLOBALS.controlled_switches_list) - 1):
            for dst_switch_index in range(src_switch_index + 1, len(GLOBALS.controlled_switches_list)):
                src_switch = GLOBALS.controlled_switches_list[src_switch_index]
                dst_switch = GLOBALS.controlled_switches_list[dst_switch_index]
                src_interface = shared.get_interface_name(src_switch, dst_switch)
                dst_interface = shared.get_interface_name(dst_switch, src_switch)
                info(
                    f"*** Init link {src_switch}({src_interface}) --> {dst_switch}({dst_interface}) with bw = {float(GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'])}  ***\n")
                self.addLink(src_switch, dst_switch, intfName1=src_interface, intfName2=dst_interface,
                             bw=float(GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw']),
                             max_queue_size=max_switch_queue_size)

        for src_switch in GLOBALS.router_switches_list:
            for dst_switch in (GLOBALS.network_spec['switches'][src_switch]['connections']).keys():
                info(
                    f"*** Init link {src_switch}({GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['src_int']}) --> {dst_switch}({GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['dst_int']}) with bw = {float(GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'])}  ***\n")
                self.addLink(src_switch, dst_switch,
                             intfName1=GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch][
                                 'src_int'],
                             intfName2=GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch][
                                 'dst_int'],
                             bw=float(GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw']),
                             max_queue_size=max_switch_queue_size)

        info(
            f"*** Init link hs({GLOBALS.network_spec['hosts']['hs']['src_int']}) --> s0({GLOBALS.network_spec['hosts']['hs']['dst_int']}) with bw = {float(GLOBALS.network_spec['hosts']['hs']['bw'])}  ***\n")
        self.addLink(s0, hs, intfName1=GLOBALS.network_spec['hosts']['hs']['dst_int'],
                     intfName2=GLOBALS.network_spec['hosts']['hs']['src_int'], params2={'ip': "10.0.1.101/16"},
                     bw=float(GLOBALS.network_spec['hosts']['hs']['bw']), max_queue_size=max_host_queue_size)

        for i in range(1, 7):
            host = f'h{i}'
            switch = f's{i}'
            info(
                f"*** Init link {host}({GLOBALS.network_spec['hosts'][host]['src_int']}) --> {switch}({GLOBALS.network_spec['hosts'][host]['dst_int']}) with bw = {float(GLOBALS.network_spec['hosts'][host]['bw'])}  ***\n")
            self.addLink(switch, host, intfName1=GLOBALS.network_spec['hosts'][host]['dst_int'],
                         intfName2=GLOBALS.network_spec['hosts'][host]['src_int'], params2={'ip': f"10.0.1.{i}/16"},
                         bw=float(GLOBALS.network_spec['hosts'][host]['bw']), max_queue_size=max_host_queue_size)


def main(_GLOBALS):
    global GLOBALS
    GLOBALS = _GLOBALS
    GLOBALS.net = MyMininet()
    NetworkTopo().build()

    GLOBALS.switch_interface_port_mapping = {
        's0': {'lo': 0, 's0-eth0': 5, 's0-eth101': 1, 's0-eth102': 2, 's0-eth103': 3, 's0-eth104': 4, 's0-eth6': 6},
        's1': {'lo': 0, 's1-eth0': 2, 's1-eth101': 1}, 's2': {'lo': 0, 's2-eth0': 2, 's2-eth102': 1},
        's3': {'lo': 0, 's3-eth0': 2, 's3-eth102': 1}, 's4': {'lo': 0, 's4-eth0': 2, 's4-eth103': 1},
        's5': {'lo': 0, 's5-eth0': 2, 's5-eth104': 1}, 's6': {'lo': 0, 's6-eth0': 2, 's6-eth104': 1},
        's101': {'lo': 0, 's101-eth1': 5, 's101-eth0': 1, 's101-eth102': 2, 's101-eth103': 3, 's101-eth104': 4},
        's102': {'lo': 0, 's102-eth2': 5, 's102-eth3': 6, 's102-eth101': 2, 's102-eth0': 1, 's102-eth103': 3,
                 's102-eth104': 4},
        's103': {'lo': 0, 's103-eth4': 5, 's103-eth101': 2, 's103-eth102': 3, 's103-eth0': 1, 's103-eth104': 4},
        's104': {'lo': 0, 's104-eth5': 5, 's104-eth6': 6, 's104-eth101': 2, 's104-eth102': 3, 's104-eth103': 4,
                 's104-eth0': 1}}

    commands = []
    # ARP Rules
    # s0
    commands.append(shared.flood_arp_for_icmp_command(target=GLOBALS.s0_switch, priority=GLOBALS.server_switch_flood_priority))

    # ARP Rules - Controlled switches
    commands.extend(shared.init_arp_for_cotnrolled_switches(GLOBALS.controlled_switch_arp_priority, GLOBALS.controlled_switch_flood_priority,
                                                     shared.build_switch_info_for_arp()))
    commands.extend(
        shared.init_arp_for_non_controlled_switches(GLOBALS.non_controlled_switch_arp_priority, GLOBALS.router_switches_list))

    # s0 to 8.8.8.8
    commands.append(shared.init_flow_for_global_dns_from_server_switch(GLOBALS.s0_switch, GLOBALS.highest_priority, GLOBALS.global_dns, "s0-eth6"))

    # s0 to hs
    commands.append(shared.init_flow_from_switch_to_direct_host_via_mac(GLOBALS.s0_switch, GLOBALS.highest_priority, GLOBALS.server_host))

    # S0 -> controlled switch
    commands.extend(shared.init_flow_from_server_switch_to_controlled_switch_for_hosts(GLOBALS.s0_switch, GLOBALS.highest_priority))

    for host in GLOBALS.client_hosts_list:
        router_switch = GLOBALS.network_spec['hosts'][host]['router_switch']
        controlled_switch = GLOBALS.network_spec['hosts'][host]['default_path_switch']

        router_switch_to_host_src_side_interface = GLOBALS.network_spec['hosts'][host]['dst_int']
        router_switch_to_controlled_switch_src_side_interface = shared.get_interface_name(router_switch,
                                                                                          controlled_switch)

        # router switch --> 8.8.8.8 controlled switch
        commands.append(OvsOfctlAddFlowCommand(router_switch, OvsOfctlCommandArguments(
            protocol=consts.OVS_PROTOCOL_IP,
            in_port=f"{GLOBALS.switch_interface_port_mapping[router_switch][router_switch_to_host_src_side_interface]}",
            priority=GLOBALS.highest_priority,
            ip_destination=GLOBALS.global_dns,
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[router_switch][router_switch_to_controlled_switch_src_side_interface]}")])))

        # router switch --> hs controlled switch
        commands.append(OvsOfctlAddFlowCommand(router_switch, OvsOfctlCommandArguments(
            in_port=f"{GLOBALS.switch_interface_port_mapping[router_switch][router_switch_to_host_src_side_interface]}",
            priority=GLOBALS.highest_priority,
            mac_destination=GLOBALS.network_spec['hosts'][GLOBALS.server_host]['mac'],
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[router_switch][router_switch_to_controlled_switch_src_side_interface]}")])))

        # router switch -> host
        commands.append(OvsOfctlAddFlowCommand(router_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_destination=GLOBALS.network_spec['hosts'][host]['mac'],
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[router_switch][router_switch_to_host_src_side_interface]}")])))

        controlled_switch_to_router_switch_src_side_interface = shared.get_interface_name(controlled_switch,
                                                                                          router_switch)
        controlled_switch_to_s0_switch_src_side_interface = shared.get_interface_name(controlled_switch, GLOBALS.s0_switch)

        # controlled switch -> 8.8.8.8 (passing through s0)
        commands.append(OvsOfctlAddFlowCommand(controlled_switch, OvsOfctlCommandArguments(
            protocol=consts.OVS_PROTOCOL_IP,
            priority=GLOBALS.highest_priority,
            ip_destination=GLOBALS.global_dns,
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[controlled_switch][controlled_switch_to_s0_switch_src_side_interface]}")])))

        # controlled switch -> server (passing through s0)
        commands.append(OvsOfctlAddFlowCommand(controlled_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_source=GLOBALS.network_spec['hosts'][host]['mac'],
            mac_destination=GLOBALS.network_spec['hosts'][GLOBALS.server_host]['mac'],
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[controlled_switch][controlled_switch_to_s0_switch_src_side_interface]}")])))

        # controlled switch -> router switch
        commands.append(OvsOfctlAddFlowCommand(controlled_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_destination=GLOBALS.network_spec['hosts'][host]['mac'],
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[controlled_switch][controlled_switch_to_router_switch_src_side_interface]}")])))

    def logit(cmd):
        print(cmd)

    GLOBALS.ovs = OvsIntermediateMininet(GLOBALS.net, True, True, custom_cmd_logging_function=logit)
    for command in commands:
        GLOBALS.ovs.apply_command(command)


if __name__ == '__main__':
    config = {"servers": "[hs]", "attackers": "[h5]", "manuel_receivers": True, "unified_host_bandwidth": None,
              "unified_switch_bandwidth": None}
    shared.init(config)
    main(shared.GLOBALS)
