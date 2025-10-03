import json
import os

class SwitchGrouper:

    def __init__(self, controlled_switches_list):
        self.controlled_switches_list = controlled_switches_list
        self.switches = sorted(controlled_switches_list)
        self.group_size = 4

    def get_switch_groups(self, json_path=None):
        if json_path and os.path.exists(json_path):
            print(f"Loading switch groups from {json_path}")
            return self._load_switch_groups_from_json(json_path)

        print("Calculating switch groups dynamically")
        return self._calculate_switch_groups()

    def save_switch_groups(self, json_path, content):
        print(f"Saving switch groups to {json_path}")
        with open(json_path, "w") as outfile:
            json.dump(content, outfile)

    def _load_switch_groups_from_json(self, json_path):
        with open(json_path, 'r') as f:
            switch_groups = json.load(f)

        print(f"Loaded {len(switch_groups)} switch groups from {json_path}")
        return switch_groups

    def _calculate_switch_groups(self):
        switch_groups = {
            'groups': [],
            'switch_neighbors': {},
            'switch_neighbors_next': {}
        }
        switch_groups["groups"] = [self.switches[i:i + self.group_size] for i in
                                   range(0, len(self.switches), self.group_size)]
        for lst in switch_groups["groups"]:
            for switch_idx, switch in enumerate(lst):
                switch_groups['switch_neighbors'][switch] = [x for x in lst if x != switch]
                switch_groups['switch_neighbors_next'][switch] = [lst[idx] for idx in range(switch_idx + 1, len(lst))]
        print(f"Calculating switch groups dynamically resulted in {switch_groups} switches")
        return switch_groups


if __name__ == '__main__':
    controlled_switches_list = [f"{i}" for i in range(101, 112)]
    switch_grouper = SwitchGrouper(controlled_switches_list)
    switch_grouper.get_switch_groups()
