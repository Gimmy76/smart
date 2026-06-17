import random
import numpy as np
from matplotlib.pyplot import cm
import csv
from decimal import Decimal
from Configuration import Configuration
from Environment import Environment
from HttpClient import HttpClient
from CmdManager import CmdManager
from DdqnAgent import DoubleDeepQNetwork
import matplotlib.pyplot as plt
import shutil
import os
import mlflow
import optuna
import hydra
from omegaconf import DictConfig, OmegaConf
from datetime import datetime

from Configuration import Configuration # Ensure Configuration is imported

def copy_cic_step_file(config, new_file_name):
    new_file_full_path = f"{config.cic_folder}/{new_file_name}"
    original_file_full_path = f"{config.cic_output_file_path}"
    shutil.copyfile(original_file_full_path, new_file_full_path)


def get_supported_attack_types():
    return ["ICMP", "TCP", "UDP", "SYN", "HTTP", "POST", "STRESS"]


def get_basic_metrics_headers():
    return ["tx_bytes", "rx_bytes", "bandwidth", "tx_packets", "rx_packets",
            "tx_packets_len", "rx_packets_len", "delivered_pkts", "loss_pct",
            "is_connected", "pkts_s", "bytes_s"]


def get_network_metrics_headers():
    return ["avg_latency_s", "avg_packet_transmission_time_s",
            "throughput_bps", "avg_jitter_s"]


def get_attack_type(config):
    if config.predefined_attack_types:
        return random.choice(config.predefined_attack_types)
    return random.choice(get_supported_attack_types())


