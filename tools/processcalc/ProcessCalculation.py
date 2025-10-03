import psutil
import csv
import time

import Shared

# This PY file is used to calculate CPU and Memory Usage
#  for all processes running currently in the system

# Run Variables
FILENAME = "../../reinforcement/tmp/cpu_and_memory_usage.csv"     # The file path where the information are to be stored
INTERVAL_S = 1  # Utilisation % during 1 second

def get_process_info():
    process_info = []
    for proc in psutil.process_iter(attrs=[Shared.ATTR_PID, Shared.ATTR_NAME, Shared.ATTR_CPU, Shared.ATTR_MEMORY]):
        try:
            # Get process info with PID, Name, CPU usage, and Memory usage
            pid = proc.info[Shared.ATTR_PID]
            name = proc.info[Shared.ATTR_NAME]
            cpu_percent = proc.info[Shared.ATTR_CPU]
            memory_percent = proc.info[Shared.ATTR_MEMORY]
            process_info.append((pid, name, cpu_percent, memory_percent))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return process_info


def main():

    with open(FILENAME, mode='w', newline='') as file:
        csv_writer = csv.writer(file)
        # Write header
        csv_writer.writerow([Shared.CSV_COL_TIMES_INDEX, Shared.CSV_COL_PROCESSID_INDEX,
                             Shared.CSV_COL_PROCESSCMD_INDEX, Shared.CSV_COL_CPU_INDEX,
                             Shared.CSV_COL_MEMORY_INDEX])

        start_time = time.time()
        sample_time = 0

        while True:
            process_info = get_process_info()
            current_time = time.time()
            elapsed_time = int(current_time - start_time)

            if elapsed_time >= sample_time:
                for pid, name, cpu_percent, memory_percent in process_info:
                    csv_writer.writerow([sample_time, pid, name, cpu_percent, memory_percent])

                sample_time += INTERVAL_S
                time.sleep(INTERVAL_S - (time.time() - current_time))


if __name__ == "__main__":
    main()
