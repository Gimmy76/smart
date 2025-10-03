import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import Shared

prefix_to_ignore = [
    "kworker",
    "rcu_",
    "systemd",
    "ksoftirqd",
    "migration",
    "idle_inject",
    "cpuhp",
    "scsi",
    "card0",
    "gvfs",
    "VBox",
    "gnome",
    "gsd",
    "xdg",
    "ibus",
    "jetbrains",
    "dbus"
]

process_to_ignore = [
    "kthreadd",
    "slub_flushwq",
    "netns",
    "mm_percpu_wq",
    "kdevtmpfs",
    "inet_frag_wq",
    "kauditd",
    "khungtaskd",
    "oom_reaper",
    "writeback",
    "kcompactd0",
    "ksmd",
    "khugepaged",
    "kintegrityd",
    "kblockd",
    "blkcg_punt_bio",
    "tpm_dev_wq",
    "ata_sff",
    "md",
    "edac-poller",
    "devfreq_wq",
    "watchdogd",
    "kswapd0",
    "ecryptfs-kthrea",
    "kthrotld",
    "acpi_thermal_pm",
    "vfio-irqfd-clea",
    "mld",
    "ipv6_addrconf",
    "kstrp",
    "zswap-shrink",
    "charger_manager",
    "jbd2/sda5-8",
    "ext4-rsv-conver",
    "ipmi-msghandler",
    "ttm_swap",
    "irq/18-vmwgfx",
    "iprt-VBoxWQueue",
    "cryptd",
    "ovsdb-server",
    "ovs-vswitchd",
    "accounts-daemon",
    "acpid",
    "avahi-daemon",
    "cron",
    "cupsd",
    "NetworkManager",
    "irqbalance",
    "networkd-dispat",
    "polkitd",
    "rsyslogd",
    "snapd",
    "switcheroo-control",
    "udisksd",
    "wpa_supplicant",
    "avahi-daemon",
    "cups-browsed",
    "ModemManager",
    "watchfrr",
    "zebra",
    "staticd",
    "named",
    "unattended-upgr",
    "whoopsie",
    "kerneloops",
    "sshd",
    "kerneloops",
    "gdm3",
    "gdm-session-worker",
    "(sd-pam)",
    "pulseaudio",
    "tracker-miner-fs",
    "gdm-x-session",
    "Xorg",
    "rtkit-daemon",
    "goa-daemon",
    "goa-identity-service",
    "upowerd",
    "ssh-agent",
    "at-spi-bus-launcher",
    "at-spi2-registryd",
    "evolution-source-registry",
    "evolution-calendar-factory",
    "dconf-service",
    "evolution-addressbook-factory",
    "gjs",
    "evolution-alarm-notify",
    "colord",
    "snap-store",
    "update-notifier",
    "fsnotifier",
    "nautilus",
    "eog"
]

def plot_cpu_memory_usage(file):
    # Read the CSV file
    df = pd.read_csv(file)

    # Group the data by 'Process ID' and 'Process Command'
    grouped = df.groupby([Shared.CSV_COL_PROCESSID_INDEX, Shared.CSV_COL_PROCESSCMD_INDEX])

    cpu_data = np.zeros((1, 0))
    memory_data = np.zeros((1, 0))

    # Create a plot for each process
    max_times = -1
    for (pid, name), group in grouped:
        if not((name in process_to_ignore) or any(name.startswith(prefix) for prefix in prefix_to_ignore)):
            print(f"{pid} - {name}")
            new_max_times = 0
            if max_times == -1:
                new_max_times = max(group[Shared.CSV_COL_TIMES_INDEX]) + 1
            else:
                new_max_times = max(max_times, max(group[Shared.CSV_COL_TIMES_INDEX]) + 1)
            if new_max_times != max_times:
                cpu_data = np.resize(cpu_data, (1, new_max_times))
                memory_data = np.resize(memory_data, (1, new_max_times))
                max_times = new_max_times
            for index, row in group.iterrows():
                item_cpu = row[Shared.CSV_COL_CPU_INDEX]
                item_memory = row[Shared.CSV_COL_MEMORY_INDEX]
                item_time = row[Shared.CSV_COL_TIMES_INDEX]
                cpu_data[0, item_time] += item_cpu
                memory_data[0, item_time] += item_memory
    plt.figure(figsize=(14, 8))

    launching_time = 23
    init_step_time = 114
    first_step_time = 210
    plot_vertical_axes = False
    plot_horizontal_ax = True

    cpu_data /= 14
    max_cpu = max(cpu_data[0][:])

    # Plot CPU usage
    plt.subplot(2, 1, 1)
    plt.plot(list(range(0, len(cpu_data[0]))), cpu_data[0][:], label="(%) CPU usage")
    plt.xlabel('Time (s)')
    plt.ylabel('CPU Usage (%)')
    plt.title(f'Global CPU Usage Over Time')

    if plot_horizontal_ax:
        plt.axhline(y=np.mean(cpu_data[0]), color='red', linestyle='--', label=f'(%) Mean usage')

    if plot_vertical_axes:
        plt.axvline(x=launching_time, color='gray', linestyle='--')
        plt.text(int(launching_time / 2), int(max_cpu), 'Launching\nsimulator', horizontalalignment='center',
                 verticalalignment='top', color='gray')
        plt.axvline(x=init_step_time, color='gray', linestyle='--')
        plt.text(int((init_step_time + launching_time) / 2), int(max_cpu), 'Initialization', horizontalalignment='center',
                 verticalalignment='top', color='gray')
        plt.axvline(x=first_step_time, color='gray', linestyle='--')
        plt.text(int((first_step_time + init_step_time) / 2), int(max_cpu), 'First Step', horizontalalignment='right',
                 verticalalignment='center', color='gray')

    plt.xlim(0, len(cpu_data[0][:]))
    plt.legend()

    memory_baseline = memory_data[0, 0]
    memory_data[memory_data < memory_baseline] = memory_baseline
    memory_data[:] -= memory_baseline
    max_memory = max(memory_data[0][:])

    # Plot Memory usage
    plt.subplot(2, 1, 2)
    plt.plot(list(range(0, len(memory_data[0]))), memory_data[0][:], color='orange', label="(%) Memory usage")
    plt.xlabel('Time (s)')
    plt.ylabel('Memory Usage (%)')
    plt.title(f'Memory Usage Over Time')

    if plot_horizontal_ax:
        plt.axhline(y=np.mean(memory_data[0]), color='red', linestyle='--', label=f'(%) Mean usage')

    if plot_vertical_axes:
        plt.axvline(x=launching_time, color='gray', linestyle='--')
        plt.text(int(launching_time / 2), int(max_memory), 'Launching\nsimulator', horizontalalignment='center',
                 verticalalignment='top', color='gray')
        plt.axvline(x=init_step_time, color='gray', linestyle='--')
        plt.text(int((init_step_time + launching_time) / 2), int(max_memory), 'Initialization',
                 horizontalalignment='center', verticalalignment='top', color='gray')
        plt.axvline(x=first_step_time, color='gray', linestyle='--')
        plt.text(int((first_step_time + init_step_time) / 2), int(max_memory), 'First Step', horizontalalignment='right',
                 verticalalignment='center', color='gray')

    plt.xlim(0, len(memory_data[0][:]))
    plt.legend()

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_cpu_memory_usage('../../reinforcement/tmp/cpu_memory_process_usage_single_episode.csv')