def run_experiment(cfg: DictConfig, trial=None):

    mlflow.end_run()
    instance_id = os.environ.get("INSTANCE_ID", "0")
    run_name = f"trial_{instance_id}_{datetime.now().strftime('%H%M%S')}"
    with mlflow.start_run(run_name=run_name):

        # ------------------------------------------------------------------
        # Parametri — in tune mode Optuna li suggerisce, in train mode
        # si usano i valori originali del paper
        # ------------------------------------------------------------------
        if trial:
            lr            = trial.suggest_float("lr",            1e-4, 1e-1, log=True)
            gamma         = trial.suggest_float("gamma",         0.80, 0.99)
            epsilon_decay = trial.suggest_float("epsilon_decay", 0.995, 0.9999)
            batch_size    = trial.suggest_categorical("batch_size", [8, 16, 32, 64])
            increasing_factor = trial.suggest_float("increasing_factor", 0.01, 0.5)
            tolerable_latency = trial.suggest_float("tolerable_latency_s", 0.001, 0.2)
            tolerable_jitter  = trial.suggest_float("tolerable_jitter_s",  0.01, 0.5)
            alpha_weight      = trial.suggest_float("alpha_weight", 0.05, 0.6)
            w_lat             = trial.suggest_categorical("w_lat", [0.5, 1.0, 2.0])
            w_jit             = trial.suggest_categorical("w_jit", [0.5, 1.0, 2.0])
            w_loss            = trial.suggest_float("w_loss", 0.5, 2.0)
            tolerable_loss    = trial.suggest_float("tolerable_loss", 0.10, 0.45)
            threshold_loss    = trial.suggest_float("threshold_loss", 0.01, 0.10)
        else:
            # Valori originali SMART — NON modificati
            lr            = 0.00006
            gamma         = 0.932
            epsilon_decay = 0.9997
            batch_size    = 32
            increasing_factor = 0.1
            tolerable_latency = 0.00001
            tolerable_jitter  = 0.05
            alpha_weight      = 0.2
            w_lat             = 2.0
            w_jit             = 2.0
            w_loss            = 1.0
            tolerable_loss    = 0.20
            threshold_loss    = 0.05

        mlflow.log_params({
            "lr": lr, "gamma": gamma,
            "epsilon_decay": epsilon_decay,
            "batch_size": batch_size,
            "increasing_factor": increasing_factor,
            "tolerable_latency_s": tolerable_latency,
            "tolerable_jitter_s": tolerable_jitter,
            "alpha_weight": alpha_weight,
            "w_lat": w_lat,
            "w_jit": w_jit,
            "w_loss": w_loss,
            "tolerable_loss": tolerable_loss,
            "threshold_loss": threshold_loss,
            "episodes": cfg.episodes,
            "steps": cfg.steps,
            "hosts_topo": cfg.hosts_topo
        })

        # ------------------------------------------------------------------
        # Setup
        # ------------------------------------------------------------------
        hosts_topo = cfg.hosts_topo
        if not hosts_topo.endswith('.json'):
            hosts_topo += '.json'

        predefined_attack_types = None
        if cfg.get("predefined_attack_types", None) and cfg.get("predefined_attack_types", None) != "":
            predefined_attack_types = cfg.predefined_attack_types.strip('[]').split(',')

        pre_set_attackers = list(cfg.get('attackers', []))

        config = Configuration(hosts_topo, cfg.episodes, cfg.steps, epsilon_decay, predefined_attack_types)
        env = Environment(config, pre_set_attackers)
        cmd = CmdManager(config)
        http_client = HttpClient(config)

        # Imposta INCREASING_FACTOR se suggerito da Optuna
        if hasattr(env, 'INCREASING_FACTOR'):
            env.INCREASING_FACTOR   = increasing_factor
            env.tolerable_latency_s = tolerable_latency
            env.tolerable_jitter_s  = tolerable_jitter
            env.alpha_weight        = alpha_weight
            env.w_lat               = w_lat
            env.w_jit               = w_jit
            env.w_loss              = w_loss
            env.tolerable_loss      = tolerable_loss
            env.threshold_loss      = threshold_loss

        ddqn_agent = DoubleDeepQNetwork(config, env, http_client,
                                        is_controlled=False,
                                        is_prefilled_actions=False)
        # Applica parametri suggeriti da Optuna
        ddqn_agent.gamma = gamma
        ddqn_agent.learning_rate = lr
        ddqn_agent.batch_size = batch_size
        ddqn_agent.experience_replay_memory = __import__("collections").deque(maxlen=max(125, batch_size * 4))

        total_rewards_per_episode = []
        current_run_dir = config.current_train_folder
        os.makedirs(os.path.join(current_run_dir, 'rl_stats'), exist_ok=True)

        try:
            for episode in range(1, cfg.episodes + 1):
                tot_episode_reward = 0
                env.reset()
                env.update_hosts()
                env.perform_setup(http_client, pre_set_attackers)
                ddqn_agent.set_actions(env.ACTIONS)
                cmd.start_network_in_background(env.servers, env.attacker_hosts,
                                                config.hosts_topo_file_name)
                env.update_hosts_ips(http_client)
                env.update_interfaces(http_client.get_switches_interfaces())
                tshark_ids = env.get_tshark_interfaces_ids(cmd)

                sender_receiver_relation = {h: random.choice(env.servers)
                                            for h in env.normal_hosts}
                attacker_victim_relation = {a: random.choice(env.victim_servers)
                                            for a in env.attacker_hosts}
                attack_types = {a: get_attack_type(config)
                                for a in env.attacker_hosts}

                current_state = env.get_state(
                    config, cmd, http_client, tshark_ids,
                    sender_receiver_relation, attacker_victim_relation, attack_types
                )

                env.last_recorded_latency = env.calculate_latency(current_state)
                env.last_recorded_jitter  = env.calculate_jitter(current_state)
                env.last_recorded_delay   = env.calculate_delay(current_state)
                env.before_last_recorded_delay = env.last_recorded_delay
                if hasattr(env, 'latency_tracker'):
                    env.latency_tracker.add_value(env.last_recorded_latency)
                if hasattr(env, 'jitter_tracker'):
                    env.jitter_tracker.add_value(env.last_recorded_jitter)

                for step in range(1, cfg.steps + 1):
                    print(f"(RL) Ep{episode}/{cfg.episodes} Step{step}/{cfg.steps}")
                    # Ricalcola tshark_ids ad ogni step
                    tshark_ids = env.get_tshark_interfaces_ids(cmd)

                    state_vec = env.transform_state_dict_to_normalized_vector(current_state)
                    action, is_predicted = ddqn_agent.action(step, state_vec)

                    new_state, reward, done, loss_val, delay, latency, jitter = \
                        env.apply_action_controlled_switches(
                            config, cmd, http_client, tshark_ids,
                            sender_receiver_relation, attacker_victim_relation,
                            attack_types, action, is_predicted
                        )

                    # Save timing measurements to CSV
                    try:
                        env.save_timing_to_csv(config, episode, step)
                    except Exception as _e:
                        print(f"(Timing) save_timing_to_csv failed: {_e}")

                    reward_val = float(reward)
                    tot_episode_reward += reward_val

                    global_step = (episode - 1) * cfg.steps + step
                    mlflow.log_metric("episode_num",      episode,        step=global_step)
                    mlflow.log_metric("step_in_episode",  step,           step=global_step)
                    mlflow.log_metric("latency_step",     latency,        step=global_step)
                    mlflow.log_metric("jitter_step",      jitter,         step=global_step)
                    mlflow.log_metric("delay_step",       delay,          step=global_step)
                    mlflow.log_metric("reward_step",      reward_val,     step=global_step)
                    mlflow.log_metric("packet_loss_pct",  loss_val * 100, step=global_step)
                    mlflow.log_metric("epsilon",          ddqn_agent.epsilon, step=global_step)

                    next_state_vec = env.transform_state_dict_to_normalized_vector(new_state)
                    ddqn_agent.store(state_vec, action, reward_val, next_state_vec, done)

                    if len(ddqn_agent.experience_replay_memory) > ddqn_agent.batch_size:
                        ddqn_agent.experience_replay(ddqn_agent.batch_size)

                    current_state = new_state
                    # In modalità tune non terminiamo mai l'episodio anticipatamente
                    if done and cfg.mode == "tune":
                        done = False
                    elif done:
                        break

                total_rewards_per_episode.append(tot_episode_reward)
                mlflow.log_metric("episode_total_reward", tot_episode_reward, step=episode)

                # Salva CSV locale
                import csv as _csv
                csv_path = os.path.join(current_run_dir, "rl_stats", f"episode_{episode}_rewards.csv")
                with open(csv_path, 'w', newline='') as _f:
                    _w = _csv.writer(_f)
                    _w.writerow(["episode", "total_reward", "lr", "gamma",
                                 "epsilon_decay", "batch_size", "tolerable_latency_s",
                                 "tolerable_jitter_s", "alpha_weight"])
                    _w.writerow([episode, tot_episode_reward, lr, gamma,
                                 epsilon_decay, batch_size, tolerable_latency,
                                 tolerable_jitter, alpha_weight])
                print(f"(RL) Episode {episode} finished. Reward: {tot_episode_reward:.4f}")
                cmd.stop_network()

        except Exception as e:
            mlflow.set_tag("status", "FAILED")
            print(f"CRITICAL ERROR: {e}")
            try:
                cmd.stop_network()
            except:
                pass
            raise

        avg_reward = float(np.mean(total_rewards_per_episode))
        mlflow.log_metric("final_average_reward", avg_reward)
        mlflow.set_tag("status", "OK")
        print(f"(RL) Experiment finished. avg_reward={avg_reward:.4f}")
        return avg_reward


