from util import Epsilon

import datetime
import gym
import tensorflow as tf
import numpy as np


def mlp_make_network(obs_shape, n_actions, fcs):
    assert type(fcs) is list and len(fcs) >= 1, "fcs needs to be of type list"
    network_input = tf.keras.Input(shape=obs_shape)
    x = tf.keras.layers.Dense(fcs[0], activation='relu',
                              kernel_initializer=tf.keras.initializers.he_normal())(network_input)
    for fc_size in fcs[1:]:
        x = tf.keras.layers.Dense(fc_size, activation='relu',
                                  kernel_initializer=tf.keras.initializers.he_normal())(x)
    network_output = tf.keras.layers.Dense(n_actions)(x)
    return tf.keras.Model(network_input, network_output)


class Memoryless_DQN_Agent:

    def __init__(self, env,
                 epsilon, gamma, alpha,
                 batch_size, lr,
                 make_network, *make_network_args,
                 random_actions=False, verbose=False,
                 visualise=False, tf_writer=None,
                 reward_style=None):
        self.env = env
        self.obs_shape = env.observation_space.shape
        self.n_actions = env.action_space.n
        self.epsilon = epsilon
        self.gamma = gamma
        self.alpha = alpha
        self.batch_size = batch_size

        self.network = make_network(self.obs_shape, self.n_actions, *make_network_args)
        self.network.compile(optimizer=tf.keras.optimizers.Adam(lr),
                             loss='mse')

        self.rewards = []
        self.ob = self.env.reset()
        self.reward = 0.0

        self.random_actions = random_actions
        self.verbose = verbose
        self.visualise = visualise
        self.tf_writer = tf_writer
        assert reward_style in [None, 'cumulative', 'punish', 'time']
        self.reward_style = reward_style

        self.steps = 0
        self.episodes = 0

    def update_Q_network(self, ob, a, r, ob_next, done):
        ob = np.asarray([ob], dtype="float32")
        state_qs = self.network.predict(ob)[0]
        ob_next = np.asarray([ob_next], dtype="float32")
        state_qs_next = self.network.predict([ob_next])[0]
        max_q_next = max([state_qs_next[a] for a in range(self.n_actions)])
        if done:
            state_qs[a] += self.alpha * r
        else:
            state_qs[a] += self.alpha * (r + self.gamma * max_q_next - state_qs[a])
        state_qs = np.asarray([state_qs], dtype="float32")
        self.network.fit(ob, state_qs, epochs=1, verbose=0)

    def act(self, ob):
        """ given current observation, pick the action with highest q value"""
        if self.random_actions:
            return self.env.action_space.sample()
        if np.random.random() < self.epsilon.value:
            return self.env.action_space.sample()
        ob = np.asarray([ob], dtype="float32")
        states_qs = self.network.predict(ob)[0]
        max_q = max(states_qs)  # Gets max q value
        actions_with_max_q = [a for a, q in enumerate(states_qs) if q == max_q]  # List of actions with max q
        return np.random.choice(actions_with_max_q)  # In the case multiple actions have the max q value

    def modify_reward(self, r, done):
        reward_in = r
        if self.reward_style == 'punish':
            reward_in = r if not done else -20
        elif self.reward_style == 'cumulative':
            reward_in = self.reward
        return reward_in

    def step(self):
        self.steps += 1
        a = self.act(self.ob)
        ob_next, r, done, _ = self.env.step(a)
        if self.visualise:
            self.env.render()
        reward_in = self.modify_reward(r, done)
        self.update_Q_network(self.ob, a, reward_in, ob_next, done)
        self.reward += r
        if done:
            self.episodes += 1
            if self.tf_writer:
                with self.tf_writer.as_default():
                    tf.summary.scalar('episode reward', self.reward, step=self.episodes)
            if self.verbose:
                print(f"{self.episodes} - {self.reward} - {self.epsilon.value}")
            self.rewards.append(self.reward)
            self.epsilon.update_epsilon()
            self.reward = 0.0
            self.ob = self.env.reset()
        else:
            self.ob = ob_next

def main(reward_style=None, env_name="CartPole-v0", n_steps=5000):
    if reward_style is None:
        reward_style_str = "none"
    else:
        reward_style_str = reward_style
    current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = 'logs/dqn/' + current_time
    summary_writer = tf.summary.create_file_writer(log_dir)

    env = gym.make(env_name)
    e = Epsilon(0.1, 0.9, 0.99)
    gamma = 0.99
    alpha = 0.5
    batch_size = 32
    lr = 0.001
    mlp_make_network_args = [[32, 32]]

    agent = Memoryless_DQN_Agent(env,
                                 e, gamma, alpha,
                                 batch_size, lr,
                                 mlp_make_network, *mlp_make_network_args,
                                 random_actions=False, verbose=True,
                                 tf_writer=summary_writer, reward_style=reward_style)
    for i in range(n_steps):
        agent.step()
    env.env.close()


if __name__ == "__main__":
    for i in range(3):
        main()
