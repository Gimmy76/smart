import numpy as np
import random
import tensorflow as tf
from tensorflow.keras import backend as K

# from keras.utils import plot_model
from tensorflow.python.keras import Input, Model
from tensorflow.python.keras.layers import Dense, Concatenate, Maximum
from tensorflow.python.keras.optimizer_v2.adam import Adam

from Util import Util

from collections import deque

from tensorflow.python.keras.saving.save import load_model


class DoubleDeepQNetwork():
    def __init__(self, config, env, http_client, is_controlled, is_prefilled_actions):
        self.ACTIONS = None
        self.config = config
        self.env = env
        self.http_client = http_client
        self.is_controlled = is_controlled
        self.is_prefilled_actions = is_prefilled_actions
        # self.nS = self.env.INPUT_SHAPE
        self.nA = self.env.OUTPUT_SHAPE
        self.gamma = 0.85
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        # Epsilon decay Values:
        #  2500 ==> 0.998
        #  5000 ==> 0.999
        self.epsilon_decay = config.epsilon_decay
        self.learning_rate = 0.025  #   0.01 0.001
        # self.tau = 0.125 # TODO: Possible future improvement
        self.batch_size = 8
        self.experience_reply_size = 125
        self.experience_replay_memory = deque(maxlen=self.experience_reply_size)
        self.update_target_each = 10 # steps
        self.epoch_count = 10

        self.max_pool = Maximum(name='pool')
        # model is updated instantly
        # target_model updated after each batch
        self.is_play = config.is_play

        self.model = self.build_model()
        if self.is_play:
            self.load_model(f"{config.model_full_path}")
            self.update_model_from_loaded()  # Update weights
        else:
            self.model_target = self.build_model()

        self.loss = []
        self.episode_loss = []
        self.gi_model_input_size = self.env.gi_model_input_size
        self.gi_model_output_size = (self.gi_model_input_size + self.env.nbr_of_host_actions) * 2
        self.goi_model_input_size = self.gi_model_input_size + self.gi_model_output_size + (
                self.env.nbr_of_controlled_switches_function_inputs * self.env.nbr_controlled_switches)
        self.goi_model_output_size = self.env.nbr_of_host_actions

        if is_prefilled_actions:
            self.prefilled_actions = self.read_lines_from_file(config.prefilled_actions_file)
            print("<------> Actions are prefilled:")
            for prefilled_action in self.prefilled_actions:
                print(f"---------> {prefilled_action}")

    def read_lines_from_file(self, file_path):
        with open(file_path, 'r') as file:
            lines = [line.strip() for line in file.readlines() if line.strip()]
            return lines

    def gen_gi_model(self, name):
        """
        Generate a Group Information (GI) model

        This model processes metrics for a group of hosts instead of individual hosts
        (gi) = Group Information model

        Input: Group metrics (statistical aggregations of host metrics in the group)
        Output: Dense representation of group features
        """
        # Group metrics input is larger as it contains statistical aggregations
        input = Input(shape=(self.env.gi_model_input_size,))
        intermediate = Dense(self.env.gi_model_input_size + self.env.gi_model_output_size, activation='relu')(input)
        output = Dense(self.env.gi_model_output_size, activation='relu', kernel_initializer='he_uniform')(intermediate)
        return Model(
            name=name,
            inputs=[input],
            outputs=[output],
        )

    def gen_goi_model(self, name):
        """
        Generate a Group-Oriented Interface (GOI) model
        
        This model replaces the HOI model and works with groups instead of individual hosts
        (goi) = Group-Oriented Interface model
        
        Inputs: 
        - gi: Current group metrics
        - g_pool: Max-pooled metrics from other groups
        - s_input: Switches metrics
        
        Output: Potential redirections for the group
        """
        gi_input = Input(shape=(self.env.gi_model_input_size,))
        g_pool_input = Input(shape=(self.env.gi_model_output_size,))
        s_input = Input(shape=(self.env.controlled_switches_layer_input,))
        concat_layer = Concatenate()([gi_input, g_pool_input, s_input])
        intermediate = Dense(self.env.gi_model_input_size + self.env.gi_model_output_size +
                            self.env.controlled_switches_layer_input + self.env.goi_model_output_size,
                            activation='relu')(concat_layer)
        output = Dense(self.env.goi_model_output_size,)(intermediate)
        return Model(
            name=name,
            inputs=[gi_input, g_pool_input, s_input],
            outputs=[output],
        )


    def gen_do_nothing_model(self, name):
        #
        #       hj -------------\
        #                      (MAX) --- (do_nothing) ---> o
        #       hk -------------/        /
        # (Switches Metrics) -----------/
        #
        # input (group pooled representation + switches metrics)
        # output (1 whether to do nothing)
        #
        h_pool_input = Input(shape=(self.env.gi_model_output_size,))
        s_input = Input(shape=(self.env.controlled_switches_layer_input,))
        concat_layer = Concatenate()([h_pool_input, s_input])
        intermediate = Dense(self.env.gi_model_output_size + self.env.controlled_switches_layer_input + 1, activation='relu')(concat_layer)
        output = Dense(1, )(intermediate)
        return Model(
            name=name,
            inputs=[h_pool_input, s_input],
            outputs=[output],
        )

    def get_s_model(self, name):
        #
        #       hj -------------\               /---> o1
        #                      (MAX) --- (s) --|
        #       hk -------------/        /      \---> o20
        # (Switches Metrics) -----------/
        #
        # input (pooled group representation + switches metrics)
        # output (bandwidth control actions)
        #
        h_pool_input = Input(shape=(self.env.gi_model_output_size,))
        s_input = Input(shape=(self.env.controlled_switches_layer_input,))
        concat_layer = Concatenate()([h_pool_input, s_input])
        intermediate = Dense(self.env.gi_model_output_size + self.env.controlled_switches_layer_input +
                            self.env.s_model_output_size, activation='relu')(concat_layer)
        output = Dense(self.env.s_model_output_size, )(intermediate)
        return Model(
            name=name,
            inputs=[h_pool_input, s_input],
            outputs=[output],
        )

    def build_model(self):
        # Number of groups instead of number of hosts
        num_groups = len(self.env.host_groups) if hasattr(self.env, 'host_groups') else 0
        
        # Ensure we have at least one group
        if num_groups == 0:
            print("Warning: No host groups defined. Using dummy group.")
            num_groups = 1
        
        # Define input sizes dynamically based on actual environment
        self.gi_model_input_size = self.env.gi_model_input_size
        self.gi_model_output_size = self.env.gi_model_output_size
        
        # Create inputs for each group
        gi_inputs = [Input(shape=(self.gi_model_input_size,), name=f"group_{i+1}") for i in range(num_groups)]
        s_inputs = Input(shape=(self.env.controlled_switches_layer_input,), name="cont_switches")

        # Create models
        do_nothing_model = self.gen_do_nothing_model('do_nothing')
        gi_model = self.gen_gi_model("gi_model")
        goi_model = self.gen_goi_model("goi_model")
        s_model = self.get_s_model('s_model')

        # Apply gi_model to each group input
        gis_imp = [gi_model([gi_inputs[i]]) for i in range(num_groups)]

        # Handle max_pool for empty list or single element
        def safe_max_pool(tensor_list):
            if not tensor_list:  # If list is empty
                # Return a zero tensor of appropriate shape
                sample_shape = K.int_shape(gi_model.output)[1:]
                return tf.zeros([1] + list(sample_shape), dtype=tf.float32)
            elif len(tensor_list) == 1:  # If only one element
                return tensor_list[0]  # Return the single element
            else:
                return self.max_pool(tensor_list)

        # Apply do_nothing and s_models 
        do_nothing_imp = do_nothing_model([safe_max_pool(gis_imp), s_inputs])
        s_imp = s_model([safe_max_pool(gis_imp), s_inputs])
        
        # Apply goi_model for each group
        gois_imp = []
        for i in range(num_groups):
            # Pool all group representations except current group
            pool_gi_in = [v for j, v in enumerate(gis_imp) if j != i]
            gi_input = gi_inputs[i]
            pooled_layer = safe_max_pool(pool_gi_in)
            gois_imp.append(goi_model([gi_input, pooled_layer, s_inputs]))

        # Concatenate all outputs
        concat_layer = Concatenate(name="actions")([do_nothing_imp] + gois_imp + [s_imp])
        model = Model(
            name='full-model',
            inputs=gi_inputs + [s_inputs],
            outputs=[concat_layer],
        )
        model.compile(loss="mse", optimizer=Adam(learning_rate=self.learning_rate))

        model.summary()

        return ModelAdapter(model)

    def update_target_from_model(self):
        self.model_target.set_weights(self.model.get_weights())
        print(f'<------> Target Model Updated')

    def update_model_from_loaded(self):
        # Update the target model from the base model
        print(f'----> Original Model:\n')
        self.model.summary()
        for layer in self.model.getLayers():
            print(f"Layer: {layer.name}")
            weights = layer.get_weights()
            for i, weight in enumerate(weights):
                print(f" Weight {i} (size: {weight.shape}):")
                print(weight)
        print(f'<------> Copying Loaded Model Weights...\n')
        self.model.set_weights(self.model_target.get_weights())
        print(f'----> Loaded Model:\n')
        self.model.summary()
        for layer in self.model.getLayers():
            print(f"Layer: {layer.name}")
            weights = layer.get_weights()
            for i, weight in enumerate(weights):
                print(f" Weight {i} (size: {weight.shape}):")
                print(weight)
        print(f'<------> Current Model updated from Loaded Model')

    def action(self, step, state):
        print(f'<------------------ Action with epsilon {self.epsilon} ------------------>\n\n')
        if self.is_controlled:
            return self.do_controlled_prompt()
        if self.is_prefilled_actions:
            return self.do_action_from_prefilled(step)
        # return self.nA - 1 # TODO: Testing purposes only, take no action
        if np.random.rand() <= self.epsilon and not self.is_play:
            action = random.randrange(self.nA)  # Explore
            print(f'<------> Taking action randomly: {action}')
            return action, False
        action_vals = self.model.predict([state])  # Exploit: Use the NN to predict the correct action from this state
        #  action_vals [0] ==> because the output shape is (1, 9) meaning one line and 12 column
        #   so to get the probabilities of taking each of the 9 actions we use the first line (index 0)
        action = np.argmax(action_vals[0])
        print(f'<------> Taking action with predict: {action}')
        return action, True

    def do_controlled_prompt(self):
        action = -1
        while self.is_controlled and action < 0:
            print("Available actions:")
            for i in range(len(self.ACTIONS)):
                ACTION = self.ACTIONS[i]
                ACTIONS_splitted = ACTION.split(':')
                
                if ACTIONS_splitted[0] == "redirect":
                    current_switches, dst_switch = self.get_controlled_redirect_action_with_dist(ACTIONS_splitted)
                    print(f" - {i}: {ACTION} (redirect from {current_switches} to {dst_switch})")
                elif ACTIONS_splitted[0] == "group_action" and ACTIONS_splitted[2] == "redirect":
                    group_name = ACTIONS_splitted[1]
                    dst_switch = ACTIONS_splitted[3]
                    print(f" - {i}: {ACTION} (redirect group {group_name} to {dst_switch})")
                else:
                    print(f" - {i}: {ACTION}")
                    
            action = int(input("Enter action index:"))
            if 0 <= action < self.nA:
                return action, True
            print(f'<------> Action ({action}) is not recognized, please try again!')
            action = -1

    def do_action_from_prefilled(self, step):
        custom_action = self.get_step_index_action_or_nothing(step)
        action = -1
        
        # Handle NOTHING action
        if custom_action == Util.nothing_action():
            action = self.ACTIONS.index(Util.nothing_action()) if Util.nothing_action() in self.ACTIONS else len(self.ACTIONS) - 1
        
        # Handle bandwidth actions
        elif custom_action.startswith("bw"):
            if custom_action in self.ACTIONS:
                action = self.ACTIONS.index(custom_action)
        
        # Handle redirect actions for individual hosts
        elif custom_action.startswith("redirect"):
            custom_action_splitted = custom_action.split(':')
            host_name = custom_action_splitted[1]
            dst_switch = custom_action_splitted[3]
            custom_action_parsed = Util.group_action(host_name, dst_switch)
            print(f'---------> {custom_action} corresponds to {custom_action_parsed}')
            
            if custom_action_parsed in self.ACTIONS:
                action = self.ACTIONS.index(custom_action_parsed)
        
        # Handle group-based actions
        elif custom_action.startswith("group_action"):
            if custom_action in self.ACTIONS:
                action = self.ACTIONS.index(custom_action)
            else:
                print(f'---------> Group action {custom_action} not found in ACTIONS')
        
        # Default to NOTHING if action not found
        if action == -1:
            print(f'---------> Action not found, defaulting to NOTHING')
            action = self.ACTIONS.index(Util.nothing_action()) if Util.nothing_action() in self.ACTIONS else len(self.ACTIONS) - 1
        
        print(f'<------> Taking action with prefilled: {action}')
        return action, True

    def get_controlled_group_redirect_action_with_dist(self, ACTIONS_splitted):
        group_name = ACTIONS_splitted[1]
        dst_switch = ACTIONS_splitted[3]
        group_hosts = []
        
        if hasattr(self.env, 'host_groups') and group_name in self.env.host_groups:
            group_info = self.env.host_groups[group_name]
            group_hosts = group_info['hosts']
            source_switch = group_info['switch']
        else:
            print(f"Warning: Group {group_name} not found in host_groups")
            source_switch = "unknown"
        
        return (f"group {group_name} (switch {source_switch})", dst_switch)

    def get_step_index_action_or_nothing(self, step):
        step_index = step - 1
        custom_action = Util.nothing_action()
        if step_index < len(self.prefilled_actions):
            custom_action = self.prefilled_actions[step_index]
        return custom_action

    def get_controlled_redirect_action_with_dist(self, ACTIONS_splitted):
        host_name = ACTIONS_splitted[1]
        dst_switch = ACTIONS_splitted[3]
        return (host_name, dst_switch)

    def test_action(self, state):  # Exploit
        action_vals = self.model.predict([state])
        return np.argmax(action_vals[0])

    def store(self, state, action, reward, nstate, done):
        # Store the experience in memory
        self.experience_replay_memory.append((state, action, reward, nstate, done))

    def experience_replay(self, batch_size):
        # Execute the experience replay
        # each element of memory is cur_state, action, reward, new_state, done(after each step)
        minibatch = random.sample(self.experience_replay_memory, batch_size)  # Randomly sample from memory

        # Convert to numpy for speed by vectorization
        x = []
        y = []
        st = []  # States
        nst = []  # Next States
        st_predict = []
        nst_predict = []
        nst_predict_target = []
        for i in range(batch_size):  # Creating the state and next state np arrays
            current_st = minibatch[i][0]
            current_nst = minibatch[i][3]
            current_st_predict = self.model.predict([current_st])[0]
            current_nst_predict = self.model.predict([current_nst])[0]
            current_nst_predict_target = self.model_target.predict([current_nst])[0]

            st.append(current_st)
            nst.append(current_nst)
            st_predict.append(current_st_predict)
            nst_predict.append(current_nst_predict)
            nst_predict_target.append(current_nst_predict_target)

        index = 0
        for state, action, reward, nstate, done in minibatch:
            x.append(state)
            # Predict from state
            nst_action_predict_target = nst_predict_target[index]
            nst_action_predict_model = nst_predict[index]
            if done == True:  # Terminal: Just assign reward much like {* (not done) - QB[state][action]}
                target = reward
            else:  # Non terminal
                print(f"<------> reward: {reward} and future reward: {nst_action_predict_target[np.argmax(nst_action_predict_model)]}")
                target = reward + self.gamma * nst_action_predict_target[
                    np.argmax(nst_action_predict_model)]  # Using Q to get T is Double DQN
            target_f = st_predict[index]
            target_f[action] = target
            y.append(target_f)
            index += 1
        hist = self.model.fit(x, y, batch_size=batch_size, epochs=self.epoch_count, verbose=1)
        # Graph Losses
        min_loss = 10000000000
        for i in range(self.epoch_count):
            min_loss = min(min_loss, hist.history['loss'][i])
        self.loss.append(min_loss)
        self.episode_loss.append(min_loss)
        # Decay Epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
            print("<------> New Epsilon value: " + str(self.epsilon))

    def save_model(self, filename):
        self.model_target.save(filename)

    def load_model(self, filename):
        self.model_target = load_model(filename)

    def set_actions(self, ACTIONS):
        self.ACTIONS = ACTIONS


