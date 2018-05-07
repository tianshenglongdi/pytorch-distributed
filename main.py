import numpy as np
import os
import torch
import torch.nn as nn
import torch.multiprocessing as mp
# from tensorboardX import SummaryWriter

from utils.options import Options
from utils.factory import ActorDict, LearnerDict, EvaluatorDict, TesterDict
from utils.factory import EnvDict, MemoryDict, ModelDict


if __name__ == '__main__':
    mp.set_start_method("spawn")

    opt = Options()
    torch.manual_seed(opt.seed)
    # board = SummaryWriter(opt.log_dir)

    env_prototype = EnvDict[opt.env_type]
    memory_prototype = MemoryDict[opt.memory_type]
    model_prototype = ModelDict[opt.model_type]
    # board.add_text('config', str(opt.num_actors) + 'actors(x ' +
    #                          str(opt.num_envs_per_actor) + 'envs) + ' +
    #                          str(opt.num_learners) + 'learners' + ' | ' +
    #                          opt.agent_type + ' | ' +
    #                          opt.env_type + ' | ' + opt.game + ' | ' +
    #                          opt.memory_type + ' | ' +
    #                          opt.model_type)

    # dummy env to get state/action/reward_shape
    dummy_env = env_prototype(opt.env_params, opt.num_actors+opt.num_learners+1)
    opt.state_shape = dummy_env.state_shape
    opt.action_shape = dummy_env.action_shape
    opt.reward_shape = opt.agent_params.num_tasks
    del dummy_env
    # shared memory
    opt.memory_params.state_shape = opt.state_shape
    opt.memory_params.action_shape = opt.action_shape
    opt.memory_params.reward_shape = opt.reward_shape
    global_memory = memory_prototype(opt.memory_params)
    # shared model
    # opt.model_params.input_dims = opt.state_shape
    # opt.model_params.output_dims = opt.action_shape
    global_model = model_prototype(opt.model_params, opt.state_shape, opt.action_shape)
    global_model.share_memory() # gradients are allocated lazily, so they are not shared here

    processes = []
    if opt.mode == 1:
        # actor
        actor_fn = ActorDict[opt.agent_type]
        for process_ind in range(opt.num_actors):
            p = mp.Process(target=actor_fn,
                           args=(process_ind, opt,
                                 env_prototype,
                                 model_prototype,
                                 global_memory,
                                 global_model))
            p.start()
            processes.append(p)
        # learner
        learner_fn = LearnerDict[opt.agent_type]
        for process_ind in range(opt.num_learners):
            p = mp.Process(target=learner_fn,
                           args=(opt.num_actors+process_ind, opt,
                                 model_prototype,
                                 global_memory,
                                 global_model))
            p.start()
            processes.append(p)
        # evaluator
        evaluator_fn = EvaluatorDict[opt.agent_type]
        p = mp.Process(target=evaluator_fn,
                       args=(opt.num_actors+opt.num_learners, opt,
                             env_prototype,
                             model_prototype,
                             global_model))
        p.start()
        processes.append(p)
    elif opt.mode == 2:
        # tester
        tester_fn = TesterDict[opt.agent_type]
        p = mp.Process(target=evaluator_fn,
                       args=(opt.num_actors+opt.num_learners+1, opt,
                             env_prototype,
                             model_prototype,
                             global_model))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