@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg: DictConfig):

    mlflow.set_tracking_uri("http://127.0.0.1:5051")
    mlflow.set_experiment("SMART_Optimization")

    if cfg.mode == "tune":
        print("[INFO] Starting Optuna autotuning...")
        instance_id = os.environ.get("INSTANCE_ID", "0")
        parent_run_name = f"trial_{instance_id}"
        mlflow.start_run(run_name=parent_run_name)
        mlflow.set_tag("mode", "tune")
        if True:  # placeholder per mantenere indentazione
            mlflow.log_param("n_trials", cfg.tune_trials)

            study = optuna.create_study(direction="maximize")
            study.optimize(
                lambda trial: run_experiment(cfg, trial),
                n_trials=cfg.tune_trials
            )

            best = study.best_trial
            print(f"\n[RESULT] Best trial #{best.number} avg_reward={best.value:.4f}")
            for k, v in best.params.items():
                print(f"  {k}: {v}")
                mlflow.log_param(f"best_{k}", v)
            mlflow.log_metric("best_avg_reward", best.value)

            with open("best_params.yaml", "w") as f:
                OmegaConf.save(config=OmegaConf.create(study.best_params), f=f)
            print("[INFO] Best params saved to best_params.yaml")

    else:
        print("[INFO] Starting standard training...")
        with mlflow.start_run(run_name="standard_train"):
            mlflow.set_tag("mode", "train")
            run_experiment(cfg)

    print("[FINISH] Run completed.")


if __name__ == '__main__':
    main()
