import subprocess
import threading
import time
import matplotlib.pyplot as plt

# List of cgroup paths to monitor
# cgroups = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hs']
cgroups = ['hs']
CGROUP_BASE_PATH = "/sys/fs/cgroup/cpuacct"
CGROUP_CPU_USAGE_FILE_NAME = "cpuacct.usage"

# Dictionary to store CPU usage percentages for each cgroup
cpu_usages = {cgroup: [] for cgroup in cgroups}

def get_cpu_usage(cgroup):
    cgroup_path = f"{CGROUP_BASE_PATH}/{cgroup}/{CGROUP_CPU_USAGE_FILE_NAME}"
    while len(cpu_usages[cgroup]) < 60:
        initial_usage = int(subprocess.check_output(['cat', cgroup_path]).strip())
        time.sleep(1)
        final_usage = int(subprocess.check_output(['cat', cgroup_path]).strip())

        usage_diff = final_usage - initial_usage
        num_cpus = 1
        total_time_available = num_cpus * 1000000000  # 1 second = 1,000,000,000 nanoseconds

        cpu_usage_percentage = (usage_diff / total_time_available) * 100
        cpu_usages[cgroup].append(cpu_usage_percentage)

        print(f"{cgroup} CPU Usage: {cpu_usage_percentage:.10f}%")

# Create and start threads for each cgroup
threads = []
for cgroup in cgroups:
    thread = threading.Thread(target=get_cpu_usage, args=(cgroup,))
    threads.append(thread)
    thread.start()

# Wait for all threads to finish
for thread in threads:
    thread.join()

# Plot the CPU usage percentages for each cgroup
plt.figure(figsize=(12, 6))

for cgroup, usages in cpu_usages.items():
    plt.plot(usages, label=f'CPU Usage % ({cgroup})')

plt.xlabel('Seconds')
plt.ylabel('CPU Usage (%)')
plt.title('CPU Usage Percentage Over Time for Multiple cgroups')
plt.legend()
plt.grid(True)
plt.show()