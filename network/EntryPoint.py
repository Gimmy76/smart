from mininet.log import setLogLevel
import Shared as shared
import ApiManager as apiMgr
import NetworkManager as netMgr
import argparse

# Complete argument parser function in EntryPoint.py
def create_console_parser():
    parser = argparse.ArgumentParser(description="Mininet Network",
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-s", "--servers", help="Server hosts names. E.g: [h1]", required=False)
    parser.add_argument("-a", "--attackers", help="Attacker hosts names. E.g: [h1]", required=False)
    parser.add_argument("-uhb", "--unified-host-bandwidth", help="When used, all non-server hosts will have same passed bandwidth", required=False)
    parser.add_argument("-usb", "--unified-switch-bandwidth", help="When used, all controlled switches will have same passed bandwidth", required=False)
    parser.add_argument("-mr", "--manuel-receivers", action="store_true", help="Whether to start DITG receivers only on manual request")
    parser.add_argument("-htf", "--hosts-topo-file", help="When given, the provided JSON file in the 'input-data' folder will be used. E.g: hosts-topology-6hosts", required=False, default="hosts-toplogy-6hosts")
    parser.add_argument("-ncs", "--num-controlled-switches", help="Number of controlled switches. Value between 4 and 99.", required=False, type=int, default=4)
    parser.add_argument("-sg", "--switch-groups-json", help="Path to a JSON file containing switch groups", required=False)
    return parser

if __name__ == '__main__':
    setLogLevel('info')  # for CLI output
    parser = create_console_parser()

    config = vars(parser.parse_args())
    shared.init(config)
    
    apiMgr.run_flask(shared.GLOBALS)
    netMgr.run_mininet(shared.GLOBALS)