# This is a hack to enable GPU rendering.
from dm_control import mujoco
# Load a model from an MJCF XML string.
xml_string = """
<mujoco>
  <worldbody>
    <light name="top" pos="0 0 1.5"/>
    <geom name="floor" type="plane" size="1 1 .1"/>
    <body name="box" pos="0 0 .3">
      <joint name="up_down" type="slide" axis="0 0 1"/>
      <geom name="box" type="box" size=".2 .2 .2" rgba="1 0 0 1"/>
      <geom name="sphere" pos=".2 .2 .2" size=".1" rgba="0 1 0 1"/>
    </body>
  </worldbody>
</mujoco>
"""

physics = mujoco.Physics.from_xml_string(xml_string)
# Render the default camera view as a numpy array of pixels.
pixels = physics.render()

import torch
import torch.nn as nn
from torch.distributions import MultivariateNormal
import gym
import numpy as np
from datetime import datetime
from PIL import Image
import os
import sys
import shelve
from collections import namedtuple
sys.path.insert(0, '/u/pgoyal/Research/metaworld')
sys.path.insert(0, '../supervised')
from metaworld.envs.mujoco.sawyer_xyz.sawyer_random import SawyerRandomEnv
from model import Predict
import pickle
from ppo import Memory, ActorCritic, PPO
from utils import objects, enable_gpu_rendering

def load_env(infile):
    positions = []
    obj_ids = []
    with open(infile) as f:
        for line in f.readlines():
            line = line.replace('(', '').replace(',', '').replace(')', '')
            parts = line.split()
            x = eval(parts[0])
            y = eval(parts[1])
            obj = eval(parts[2])
            print(x, y, obj)
            positions.append((x, y))
            obj_ids.append(obj)

    return positions, obj_ids

class LangModule:
    def __init__(self, args):
        if args:
            self.lang_network = Predict(args.model_file, lr=0, n_updates=0)
            self.descr = self.load_description(args)
        self.reset()

    def encode_description(self, vocab, descr):
        result = []
        for w in descr.split():
            try:
                t = vocab.index(w)
            except ValueError:
                t = vocab.index('<unk>')
            result.append(t)
        return torch.Tensor(result)

    def load_description(self, args, mode='test'):
        vocab = pickle.load(open('../../data/vocab_train.pkl', 'rb'))
        descriptions = pickle.load(open('../../data/{}_descr.pkl'.format(mode), 'rb'))
        return self.encode_description(vocab, descriptions[args.obj_id][args.descr_id])

    def update(self, img_left, img_center, img_right):
        img_left = Image.fromarray(img_left)
        img_left = np.array(img_left.resize((50, 50)))
        img_center = Image.fromarray(img_center)
        img_center = np.array(img_center.resize((50, 50)))
        img_right = Image.fromarray(img_right)
        img_right = np.array(img_right.resize((50, 50)))
        self.traj_r.append(img_right)
        self.traj_l.append(img_left)
        self.traj_c.append(img_center)

    def get_rewards(self, done):
        if done:
            prob = 0
        else:
            prob = self.lang_network.predict(
                self.traj_r, self.traj_l, self.traj_c, self.descr)
        self.potentials.append(prob)
        return self.potentials

    def reset(self):
        self.traj_r = []
        self.traj_l = []
        self.traj_c = []
        self.potentials = []

