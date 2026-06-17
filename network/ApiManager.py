# Flask
import os

from flask import Flask
import threading
from mininet.term import makeTerm
import Shared as shared
from decimal import Decimal
from mininet.log import setLogLevel, info
import time
import re

# Intermed Imports
from intermed.OvsIntermediateMininet import *
from intermed.OvsIntermediate import *
from intermed import OvsIntermediateConstants as consts

app = Flask(__name__)

# Flask routes
def safe_cmd(node, cmd, default=''):
    """Wrapper per safe_cmd(GLOBALS.net[x], ) che gestisce AssertionError quando il nodo e' occupato."""
    try:
        return node.cmd(cmd)
    except (AssertionError, Exception) as e:
        print(f"(Network) WARNING: node busy/error, skipping cmd: {cmd[:60]} -- {e}")
        return default


@app.route("/")
def mininet_network_up_page():
    return "<p>Network is up!</p>"

@app.route("/get-host-names")
def get_host_names():
    global GLOBALS
    hosts = []
    for key in GLOBALS.network_spec['hosts']:
        hosts.append(key)
    return hosts

@app.route("/get-switches-interfaces")
def get_switches_interfaces():
    global GLOBALS
    hosts = []
    for key in GLOBALS.network_spec['hosts']:
        host_spec = shared.get_host_status(key)
        hosts.append(host_spec["dst_int"])
    return hosts

@app.route("/host-ip/<host_name>")
def get_ip_by_host_name(host_name):
    global GLOBALS
    try:
        return GLOBALS.net[host_name].IP()
    except:
        return 'UNKNOWN'

@app.route("/host-status/<host_name>")
def get_host_status(host_name):
    global GLOBALS
    return shared.get_host_status(host_name)

@app.route("/host-status-connected/<host_name>")
def get_host_status_connected(host_name):
    global GLOBALS
    return str(shared.get_host_status(host_name)['connected'])

@app.route("/get_switch-status-connected/<src_switch>")
def get_switch_status_connected(src_switch):
    global GLOBALS
    data_per_switch = {}
    for dst_switch in GLOBALS.network_spec['switches'][src_switch]['connections'].keys():
        data_per_switch[dst_switch] = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['connected']
    return data_per_switch

@app.route("/get_dst_switches/<src_switch>")
def get_dst_switches(src_switch):
    global GLOBALS
    return {'dst_switches': list(GLOBALS.network_spec['switches'][src_switch]['connections'].keys())}