class ModelAdapter:
    def __init__(self, model):
        self.model = model

    def fit(self, x, y, **kwargs):
        if not x or len(x) == 0:
            raise ValueError("Empty input provided to fit method")
        
        inputs = []
        state = x[0]
        
        if len(state) < 2:
            raise ValueError(f"Invalid state format: expected array with groups and switches, got {state}")
        
        # Extract group data and switch data from the state
        groups_array = state[0]  # First element is groups data
        switches_array = state[1]  # Second element is switches data
        
        if len(groups_array) == 0:
            raise ValueError("No group data found in state")
        
        # Add each group's data as a separate input
        for gi_row in groups_array:
            inputs.append(np.expand_dims(gi_row, axis=0))
        
        # Add switches data
        inputs.append(np.expand_dims(switches_array.flatten(), axis=0))

        # Handle multiple states in the batch
        try:
            for i in range(1, len(x)):
                state = x[i]
                groups_array = state[0]
                switches_array = state[1]
                
                # Concatenate each group's data
                for idx, gi_row in enumerate(groups_array):
                    if idx < len(inputs) - 1:  # -1 to account for switches at the end
                        inputs[idx] = np.concatenate((inputs[idx], np.expand_dims(gi_row, axis=0)))
                    else:
                        print(f"Warning: Group index {idx} out of range for inputs with {len(inputs) - 1} groups")
                
                # Concatenate switches data
                inputs[-1] = np.concatenate((inputs[-1], np.expand_dims(switches_array.flatten(), axis=0)))
            
            expected = np.array(y)
            return self.model.fit(inputs, expected, **kwargs)
        except Exception as e:
            print(f"Error during model fitting: {str(e)}")
            # Return a dummy history object as fallback
            from tensorflow.keras.callbacks import History
            history = History()
            history.history = {'loss': [float('inf')]}
            history.params = {}
            history.model = self.model
            return history

    def predict(self, x, **kwargs):
        """
        Predict method that works with the new group-based model structure.
        Compatible with TensorFlow's expected input format.
        """
        if not x or len(x) == 0:
            raise ValueError("Empty input provided to predict method")
        
        state = x[0]
        if len(state) < 2:
            raise ValueError(f"Invalid state format: expected array with groups and switches, got {state}")
        
        groups_array = state[0]  # Group metrics
        switches_array = state[1]  # Switch metrics
        
        if len(groups_array) == 0:
            raise ValueError("No group data found in state")
        
        # Create a list of numpy arrays for each input
        inputs = []
        
        # Add inputs for each group
        for i in range(len(groups_array)):
            inputs.append(np.expand_dims(groups_array[i], axis=0))
        
        # Add input for switches
        inputs.append(np.expand_dims(switches_array.flatten(), axis=0))
        
        # For TensorFlow compatibility, convert to NumPy arrays if needed
        inputs = [np.array(input_arr) for input_arr in inputs]
        
        try:
            # Use direct Keras call to avoid TensorFlow compatibility issues
            return self.model(inputs, training=False).numpy()
        except Exception as e:
            print(f"Error during model prediction: {str(e)}")
            # Return a default prediction (all zeros) as fallback
            output_size = self.model.output_shape[-1]
            return np.zeros((1, output_size))

    def set_weights(self, *args, **kwargs):
        return self.model.set_weights(*args, **kwargs)

    def get_weights(self, *args, **kwargs):
        return self.model.get_weights(*args, **kwargs)

    def save(self, filename):
        self.model.save(filename)

    def summary(self):
        self.model.summary()

    def getLayers(self):
        return self.model.layers