def main(args):
    ############## Hyperparameters ##############
    log_interval = 1000           # print avg reward in the interval
    max_total_timesteps = args.max_total_timesteps
    if max_total_timesteps == 0:
        max_total_timesteps = np.inf
    
    update_timestep = args.update_timestep # update policy every n timesteps
    action_std = args.action_std            # constant std for action distribution (Multivariate Normal)
    K_epochs = args.K_epochs               # update policy for K epochs
    eps_clip = args.eps_clip              # clip parameter for PPO
    gamma = 0.99                # discount factor
    
    lr = 0.0003                 # parameters for Adam optimizer
    betas = (0.9, 0.999)
    
    # creating environment
    positions, obj_ids = load_env(
        '../../data/envs/obj{}-env{}.txt'.format(args.obj_id, args.env_id))
    state_dim = 6
    action_dim = 4
    if args.output_file:
        outfile = open(args.output_file, 'a')
    else:
        outfile = None

    env = SawyerRandomEnv(
        objects=objects, 
        positions=positions, 
        obj_ids=obj_ids, 
        state_rep='feature', 
        reward_type=args.reward_type,
        max_timesteps = args.max_timesteps)

    if args.reward_type == 'lang':
        lang_module = LangModule(args)
    else:
        lang_module = LangModule(None)

    if args.save_path and os.path.exists(args.save_path):
        with open(args.save_path, 'rb') as f:
            ckpt = pickle.load(f)
        memory = ckpt['memory']
        ppo = ckpt['ppo']
        total_steps = ckpt['total_steps']
        i_episode = ckpt['i_episode']
        time_step = ckpt['time_step']
        success_list = ckpt['success_list']
        state = ckpt['state']
        env = ckpt['env']
        if lang_module:
            lang_module.traj_l = ckpt['traj_l']
            lang_module.traj_r = ckpt['traj_r']
            lang_module.traj_c = ckpt['traj_c']
            lang_module.potentials = ckpt['potentials']
        np.random.set_state(ckpt['np_random_state'])
        torch.random.set_rng_state(ckpt['torch_random_state'])
    else:
        memory = Memory()
        ppo = PPO(args, state_dim, action_dim, action_std, lr, 
            betas, gamma, K_epochs, eps_clip)
        state = env.reset()
        total_steps = 0
        i_episode = 0
        time_step = 0
        success_list = []

    while True:
        while True:
            time_step +=1
            # Running policy_old:
            action = ppo.select_action(state, memory)
            state, reward, done, success = env.step(action)

            if args.reward_type == 'lang':
                img_left, img_center, img_right, _ = env.get_frame()
                lang_module.update(img_left, img_center, img_right)
                potentials = lang_module.get_rewards(done)
                if len(potentials) > 1:
                    reward += (gamma * potentials[-1] - potentials[-2])
            # Saving reward:
            memory.rewards.append(reward)
            
            # update if its time
            if time_step % update_timestep == 0:
                ppo.update(memory)
                memory.clear_memory()
                total_steps += time_step
                time_step = 0

            if (total_steps + time_step) % log_interval == 0:
                current_time = datetime.now().strftime('%H:%M:%S')
                print('[{}] \t Episode {} \t Timesteps: {} \t Success: {}'.format(
                    current_time, i_episode, total_steps + time_step, sum(success_list)),
                    file=outfile, flush=True)
                if args.save_path:
                    ckpt = {
                        'i_episode': i_episode,
                        'total_steps': total_steps,
                        'time_step': time_step,
                        'success_list': success_list,
                        'state': state,
                        'env': env,
                        'traj_l': lang_module.traj_l,
                        'traj_r': lang_module.traj_r,
                        'traj_c': lang_module.traj_c,
                        'potentials': lang_module.potentials,
                        'memory': memory,
                        'ppo': ppo,
                        'np_random_state': np.random.get_state(),
                        'torch_random_state': torch.random.get_rng_state()
                    }
                    with open(args.save_path, 'wb') as f:
                        pickle.dump(ckpt, f)
        
            if done or (total_steps + time_step >= max_total_timesteps):
                break
        
        success_list.append(success)

        if total_steps + time_step >= max_total_timesteps:
            break
        
        if args.save_path:
            if sum(success_list[-5:]) == 5:
                torch.save(ppo.policy.state_dict(), args.save_path)
                break

        i_episode += 1
        env.reset()
        if args.reward_type == 'lang':
            img_left, img_center, img_right, _ = env.get_frame()
            lang_module.reset()
            lang_module.update(img_left, img_center, img_right)

def get_args():
    import argparse
    parser = argparse.ArgumentParser('Train PPO policy')
    parser.add_argument('--random-seed', type=int, help='Environment seed')
    parser.add_argument('--reward-type', help='sparse | dense | lang')
    parser.add_argument('--model-file', help='')
    parser.add_argument('--output-file', help='')
    parser.add_argument('--save-path', help='')
    parser.add_argument('--obj-id', type=int, help='Index of main object; 0-12')
    parser.add_argument('--env-id', type=int, help='Index of environment; 0-99')
    parser.add_argument('--descr-id', type=int, help='Index of description; 0-2')
    parser.add_argument('--max-timesteps', type=int, default=500)
    parser.add_argument('--max-total-timesteps', type=int, default=500000)
    parser.add_argument('--update-timestep', type=int, default=2000)
    parser.add_argument('--action-std', type=float, default=0.5)
    parser.add_argument('--K-epochs', type=int, default=10)
    parser.add_argument('--eps-clip', type=float, default=0.2)
    args = parser.parse_args()
    return args
         
if __name__ == '__main__':
    args = get_args()
    torch.manual_seed(args.random_seed)
    np.random.seed(args.random_seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    print(args)
    main(args)
    