@app.route("/get_switch_bw/<src_switch>/<dst_switch>")
def get_switch_bw(src_switch, dst_switch):
    global GLOBALS
    return {'bw': GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'] }

@app.route("/get_link_information/<src_switch>/<dst_switch>")
def get_link_information(src_switch, dst_switch):
        global GLOBALS
        link_info = {'tx_bytes': 0, 'rx_bytes': 0, 'bw': ''}
        src_int = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['src_int']
        dst_int = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['dst_int']
        bw = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw']
        link_info['bw'] = bw
        src_switch_interface_statistics = safe_cmd(GLOBALS.net[src_switch], f'ovs-vsctl get interface {src_int} statistics')
        dst_switch_interface_statistics = safe_cmd(GLOBALS.net[dst_switch], f'ovs-vsctl get interface {dst_int} statistics')
        for stat in src_switch_interface_statistics.replace("{", "").replace("}", "").split(","):
            item = stat.strip().split('=')
            if len(item) < 2:
                continue
            key = item[0]
            value = item[1]
            if key == 'tx_bytes':
                link_info['tx_bytes'] = int(value)
                break
        for stat in dst_switch_interface_statistics.replace("{", "").replace("}", "").split(","):
            item = stat.strip().split('=')
            if len(item) < 2:
                continue
            key = item[0]
            value = item[1]
            if key == 'rx_bytes':
                link_info['rx_bytes'] = int(value)
                break
        return link_info

@app.route("/change-host-status/<host_name>")
def change_host_status(host_name):
    global GLOBALS
    host_status = get_host_status(host_name)

    host_ip = host_status['ip']
    connected_switch = host_status['connected-switch']
    connected= host_status['connected']
    switch_port = host_status['switch-port']
    turned_on = False
    if connected:
        turned_on = False
        safe_cmd(GLOBALS.net[connected_switch], shared.get_host_switch_turn_off_link_command(host_ip, connected_switch))
        GLOBALS.network_spec['hosts'][host_name]['connected']= turned_on
    else:
        turned_on = True
        safe_cmd(GLOBALS.net[connected_switch], shared.get_host_switch_turn_on_link_command(host_ip, connected_switch, switch_port))
        GLOBALS.network_spec['hosts'][host_name]['connected'] = turned_on
    if turned_on:
        return f'the link of {host_name} is turned on successfully'
    else:
        return f'the link of {host_name} is turned off successfully'

@app.route("/get_host_path/<host_name>")
def get_host_path(host_name):
    global GLOBALS
    switches_along_the_path = {'current': [], 'default': '', 'options': []}
    
    # Special case for server host
    if host_name in GLOBALS.servers:
        switches_along_the_path['default'] = GLOBALS.s0_switch
        switches_along_the_path['current'] = [GLOBALS.s0_switch]
        return switches_along_the_path
    
    # Normal host processing
    try:
        for switch in list(GLOBALS.network_spec['hosts'][host_name]['current_path'].keys()):
            if GLOBALS.network_spec['hosts'][host_name]['current_path'][switch]:
                switches_along_the_path['current'].append(switch)
            else:
                switches_along_the_path['options'].append(switch)
        switches_along_the_path['default'] = GLOBALS.network_spec['hosts'][host_name]['default_path_switch']
    except Exception as e:
        print(f"Error getting path for host {host_name}: {str(e)}")
        # Return empty values for error cases
        switches_along_the_path['default'] = ''
        switches_along_the_path['current'] = []
        switches_along_the_path['options'] = []
    
    return switches_along_the_path

@app.route("/get-host-packet-loss/<host>")
def get_host_packet_loss(host):
    global GLOBALS
    try:
        if host in GLOBALS.network_spec['hosts']:
            # Get the host status to extract packet loss
            host_status = get_host_status(host)
            if 'loss_pct' in host_status:
                return {'loss_pct': host_status['loss_pct']}
            # Try to compute loss percentage
            tx_packets = host_status.get('tx_packets', 0)
            delivered_pkts = host_status.get('delivered_pkts', 0)
            
            if tx_packets > 0:
                loss_pct = (tx_packets - delivered_pkts) / tx_packets
            else:
                loss_pct = 0.0
                
            return {'loss_pct': loss_pct}
        return {'loss_pct': 0.0}
    except Exception as e:
        print(f"Error getting packet loss for host {host}: {str(e)}")
        return {'loss_pct': 0.0}

@app.route("/start-ddos-flooding/<attacker_host>/<victim_host>/<attack_type>")
def start_ddos_flooding_attack(attacker_host, victim_host, attack_type):
    global GLOBALS
    host_status = get_host_status(victim_host)
    victim_ip = host_status['ip']
    terminal_name = f'ddos-flooding-{attacker_host}-{victim_host}'
    pid_file = f'/tmp/scapy_{attacker_host}.pid'
    safe_cmd(GLOBALS.net[attacker_host], f"{shared.PYTHON} {GLOBALS.network_dir}/ScapyFlooding.py -ip {victim_ip} -p 8999 -att {attack_type} & echo $! > {pid_file}")
    GLOBALS.ddos_flooding_attacks[terminal_name] = {'host': attacker_host, 'pid_file': pid_file}
    log = f"Starting attack --> Attacker: {attacker_host} --> Victim: {victim_host}"
    print(f'(Network) ==> {log}')
    return log

@app.route("/stop-ddos-flooding/<attacker_host>/<victim_host>")
def stop_ddos_flooding_attack(attacker_host, victim_host):
    global GLOBALS
    terminal_name = f'ddos-flooding-{attacker_host}-{victim_host}'
    try:
        entry = GLOBALS.ddos_flooding_attacks[terminal_name]
        pid_file = entry['pid_file']
        safe_cmd(GLOBALS.net[entry['host']], f"if [ -f {pid_file} ]; then pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; fi")
        del GLOBALS.ddos_flooding_attacks[terminal_name]
    except Exception as e:
        print(f'Warning stopping ddos {terminal_name}: {e}')
    log = f"Stopping attack --> Attacker: {attacker_host} --> Victim: {victim_host}"
    print(f'(Network) ==> {log}')
    return log

@app.route("/start-mhddos/<attacker_host>/<victim_host>/<attack_type>")
def start_mhddos_attack(attacker_host, victim_host, attack_type):
    global GLOBALS
    host_status = get_host_status(victim_host)
    victim_ip = host_status['ip']
    terminal_name = f'mhddos-{attacker_host}-{victim_host}'
    
    # Build command based on attack type
    cmd = f"{shared.PYTHON} -u {GLOBALS.mhddos_start_path}"
    
    attack_type = attack_type.upper()
    if attack_type == "TCP":
        # TCP is a Layer 4 attack: <method> <ip:port> <threads> <duration>
        cmd += f" TCP {victim_ip}:80 50 100000"
    elif attack_type == "UDP":
        # UDP is also a Layer 4 attack
        cmd += f" UDP {victim_ip}:80 50 100000"
    elif attack_type == "HTTP":
        # GET is a Layer 7 attack: <method> <url> <socks_type> <threads> <proxylist> <rpc> <duration>
        cmd += f" GET http://{victim_ip}:80/ 1 50 none 1 60"
    elif attack_type == "POST":
        # POST is a Layer 7 attack with payload
        cmd += f" POST http://{victim_ip}:80/ 1 50 none 1 60"
    elif attack_type == "STRESS":
        # STRESS is a Layer 7 attack
        cmd += f" STRESS http://{victim_ip}:80/ 1 100 none 1 60"
    elif attack_type in ["ICMP", "SYN"]:
        # For ICMP and SYN, use ScapyFlooding.py instead of MHDDoS
        cmd += f" {attack_type} {victim_ip}:80 50 100000"
    else:
        # Default to TCP for backward compatibility
        cmd += f" TCP {victim_ip}:80 50 100000"
        print(f"(Network) ==> Warning: Unknown attack type '{attack_type}'. Defaulting to TCP.")
    
    pid_file = f'/tmp/mhddos_{attacker_host}.pid'
    safe_cmd(GLOBALS.net[attacker_host], f"{cmd} & echo $! > {pid_file}")
    GLOBALS.ddos_flooding_attacks[terminal_name] = {'host': attacker_host, 'pid_file': pid_file}
    
    log = f"Starting {attack_type} attack --> Attacker: {attacker_host} --> Victim: {victim_host}"
    print(f'(Network) ==> {log}')
    return log

@app.route("/stop-mhddos/<attacker_host>/<victim_host>")
def stop_mhddos_attack(attacker_host, victim_host):
    global GLOBALS
    terminal_name = f'mhddos-{attacker_host}-{victim_host}'
    try:
        entry = GLOBALS.ddos_flooding_attacks[terminal_name]
        pid_file = entry['pid_file']
        safe_cmd(GLOBALS.net[attacker_host], 
            f"if [ -f {pid_file} ]; then pid=$(cat {pid_file}); pgid=$(ps -o pgid= -p $pid 2>/dev/null | tr -d ' '); if [ -n \"$pgid\" ] && [ \"$pgid\" != \"1\" ]; then kill -- -$pgid 2>/dev/null; fi; kill -9 $pid 2>/dev/null; rm -f {pid_file}; fi"
        )
        del GLOBALS.ddos_flooding_attacks[terminal_name]
    except Exception as e:
        print(f'(Network) ==> Warning stopping mhddos {terminal_name}: {e}')
    log = f"Stopping attack --> Attacker: {attacker_host} --> Victim: {victim_host}"
    print(f'(Network) ==> {log}')
    return log

@app.route("/reset-http-server")
def reset_http_server():
    global GLOBALS
    server_port = 80
    for host_name in GLOBALS.servers:
        get_pid_using_port(host_name, server_port)

    info("(Network) ==> stopping HTTP server...\n")
    for entry in GLOBALS.http_servers:
        try:
            pid_file = entry['pid_file']
            safe_cmd(GLOBALS.net[entry['host']], f"if [ -f {pid_file} ]; then pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; fi")
        except Exception as e:
            print(f'Warning stopping http server: {e}')
    GLOBALS.http_servers = []

    for host_name in GLOBALS.servers:
        ip = get_host_status(host_name)['ip']
        check_port_used_and_kill_process(host_name, server_port)
        pid_file = f'/tmp/httpserver_{host_name}.pid'
        safe_cmd(GLOBALS.net[host_name], f"{shared.PYTHON} {GLOBALS.http_server_file} -n {host_name} -ip {ip} & echo $! > {pid_file}")
        GLOBALS.http_servers.append({'host': host_name, 'pid_file': pid_file})
        info("(Network) ==> starting HTTP server...\n")

    log = f"HTTP server reset for hosts: {GLOBALS.servers}"
    info(f'(Network) ==> {log}')
    return log

@app.route("/get-host-interface-statistics/<host_name>")
def get_host_interface_statistics(host_name):
    global GLOBALS
    host_status = get_host_status(host_name)
    # for example: interface is s2-eth3, where s2 is the switch, 3 is the port
    interface = f"{host_status['dst_int']}"
    return safe_cmd(GLOBALS.net[host_status['router_switch']], f'ovs-vsctl get interface {interface} statistics')

@app.route("/get-host-ifconfig/<host>")
def get_host_ifconfig(host):
    global GLOBALS
    return safe_cmd(GLOBALS.net[host], f'ifconfig')

@app.route("/get-switch-statistics/<switch>/<interface_name>")
def get_switch_interface_statistics(switch, interface_name):
    global GLOBALS
    interface = interface_name
    return safe_cmd(GLOBALS.net[switch], f'ovs-vsctl get interface {interface} statistics')

@app.route("/start-ditg-flow/<source_host>/<destination_host>/<duration_ms>")
def start_ditg_flow(source_host, destination_host, duration_ms):
    global GLOBALS
    # Start the process in a different thread
    thread = threading.Thread(target=start_ditg_flow_thread, args=(source_host, destination_host, duration_ms,), daemon=True)
    thread.start()
    log = f"Starting flow --> Sender: {source_host} --> Receiver: {destination_host}"
    print(f'(Network) ==> {log}')
    return log

@app.route("/start-tcp-flow/<source_host>/<destination_host>/<duration_ms>")
def start_tcp_flow(source_host, destination_host, duration_ms):
    global GLOBALS
    # Start the process in a different thread
    thread = threading.Thread(target=start_tcp_flow_thread, args=(source_host, destination_host, duration_ms,), daemon=True)
    thread.start()
    log = f"Starting flow --> Sender: {source_host} --> Receiver: {destination_host}"
    print(f'(Network) ==> {log}')
    return log

def start_ditg_flow_thread(source_host, destination_host, duration_ms):
    global GLOBALS
    destination_host_status = get_host_status(destination_host)

    # Terminal names
    source_terminal_name = f'ditg-flow-{source_host}-{destination_host}-src'
    duration_ms = int(duration_ms) + 1
    print(f'running with {duration_ms}')
    # Creating terminals
    # sleep is added in order for the sender to wait the receiver to be started
    pid_file = f'/tmp/ditg_{source_host}.pid'
    safe_cmd(GLOBALS.net[source_host], f"{GLOBALS.ditg_directory}/ITGSend -T TCP -a {destination_host_status['ip']} -t {duration_ms} -z 60001 & echo $! > {pid_file}")
    GLOBALS.ditg_flows[source_terminal_name] = {'host': source_host, 'pid_file': pid_file}


def start_tcp_flow_thread(source_host, destination_host, duration_ms):
    global GLOBALS
    try:
        destination_host_status = get_host_status(destination_host)
    except Exception as e:
        print(f'(Network) WARNING: start_tcp_flow_thread failed getting host status: {e}')
        return
    source_terminal_name = f'tcp-flow-{source_host}-{destination_host}-src'
    duration_s = int(int(duration_ms) / 1000)
    pid_file = f'/tmp/tcpflow_{source_host}.pid'
    print(f'(Network) ==> TCP flow {source_host}->{destination_host} for {duration_s}s')
    safe_cmd(GLOBALS.net[source_host], 
        f"{shared.PYTHON} {GLOBALS.tcp_flow_client_file} -n {source_host}"
        f" -ip {destination_host_status['ip']} -t {duration_s} -np 100000 & "
        f"echo $! > {pid_file}"
    )
    GLOBALS.tcp_flows[source_terminal_name] = {'host': source_host, 'pid_file': pid_file}
    print(f'(Network) ==> started {source_terminal_name}')

@app.route("/stop-all-ditg-flows")
def stop_all_ditg_flows():
    global GLOBALS
    for name, entry in list(GLOBALS.ditg_flows.items()):
        try:
            safe_cmd(GLOBALS.net[entry["host"]], f"if [ -f {entry['pid_file']} ]; then pid=$(cat {entry['pid_file']}); kill $pid 2>/dev/null; rm -f {entry['pid_file']}; fi")
        except Exception as e:
            print(f'Warning stopping ditg {name}: {e}')
    GLOBALS.ditg_flows.clear()
    print(f'(Network) ==> Stopped all DITG flows')
    return "Stopped all DITG flows"

@app.route("/stop-all-tcp-flows")
def stop_all_tcp_flows():
    global GLOBALS
    for name, entry in list(GLOBALS.tcp_flows.items()):
        try:
            host = entry['host']
            pid_file = entry['pid_file']
            safe_cmd(GLOBALS.net[host], 
                f"if [ -f {pid_file} ]; then "
                f"  pid=$(cat {pid_file}); "
                f"  kill $pid 2>/dev/null; "
                f"  rm -f {pid_file}; "
                f"fi"
            )
        except Exception as e:
            print(f'(Network) ==> Warning stopping tcp flow {name}: {e}')
    GLOBALS.tcp_flows.clear()
    print(f'(Network) ==> Stopped all TCP flows')
    return "Stopped all TCP flows"


@app.route("/reset-ditg-receivers")
def reset_ditg_receivers():
    global GLOBALS

    for entry in GLOBALS.ditg_receivers:
        try:
            pid_file = entry['pid_file']
            safe_cmd(GLOBALS.net[entry['host']], f"if [ -f {pid_file} ]; then pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; fi")
        except Exception as e:
            print(f'Warning stopping ditg receiver: {e}')
    GLOBALS.ditg_receivers = []

    for host_name in GLOBALS.servers:
        # Creating DITG Receiver in Host -a {shared.get_host_status(host_name)['ip']}
        try:
            os.remove(f"{GLOBALS.tmp_dir}/ITGRecv.log")
        except FileNotFoundError:
            pass
        pid_file = f'/tmp/ditgrecv_{host_name}.pid'
        safe_cmd(GLOBALS.net[host_name], f"nice -n -20 {GLOBALS.ditg_directory}/ITGRecv -l {GLOBALS.tmp_dir}/ITGRecv.log & echo $! > {pid_file}")
        GLOBALS.ditg_receivers.append({'host': host_name, 'pid_file': pid_file})

    log = f"Resetting DITG for hosts: {GLOBALS.servers}"
    print(f'(Network) ==> {log}')
    return log

@app.route("/reset-tcp-receivers")
def reset_tcp_receivers():
    global GLOBALS
    server_port = 80
    for host_name in GLOBALS.servers:
        get_pid_using_port(host_name, server_port)

    info("(Network) ==> stopping server...\n")
    for entry in GLOBALS.tcp_receivers:
        try:
            pid_file = entry['pid_file']
            safe_cmd(GLOBALS.net[entry['host']], f"if [ -f {pid_file} ]; then pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; fi")
        except Exception as e:
            print(f'Warning stopping tcp receiver: {e}')
    GLOBALS.tcp_receivers = []


    for host_name in GLOBALS.servers:
        ip = get_host_status(host_name)['ip']
        check_port_used_and_kill_process(host_name, server_port)
        pid_file = f'/tmp/tcpserver_{host_name}.pid'
        safe_cmd(GLOBALS.net[host_name], 
            f"{shared.PYTHON} {GLOBALS.tcp_flow_server_file} -n {host_name} -ip {ip} & echo $! > {pid_file}"
        )
        GLOBALS.tcp_receivers.append({'host': host_name, 'pid_file': pid_file})
        info("(Network) ==> starting server...\n")

    log = f"Resetting TCP for hosts: {GLOBALS.servers}"
    info(f'(Network) ==> {log}')
    return log

@app.route("/stop-tcp-receivers")
def stop_tcp_receivers():
    global GLOBALS
    server_port = 80
    for host_name in GLOBALS.servers:
        get_pid_using_port(host_name, server_port)

    info("(Network) ==> stopping server...\n")
    for entry in GLOBALS.tcp_receivers:
        try:
            pid_file = entry['pid_file']
            host = entry['host']
            safe_cmd(GLOBALS.net[host], f"if [ -f {pid_file} ]; then pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; fi")
        except Exception as e:
            print(f'Warning stopping tcp receiver: {e}')
    GLOBALS.tcp_receivers = []

    log = f"Stopped TCP for hosts: {GLOBALS.servers}"
    info(f'(Network) ==> {log}')
    return log

def get_pid_using_port(host_name, port):
    # Getting the process using port 80
    try:
        used_port_result = safe_cmd(GLOBALS.net[host_name], f"ss -lptn 'sport = :{port}'")
    except AssertionError:
        print(f"(Network) WARNING: node {host_name} is busy (waiting), skipping get_pid_using_port")
        return 'None'
    info(used_port_result + "\n")
    # If port 80 is used, the result should have "..., pid={process-id},"
    pattern = re.compile(r'pid=(\d+)')
    match = pattern.search(used_port_result)
    if match:
        # Getting {process-id} value
        pid_value = match.group(1)
        info(f"(Network) ==> port <{port}> in host <{host_name}> is used by 'pid' <{pid_value}>\n")
        return pid_value
    return 'None'
def check_port_used_and_kill_process(host_name, port):
    pid_value = get_pid_using_port(host_name, port)
    if not pid_value == 'None':
        # Killing the process
        info(f"(Network) ==> killing process using port <{port}> in host <{host_name}> with 'pid' <{pid_value}>\n")
        info(safe_cmd(GLOBALS.net[host_name], f"kill {pid_value}") + "\n")

@app.route("/get-host-bw/<host>")
def get_host_bw(host):
    return {'bw': get_host_status(host)['bw']}
@app.route("/increase-host-bw/<host>/<change>")
def increase_host_bw(host, change):
    global GLOBALS

    host_spec = get_host_status(host)
    current_bw = host_spec['bw']
    new_bw = Decimal(current_bw) + Decimal(change)
    GLOBALS.network_spec['hosts'][host]['bw'] = new_bw

    host_interface = f'{host}-eth0'
    GLOBALS.net[host].intf(host_interface).config(bw=new_bw, smooth_change=False)

    switch_name = host_spec['connected-switch']
    switch_interface = f'{switch_name}-eth{host_spec["switch-port"]}'
    GLOBALS.net[switch_name].intf(switch_interface).config(bw=new_bw, smooth_change=False)
    print(f'(Network) ==> Increased bandwidth of {host} to {new_bw}')
    return 'Increased'

@app.route("/decrease-host-bw/<host>/<change>")
def decrease_host_bw(host, change):
    global GLOBALS

    host_spec = get_host_status(host)
    current_bw = Decimal(host_spec['bw'])
    new_bw = current_bw - Decimal(change)
    GLOBALS.network_spec['hosts'][host]['bw'] = new_bw

    host_interface = f'{host}-eth0'
    GLOBALS.net[host].intf(host_interface).config(bw=new_bw, smooth_change=False)

    switch_name = host_spec['connected-switch']
    switch_interface = f'{switch_name}-eth{host_spec["switch-port"]}'
    GLOBALS.net[switch_name].intf(switch_interface).config(bw=new_bw, smooth_change=False)
    print(f'(Network) ==> Decreased bandwidth of {host} to {new_bw}')
    return 'Decreased'
@app.route("/increase-switch-bw/<src_switch>/<dst_switch>/<change>")
def increase_switch_bw(src_switch, dst_switch, change):
    global GLOBALS
    print(f'(Network) ==> received request to increase BW for {src_switch}<->{dst_switch}')
    current_switch_bw= Decimal(GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'])
    new_bw = current_switch_bw + Decimal(change)

    GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'] = new_bw
    GLOBALS.network_spec['switches'][dst_switch]['connections'][src_switch]['bw'] = new_bw

    src_switch_interface = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['src_int']
    GLOBALS.net[src_switch].intf(src_switch_interface).config(bw=new_bw, smooth_change=False)

    dst_switch_interface = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['dst_int']
    GLOBALS.net[dst_switch].intf(dst_switch_interface).config(bw=new_bw, smooth_change=False)

    print(f'(Network) ==> increase bandwidth between {src_switch} and {dst_switch} from {current_switch_bw} to {new_bw}')
    return 'Switch bandwidth increased'

@app.route("/decrease-switch-bw/<src_switch>/<dst_switch>/<change>")
def decrease_switch_bw(src_switch, dst_switch, change):
    global GLOBALS
    print(f'(Network) ==> received request to decrease BW for {src_switch}<->{dst_switch}')
    current_switch_bw = Decimal(GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'])
    new_bw = current_switch_bw - Decimal(change)

    GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['bw'] = new_bw
    GLOBALS.network_spec['switches'][dst_switch]['connections'][src_switch]['bw'] = new_bw

    src_switch_interface = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['src_int']
    GLOBALS.net[src_switch].intf(src_switch_interface).config(bw=new_bw, smooth_change=False)

    dst_switch_interface = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['dst_int']
    GLOBALS.net[dst_switch].intf(dst_switch_interface).config(bw=new_bw, smooth_change=False)

    print(f'(Network) ==> decrease bandwidth between {src_switch} and {dst_switch} from {current_switch_bw} to {new_bw}')
    return 'Switch bandwidth decreased'

################################### second approach second try #############################################################
@app.route("/redirect_switch_flow/<host_name>/<dst_switch>")
def redirect_switch_flow(host_name, dst_switch):
    global GLOBALS

    host_mac_address = GLOBALS.network_spec['hosts'][host_name]['mac']
    server_mac_address = GLOBALS.network_spec['hosts'][GLOBALS.servers[0]]['mac']

    switches_along_the_path = get_host_path(host_name)['current']
    default_path_switch = GLOBALS.network_spec['hosts'][host_name]['default_path_switch']

    commands = []

    for controlled_switch in switches_along_the_path:

        # Changing network spec
        GLOBALS.network_spec['hosts'][host_name]['current_path'][controlled_switch] = False

        # Remove from S0 to controlled switch
        commands.append(OvsOfctlDelFlowsCommand(GLOBALS.s0_switch,
                                                OvsOfctlCommandArguments(mac_destination=host_mac_address)))

        if controlled_switch == default_path_switch:
            # Flow: host --> router_switch --> controlled_switch (default) --> s0 --> hs
            commands.append(OvsOfctlDelFlowsCommand(controlled_switch,
                                                    OvsOfctlCommandArguments(mac_source=host_mac_address,
                                                        mac_destination=server_mac_address)))
        else:
            # Flow: host --> router_switch --> controlled_switch_1 (default) --> controlled_switch_2 --> s0 --> hs
            # # Default path switch rule
            commands.append(OvsOfctlDelFlowsCommand(default_path_switch,
                                                    OvsOfctlCommandArguments(mac_source=host_mac_address,
                                                                             mac_destination=server_mac_address)))
            # # other controlled switch rule
            # # # Flow: host --> server
            commands.append(OvsOfctlDelFlowsCommand(controlled_switch,
                                                    OvsOfctlCommandArguments(mac_source=host_mac_address,
                                                                             mac_destination=server_mac_address)))
            # # # Flow: server --> host
            commands.append(OvsOfctlDelFlowsCommand(controlled_switch,
                                                    OvsOfctlCommandArguments(mac_source=server_mac_address,
                                                                             mac_destination=host_mac_address)))

    # Changing network spec
    GLOBALS.network_spec['hosts'][host_name]['current_path'][dst_switch] = True

    # S0 --> dst_switch
    s0_switch_int_facing_dst_switch = shared.get_interface_name(GLOBALS.s0_switch, dst_switch)

    commands.append(OvsOfctlAddFlowCommand(GLOBALS.s0_switch, OvsOfctlCommandArguments(
        priority=GLOBALS.highest_priority,
        mac_destination=host_mac_address,
        actions=[
            OvsCommandArgumentActionOutput(
                f"{GLOBALS.switch_interface_port_mapping[GLOBALS.s0_switch][s0_switch_int_facing_dst_switch]}")])))

    if dst_switch == default_path_switch:
        # Flow: host --> router_switch --> controlled_switch (default) --> s0 --> hs
        dst_switch_int_facing_s0_switch = shared.get_interface_name(dst_switch, GLOBALS.s0_switch)

        commands.append(OvsOfctlAddFlowCommand(dst_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_source=host_mac_address,
            mac_destination=server_mac_address,
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[dst_switch][dst_switch_int_facing_s0_switch]}")])))
    else:
        # Flow: host --> router_switch --> controlled_switch_1 (default) --> controlled_switch_2 (dst_switch) --> s0 --> hs
        # # Default path switch rule --> dst_switch
        default_path_switch_int_facing_dst_switch = shared.get_interface_name(default_path_switch, dst_switch)

        commands.append(OvsOfctlAddFlowCommand(default_path_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_source=host_mac_address,
            mac_destination=server_mac_address,
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[default_path_switch][default_path_switch_int_facing_dst_switch]}")])))
        # # other controlled switch rule
        # # # Flow: dst_switch --> s0
        dst_switch_int_facing_s0_switch = shared.get_interface_name(dst_switch, GLOBALS.s0_switch)

        commands.append(OvsOfctlAddFlowCommand(dst_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_source=host_mac_address,
            mac_destination=server_mac_address,
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[dst_switch][dst_switch_int_facing_s0_switch]}")])))
        # # # Flow: dst_switch --> default path switch
        dst_switch_int_facing_default_path_switch = shared.get_interface_name(dst_switch, default_path_switch)

        commands.append(OvsOfctlAddFlowCommand(dst_switch, OvsOfctlCommandArguments(
            priority=GLOBALS.highest_priority,
            mac_source=server_mac_address,
            mac_destination=host_mac_address,
            actions=[
                OvsCommandArgumentActionOutput(
                    f"{GLOBALS.switch_interface_port_mapping[dst_switch][dst_switch_int_facing_default_path_switch]}")])))

    for command in commands:
        GLOBALS.ovs.apply_command(command)

    return 'flow redirected'

################################### second approach second try #############################################################




################# To be removed Second approach first try ##############################################################################################
@app.route("/redirect-switch-flow-old/<src_switch>/<flow_number>")
def redirect_switch_flow_old(src_switch, flow_number):
    global GLOBALS
    first_switch_name = ""
    second_switch_name = ""
    third_switch_name = ""
    isconnected_first_dst_switch = False
    isconnected_second_dst_switch = False
    isconnected_third_dst_switch = False
    i=0
    for dst_switch in GLOBALS.network_spec['switches'][src_switch]['connections'].keys():
        i=i+1
        if i==1:
           isconnected_first_dst_switch = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['connected']
           first_switch_name = dst_switch
        elif i==2:
           isconnected_second_dst_switch = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['connected']
           second_switch_name = dst_switch
        elif i==3:
           isconnected_third_dst_switch = GLOBALS.network_spec['switches'][src_switch]['connections'][dst_switch]['connected']
           third_switch_name = dst_switch

    if isconnected_first_dst_switch == True & flow_number == 1:
        shared.turn_down_link(src_switch, GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['src_int'],
                              first_switch_name, GLOBALS.network_spec["switches"][src_switch][first_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['connected'] = False

        shared.turn_up_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['src_int'],
                              second_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][second_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['connected'] = True
    elif isconnected_first_dst_switch == True & flow_number ==2:
        shared.turn_down_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['src_int'],
                              first_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][first_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['connected'] = False

        shared.turn_up_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['src_int'],
                              third_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][third_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['connected'] = True

    if isconnected_second_dst_switch == True & flow_number ==1:
        shared.turn_down_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['src_int'],
                              second_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][second_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['connected'] = False

        shared.turn_up_link(src_switch,
                            GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['src_int'],
                            first_switch_name,
                            GLOBALS.network_spec["switches"][src_switch][first_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['connected'] = True

    elif isconnected_second_dst_switch == True & flow_number ==2:
        shared.turn_down_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['src_int'],
                              second_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][second_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['connected'] = False

        shared.turn_up_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['src_int'],
                              third_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][third_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['connected'] = True

    if isconnected_third_dst_switch == True & flow_number == 1:
        shared.turn_down_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['src_int'],
                              third_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][third_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['connected'] = False

        shared.turn_up_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['src_int'],
                              first_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][first_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][first_switch_name]['connected'] = False

    elif isconnected_third_dst_switch == True & flow_number == 2:
        shared.turn_down_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['src_int'],
                              third_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][third_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][third_switch_name]['connected'] = False

        shared.turn_up_link(src_switch,
                              GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['src_int'],
                              second_switch_name,
                              GLOBALS.network_spec["switches"][src_switch][second_switch_name]["dst_int"])
        GLOBALS.network_spec['switches'][src_switch]['connections'][second_switch_name]['connected'] = True

    print(f'Flow of {src_switch} has been redirectd')

    return 'flow redirected'
################# To be removed ##############################################################################################
def run_flask_thread():
    trial_num = int(os.getenv('TRIAL_NUM', '0'))
    port = 5000 + trial_num
    print(f"(Network) Flask listening on port {port}")
    app.run(debug=False, port=port, host='0.0.0.0')

def run_flask(_GLOBALS):
    global GLOBALS
    GLOBALS = _GLOBALS
    flask_thread = threading.Thread(target=run_flask_thread, daemon=True)
    flask_thread.start()