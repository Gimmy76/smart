import os
import argparse
import json
import math

PWD = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = f"{PWD}/../../input-data"
IP_BASE = "10.0.1"
MAC_BASE = "00:00:00:00:00"
current_config = {
    'file_path': '',
    'filename': '',
    'dry_run': False
}


def host_template() -> dict:
    return {
        "ip": "",
        "router_switch": "",
        "mac": "",
        "default_path_switch": ""
    }


def get_host(host_num: int, switch: str) -> dict:
    template = host_template()
    template['ip'] = get_ip(host_num)
    template['router_switch'] = get_router_switch(host_num)
    template['mac'] = get_mac(host_num)
    template['default_path_switch'] = switch
    return template


def append_host(hosts: dict, host_num: int, switch: str) -> None:
    hosts[get_host_name(host_num)] = get_host(host_num, switch)


def get_host_name(host_num: int) -> str:
    return f"h{host_num}"


def get_router_switch(host_num: int) -> str:
    return f"s{host_num}"


def get_ip(host_num: int) -> str:
    return f"{IP_BASE}.{str(host_num)}"


def get_mac(host_num: int) -> str:
    return f"{MAC_BASE}:{str(host_num).zfill(2)}"


def get_balanced_host_distribution(total_hosts, num_switches):
    """Distribute hosts evenly among switches"""
    # Calculate base number of hosts per switch
    base_hosts_per_switch = total_hosts // num_switches

    # Calculate how many switches get an extra host
    extra_hosts = total_hosts % num_switches

    # Create distribution list
    distribution = []
    for i in range(num_switches):
        if i < extra_hosts:
            distribution.append(base_hosts_per_switch + 1)
        else:
            distribution.append(base_hosts_per_switch)

    return distribution


def validate_input(config: dict):
    # Get controlled switches
    CURRENT_SUPPORTED_SWITCHES = []
    switch_counts = config['switch_numbers'].split(',')
    for i, count in enumerate(switch_counts):
        switch_name = f"s{101 + i}"
        CURRENT_SUPPORTED_SWITCHES.append(switch_name)
        config[switch_name] = count

    # Get total host count
    all_hosts_count = sum(int(config[switch]) for switch in CURRENT_SUPPORTED_SWITCHES)

    if all_hosts_count > 99:
        raise Exception(
            f"The given values result in ({all_hosts_count}) generated host, which is more than actual limitation of "
            f"(99) hosts!")

    if 'filename' not in config or config['filename'] is None or len(config['filename']) == 0:
        print("*** No filename provided, this is considered as a dry-run, results will be printed ***")
        current_config['dry_run'] = True
    else:
        current_config['dry_run'] = False
        filename = config['filename']
        if not filename.lower().endswith(".json"):
            filename += ".json"
        current_config['filename'] = filename
        file_path = f"{OUTPUT_DIR}/{filename}"
        current_config['file_path'] = file_path
        if os.path.isfile(file_path) and not config['force']:
            raise Exception(f"File {filename} already exists in the output directory!")

    return CURRENT_SUPPORTED_SWITCHES


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Hosts Topology Generator",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-sn", "--switch-numbers",
                        help="Comma-separated list of hosts per controlled switch. E.g: 2,2,2,2", required=False)
    parser.add_argument("-th", "--total-hosts", help="Total number of hosts to distribute evenly across switches",
                        required=False, type=int)
    parser.add_argument("-f", "--filename", help="File name to be used for the generated file with hosts (if empty, "
                                                 "no file will be generated and the script will be executed in "
                                                 "dry-run mode)", required=False, default="")
    parser.add_argument("-force", "--force", action="store_true",
                        help="When used and --filename is provided, if the file already exists, it will be overwritten",
                        required=False, default=False)

    config = vars(parser.parse_args())

    # Process switch numbers
    if config['total_hosts'] and not config['switch_numbers']:
        # Calculate switch count (default to 4 switches if not specified)
        num_switches = 4
        # Generate balanced distribution
        total_hosts = config['total_hosts']
        distribution = get_balanced_host_distribution(total_hosts, num_switches)
        config['switch_numbers'] = ','.join(map(str, distribution))
        print(f"*** Balanced distribution: {distribution} hosts per switch ***")
    elif not config['switch_numbers']:
        # Default to traditional setup
        config['switch_numbers'] = "2,2,2,2"
        print("*** Using default distribution: 2,2,2,2 hosts per switch ***")

    switch_counts = config['switch_numbers'].split(',')
    for i, count in enumerate(switch_counts):
        switch_name = f"s{101 + i}"
        config[switch_name] = count

    CURRENT_SUPPORTED_SWITCHES = validate_input(config)

    hosts = {}

    current_host_number = 1
    for switch in CURRENT_SUPPORTED_SWITCHES:
        print(f"*** Processing switch ({switch}) ==> ({config[switch]}) hosts connected ***")
        first_host = ""
        last_host = ""
        for i in range(int(config[switch])):
            host_name = get_host_name(current_host_number)
            append_host(hosts, current_host_number, switch)
            print(f"   > Adding host {host_name} to switch {switch}")
            if len(first_host) == 0:
                first_host = host_name
            last_host = host_name
            current_host_number += 1
        if first_host == last_host:
            print(f" => Switch {switch} has host ({first_host})")
        else:
            print(f" => Switch {switch} has hosts in range ({first_host} ... {last_host})")

    if current_config['dry_run']:
        print(json.dumps(hosts, sort_keys=False, indent=2))
    else:
        file_path = current_config['file_path']
        if os.path.isfile(file_path) and not config['force']:
            raise Exception(f"File {current_config['filename']} already exists in the output directory!")
        with open(file_path, 'w') as f:
            json.dump(hosts, f, sort_keys=False, indent=2)