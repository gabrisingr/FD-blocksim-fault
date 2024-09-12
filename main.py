import time
import os
import sys
from json import dumps as dump_json
from blocksim.models.node import Node
from blocksim.world import SimulationWorld
from blocksim.node_factory import NodeFactory
from blocksim.transaction_factory import TransactionFactory
from blocksim.models.network import Network

def write_report(world, nodes_list, x):
    dir= './output/'+ str(len(nodes_list))+"/"
    path=dir+ world.blockchain +'_'+str(x)+'.json'
    if not os.path.exists(dir):
        os.mkdir(dir)
        with open(path, 'w') as f:
            pass
    with open(path, 'w') as f:
        f.write(dump_json(world.env.data))


def report_node_chain(world, nodes_list):
    for node in nodes_list:
        head = node.chain.head
        chain_list = []
        num_blocks = 0
        for i in range(head.header.number):
            b = node.chain.get_block_by_number(i)
            chain_list.append(str(b.header))
            num_blocks += 1
        chain_list.append(str(head.header))
        key = f'{node.address}_chain'
        world.env.data[key] = {
            'head_block_hash': f'{head.header.hash[:8]} #{head.header.number}',
            'number_of_blocks': num_blocks,
            'chain_list': chain_list
        }


def get_nodes_by_address(nodes: list, addresses: list)->list:
    nb = []
    for node in nodes:
        if node.address in addresses:
            nb.append(node)
    return nb

def run_model():    
    for n in [4]:
        for x in range(30):              
            now = 0#int(time.time())  # Current time
            duration = 10000 #3200  # seconds

            world = SimulationWorld(
                duration,
                now,
                'input-parameters/config.json',
                'input-parameters/latency.json',
                'input-parameters/throughput-received.json',
                'input-parameters/throughput-sent.json',
                'input-parameters/delays.json')
            
            # Create the network
            network = Network(world.env, 'Internet') #NetworkXPTO

            if world.blockchain not in ['vcubechain', 'fabric']:
                non_miners = {
                    'Ohio': {
                        'how_many': int(n/4),
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Tokyo': {
                        'how_many': int(n/4),
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Ireland': {
                        'how_many': int((n/2)-1),
                        'mega_hashrate_range': "(20, 40)"
                    }
                }
                miners = {
                    'Ohio': {
                        'how_many': 0,
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Tokyo': {
                        'how_many': 0,
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Ireland': {
                        'how_many': int(1),
                        'mega_hashrate_range': "(20, 40)"
                    }
                }
            else: #vcubechain and fabric
                non_miners = {
                    'Ohio': {
                        'how_many': int(n/4),
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Tokyo': {
                        'how_many': int(n/4),
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Ireland': {
                        'how_many': int(n/2),
                        'mega_hashrate_range': "(20, 40)"
                    }
                }
                miners = {
                    'Ohio': {
                        'how_many': 0,
                        'mega_hashrate_range': "(20, 40)"
                    },
                    'Ireland': {
                        'how_many': 0,
                        'mega_hashrate_range': "(20, 40)"
                    }
                }
            node_factory = NodeFactory(world, network)
            # Create all nodes
            nodes_list = node_factory.create_nodes(miners, non_miners)

            dir= './output/'+ str(len(nodes_list))+"/"
            path=dir+ world.blockchain +'_'+str(x)+'.json'
            if not os.path.exists(dir):
                os.mkdir(dir)
            file_path = dir+world.blockchain+'_'+str(x)+'.txt'
            sys.stdout = open(file_path, "w")
            
            print("Running n=",n)

            # Start the network heartbeat
            world.env.process(network.start_heartbeat())
            
            if world.blockchain not in ['vcubechain', 'fabric']:
                # Full Connect all nodes - all2all
                for node in nodes_list:
                    node.connect(nodes_list)
            elif world.blockchain == 'vcubechain':
                # Full Connect all nodes in the vcube    
                for node in nodes_list:
                    node.connect(get_nodes_by_address(nodes_list, node.vcube.neighbors()))
            else:
            	for node in nodes_list:
                    node.connect(get_nodes_by_address(nodes_list, node.gossip.neighbors()))

            transaction_factory = TransactionFactory(world)
            transaction_factory.broadcast(1000, 1, 15, nodes_list) # x times; y transactions; every k seconds.

            # schedule a fault
            def fault(delay, msg, address, n):
                yield world._env.timeout(delay)
                print(f"time {delay}: {msg}")
                #kill node by id
                if world.blockchain not in ['vcubechain', 'fabric']:
                # Crash selected node, remove from the list of current active nodes
                    nodes_list[address].crashed = True
                    nodes_list[address].disconnect(nodes_list)
                elif world.blockchain == 'vcubechain':
                    # Crash selected node, remove from the list of miners
                    nodes_list[address].crashed = True
                    nodes_list[address].is_mining = False
                    #retirar as conexões dele
                    nodes_list[address].hashrate = 0
                    nodes_list[address].disconnect(nodes_list)
                    for node in nodes_list:
                        #suspect fault and remove the address from correct node list
                        node.vcube.suspect(n)
                        #find new leader
                        node.check_leader()
                    nodes_list.pop(address)
                else:
                    #crash node
                    nodes_list[address].crashed = True
                    nodes_list[address].is_mining = False
                    nodes_list[address].hashrate = 0
                    nodes_list[address].disconnect(nodes_list)
                    for node in nodes_list:
                        #suspect fault and remove the address from correct node list
                        node.gossip.suspect(n)
                        #find new leader
                        node.check_leader()
                    nodes_list.pop(address)
                
            world._env.process(fault(500.0, "Hello, World.", -1, 3))

            #for node in nodes_list:
                #node.run() #start FD
            world.start_simulation()

            report_node_chain(world, nodes_list)
            write_report(world, nodes_list, x)  


if __name__ == '__main__':
    #vcube = VCube(8)
    #for s in range(3):
    #    for p in vcube.cis(7,s): #process i, cluster s
    #        print ('cis',p)
    
    #print('is correct?', vcube.is_correct(1))
    #print('neighbor', vcube.neighbor(0,1))

    #print('suspect',vcube.suspect(1))
    #print('is correct?', vcube.is_correct(1))
    #print('neighbor', vcube.neighbor(0,1))

    #print('unsuspect',vcube.unsuspect(1))
    #print('is correct?', vcube.is_correct(1))
    #print('neighbor', vcube.neighbor(0,1))
    run_model()
