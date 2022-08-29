# VCube: A Provably Scalable Distributed Diagnosis Algorithm
#November 2014
#DOI: 10.1109/ScalA.2014.14
#Conference: 5th Workshop on Latest Advances in Scalable Algorithms for Large-Scale Systems (ScalA)At: New Orleans

from blocksim.models import vcubechain
from blocksim.models.fd.vcubefd.message import Message
from blocksim.utils import time, get_random_values, get_received_delay, get_sent_delay, get_latency_delay
import math

from blocksim.models.network import Network

class VCube:
    id : int #process address(id), starting from zero
    N : int #number of nodes in the system
    dim : int #vcube dimension = log2(n)
    ts = [] #array of timestamps (size=N) -> int
    correct = [] #array of process' status -> True=correct or False=suspect (size=N)
    pending_info = []
    detection_time = 3
    round_time = 30  
    
    def __init__(self, node, address: str, n: int):
        self.node = node
        self.env = node.env
        self.network_message = Message(self, n)
        self.id = int(address)
        self.N = n
        self.dim = int(math.log2(n))
        self.ts = [0]*n
        self.correct = [True]*n  #all processes are correct at start      

    def run(self):        
        while self.correct[self.id] is True:             
            get_info_message = self.network_message.get_info()            
            for p in self.neighbors():
                print(
                    f'{self.id} at {time(self.env)}: Testing {p}')
                self.env.process(self.node.send(p, get_info_message))
                self.pending_info.append(p)
            yield self.node.env.timeout(self.detection_time)

            #check processes which tests were not answered
            for p in self.pending_info:
                self.suspect(str(p))
            self.pending_info.clear()  

            yield self.node.env.timeout(self.round_time - self.detection_time)  

    def max_correct_id(self) :
        for id in reversed(range(self.N)):
            if self.correct[id] is True:
                return id
        return None

    def _receive_get_info(self, envelope):
        p = envelope.origin.address
        print(
            f'{self.id} at {time(self.env)}: fd_get_info message received from {p}')
        info_message = self.network_message.info() 
        print(
            f'{self.id} at {time(self.env)}: send fd_info message to {p}')
        self.env.process(self.node.send(p, info_message))

    def _receive_info(self, envelope):
        p = envelope.origin.address
        self.pending_info.remove(p)
        print(
            f'{self.id} at {time(self.env)}: fd_info message received from {p}')

        if (self.correct[int(p)] is False): #p is considered suspect
            self.unsuspect(p)

        status = envelope.msg['status']
        ts = envelope.msg['ts']
        #upddate status with info received from tested node
        for i in range(self.N):
            if i not in [id, p] and self.correct[i] != status[i] and self.ts[i] < ts[i]:
                if status[i] is True:
                    self.unsuspect(i)
                else:
                    self.suspect(i)           
        

    @staticmethod
    def cis(i: int, s: int)->list:
        cluster = []
        VCube.cis_rec(cluster, i, s)
        return cluster
    
    @staticmethod
    def cis_rec(cluster:list, i: int, s: int):        
        xor = i^pow(2, s)
        cluster.append(xor)
        for ss in range(s):            
            VCube.cis_rec(cluster, xor, ss)
    
    @staticmethod
    def cluster(i: int, j : int) ->int:
        s=-1
        k = i^j
        while k>0:
            s+=1
            k=k>>1
        return s
    
    def is_correct(self, address: str)->bool:
        return self.correct[int(address)]

    def suspect(self, address: str)->bool: #remove address from correct, if it is correct
        if self.node.crashed == True:
            return

        if self.ts[int(address)] % 2 == 0: #update ts
            self.ts[int(address)] = self.ts[int(address)] +1 
        self.correct[int(address)] = False
        self.node.notify_crash(address)       

    def unsuspect(self, address:str)->bool: #add address to correct, if it is not correct
        if self.node.crashed == True:
            return

        if self.ts[int(address)] % 2 == 1: #update ts
            self.ts[int(address)] = self.ts[int(address)] +1 

        self.correct[int(address)] = True
        self.node.notify_up(address)
    
    def neighbor(self, address: str, s)->str: #check the first correct p in c(i,s), if exists
        cluster = self.cis(int(address), s)
        print ("cis", address, s, cluster)
        for p in cluster:
            if self.is_correct(p):
                return str(p)
        return None

    def neighbors(self, address: str, s=None)->list: #fault-free neighbors from a process i in clusters 1..s
        if s==None:
            s = self.dim
        nb = []
        for ss in range(s):
            p = self.neighbor(address, ss) 
            if p != None:
                nb.append(p)
        return nb
    
    def neighbors(self, s=None)->list: #fault-free neighbors from a process itself in cluseters 1..s
        #print('neighbors s', s)
        if s==None:
            s = self.dim
        nb = []
        for ss in range(s):
            p = self.neighbor(str(self.id), ss) 
            if p != None:
                nb.append(p)
        return nb
