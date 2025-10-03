class Util():

    @staticmethod
    def nothing_action():
        return 'NOTHING'

    @staticmethod
    def bw_action(src_switch, dst_switch, bw_action):
        # bw_action: 0 => Decrease, 1 => Increase
        return f'bw:{src_switch}:{dst_switch}:{bw_action}'

    @staticmethod
    def group_action(group, dst_switch):
        return f'group_action:{group}:redirect:{dst_switch}'

