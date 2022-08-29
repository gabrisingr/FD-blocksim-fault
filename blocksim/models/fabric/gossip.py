from random import seed
from random import randint
import time
from blocksim.models.network import Network

class Gossip:
    address : str
    N : int #number of nodes in the system
    k : int #number of neighbors (default=3)
    seed : int #used for random value
    correct : list = [] #list of process/nodes considered correct by i

    def __init__(self, address: str, n: int, k : int=3, _seed=None):        
        self.address = address
        self.N = n
        self.k = k
        if _seed == None:
            _seed = int(time.time())
        self.seed = _seed
        seed(self.seed)
        for p in range(n):
            self.correct.append(str(p)) #add all processes as correct at start
   
    def is_correct(self, address: str)->bool:
        return address in self.correct

    def suspect(self, address: str)->bool: #remove address from correct, if it is correct
        try:
            self.correct.remove(address)
            Network.get_node(self.address).crash()
            return True
        except ValueError:
            return False

    def unsuspect(self, address)->bool: #add address to correct, if it is not correct
        if self.is_correct(address):
            return False
        else:
            self.correct.append(address)
            self.correct.sort(key=int)
            Network.get_node(self.address).up()
            return True
    
    def neighbors(self, _except:list=[])->list: #fault-free neighbors from a process itself
        nb = []
        while len(nb) < self.k:
            p = str(randint(0, self.N))
            if (p != self.address) and  self.is_correct(p) and (p not in nb) and p not in _except:
                nb.append(p)
        return nb
