from queue import Empty
from blocksim.models.fd.vcubefd.vcube import VCube
from blocksim.models.node import Node, Envelope
from blocksim.models.network import Network
from blocksim.models.vcubechain.message import Message
from blocksim.models.chain import Chain
from blocksim.models.db import BaseDB
from blocksim.models.consensus import Consensus
from blocksim.models.transaction_queue import TransactionQueue
from blocksim.models.block import Block, BlockHeader
from blocksim.utils import time, get_random_values, get_received_delay, get_sent_delay, get_latency_delay

class VCubeNode(Node):
    leader: str = None #address of the leader process (highest id from correct processes)
    vcube: VCube
    crashed: bool = False
    pending_txs = []

    # Create the VCubeChain genesis block and init the chain
    def __init__(self,
                 env,
                 network: Network,
                 location: str,
                 address: str,
                 n: int,
                 hashrate=0,
                 is_mining=False):
        # Create the genesis block and init the chain
        genesis = Block(BlockHeader())
        consensus = Consensus(env)
        chain = Chain(env, self, consensus, genesis, BaseDB())
        self.hashrate = hashrate
        self.is_mining = is_mining
        if address == str(n-1): # leader is the mining process
            self.hashrate = 1
        super().__init__(env,
                         network,
                         location,
                         address,
                         chain,
                         consensus)
        self.temp_headers = {}
        self.network_message = Message(self)
        if is_mining:
            # Transaction Queue to store the transactions
            self.transaction_queue = TransactionQueue(
                env, self, self.consensus)
        self._handshaking = env.event()
        self.vcube = VCube(self, address, n)        

    def run(self):
        self.env.process(self.vcube.run())

    def is_leader(self) :
        return self.address == self.leader

    def get_leader(self):
        if (self.leader == None):
            self.check_leader()
        print(
                f'{self.address} at {time(self.env)}: Leader is {self.leader}')
        return self.leader
    
    def new_leader(self):
    	if (self.crashed == True):
    	    new_leader = str(self.vcube.max_correct_id()-1)
    	    self.leader = new_leader
    	return self.leader 
        
    def check_leader(self):
        new_leader = str(self.vcube.max_correct_id()) 
        if new_leader != self.leader:
            print(
                f'{self.address} at {time(self.env)}: New leader {new_leader}')
            self.leader = new_leader
            if self.is_leader() is False:
                super().connect([self.network.get_node(self.leader)])
            else:
                self.is_mining = True
                self.hashrate = 1
                self.transaction_queue = TransactionQueue(
                    self.env, self, self.consensus)                
                self._send_leader(self.address, self.leader)             
    
    def _send_leader(self, _from: str, leader: str):
        leader_msg = self.network_message.leader(leader)
        if self.address == _from:
            ss = self.vcube.dim
        else:
            ss = self.vcube.cluster(int(self.address), int(_from))
        for p in self.vcube.neighbors(ss):
            print(
                f'{self.address} at {time(self.env)}: Notify new leader {leader} to {p}')
            self.env.process(self.send(p, leader_msg))
    
    def _receive_leader(self, envelope):
        print(
            f'{self.address} at {time(self.env)}: Leader message received from {envelope.origin.address}')
        self.leader = envelope.msg['leader']
        self.connect([self.network.get_node(self.get_leader())])
        #self.check_leader()
       
        self._handshaking.succeed()
        self._handshaking = self.env.event()
        #print('leader', leader)
        self._send_leader(envelope.origin.address, envelope.msg['leader'])
        

    def build_new_block(self):
        """Builds a new candidate block and propagate it to the network

        We input in our model the block size limit, and also extrapolate the probability
        distribution for the number of transactions per block, based on measurements from
        the public network (https://www.blockchain.com/charts/n-transactions-per-block?timespan=2years).
        If the block size limit is 1 MB, as we know in Bitcoin, we take from the probability
        distribution the number of transactions, but if the user choose to simulate an
        environment with a 2 MB block, we multiply by two the number of transactions.
        With this we can see the performance in different block size limits."""
        if self.is_mining is False:
            raise RuntimeError(f'Node {self.location} is not a miner')
        block_size = self.env.config['vcubechain']['block_size_limit_mb']
        transactions_per_block_dist = self.env.config[
            'vcubechain']['number_transactions_per_block']
        transactions_per_block = int(
            get_random_values(transactions_per_block_dist)[0])
        pending_txs = []
        for i in range(transactions_per_block * block_size):
            if self.transaction_queue.is_empty():
                break
            pending_tx = self.transaction_queue.get()
            pending_txs.append(pending_tx)
        candidate_block = self._build_candidate_block(pending_txs)
        print(
            f'{self.address} at {time(self.env)}: New candidate block #{candidate_block.header.number} created {candidate_block.header.hash[:8]} with difficulty {candidate_block.header.difficulty} and {len(pending_txs)} txs')
        if pending_txs:
            # Add the candidate block to the chain of the miner node
            self.chain.add_block(candidate_block)
            # We need to broadcast the new candidate block across the network
            self.broadcast_new_blocks([candidate_block])

    def _build_candidate_block(self, pending_txs):
        # Get the current head block
        prev_block = self.chain.head
        coinbase = self.address
        timestamp = self.env.now
        difficulty = self.consensus.calc_difficulty(prev_block, timestamp)
        block_number = prev_block.header.number + 1
        candidate_block_header = BlockHeader(
            prev_block.header.hash,
            block_number,
            timestamp,
            coinbase,
            difficulty)
        return Block(candidate_block_header, pending_txs)

    def _read_envelope(self, envelope):
        super()._read_envelope(envelope)
        if envelope.msg['id'] == 'leader':
            self._receive_leader(envelope)
        if envelope.msg['id'] == 'status':
            self._receive_status(envelope)
        if envelope.msg['id'] == 'new_blocks':
            self._receive_new_blocks(envelope)
        if envelope.msg['id'] == 'transactions':
            self._receive_full_transactions(envelope)
        if envelope.msg['id'] == 'get_headers':
            self._send_block_headers(envelope)
        if envelope.msg['id'] == 'block_headers':
            self._receive_block_headers(envelope)
        if envelope.msg['id'] == 'get_block_bodies':
            self._send_block_bodies(envelope)
        if envelope.msg['id'] == 'block_bodies':
            self._receive_block_bodies(envelope)
        if envelope.msg['id'] == 'fd_get_info':
            self.vcube._receive_get_info(envelope)
        if envelope.msg['id'] == 'fd_info':
            self.vcube._receive_info(envelope)
        

    ##              ##
    ## Handshake    ##
    ##              ##

    def connect(self, nodes: list):
        super().connect(nodes)
        self.check_leader()

    def disconnect(self, nodes: list):
        super().disconnect(nodes)

    ##              ##
    ## Transactions ##
    ##              ##

    def request_txs(self, hashes: list, destination_address: str):
        """Request transactions to a specific node by `destination_address`"""
        for tx_hash in hashes:
            self.tx_on_transit[tx_hash] = tx_hash
        get_data_msg = self.network_message.get_data(hashes, 'tx')
        self.env.process(self.send(destination_address, get_data_msg))

    ## replace broadcast from Node ##
    def broadcast(self, msg, _from=None):
        """Broadcast a message to all neighbors in the tree"""
        if self.address == _from or _from == None:
            ss = self.vcube.dim
        else:
            ss = self.vcube.cluster(int(self.address), int(_from))
        nb = self.vcube.neighbors(ss)
        for node_address, node in self.active_sessions.items():
            if (node_address in nb):
                connection = node['connection']
                origin_node = connection.origin_node
                destination_node = connection.destination_node

                # Monitor the transaction propagation on vcubechain
                if msg['id'] == 'transactions':
                    txs = {}
                    for tx in msg['transactions']:
                        txs.update({f'{tx.hash[:8]}': self.env.now})
                    self.env.data['tx_propagation'][f'{origin_node.address}_{destination_node.address}'].update(
                        txs)
                # Monitor the block propagation on vcubechain
                if msg['id'] == 'new_blocks':
                    blocks = {}
                    for block_hash in msg['new_blocks']:
                        blocks.update({f'{block_hash[:8]}': self.env.now})
                    self.env.data['block_propagation'][f'{origin_node.address}_{destination_node.address}'].update(
                        blocks)

                upload_transmission_delay = get_sent_delay(
                    self.env, msg['size'], origin_node.location, destination_node.location)
                yield self.env.timeout(upload_transmission_delay)
                envelope = Envelope(msg, time(self.env),
                                destination_node, origin_node)
                connection.put(envelope)

    def process_txs(self, envelope):
        print(
             f'{self.address} at {time(self.env)}: transactions will be processed by leader {self.address}')
        self._receive_full_transactions(envelope)


    def broadcast_transactions(self, transactions: list, _from:str=None):
        """Send transactions to the leader or process transactions if it is the leader"""
        yield self.connecting  # Wait for all connections
        yield self._handshaking  # Wait for handshaking to be completed
       
        for tx in transactions:
            # Checks if the transaction was previous sent
            try:
                if any({tx.hash} & self.active_sessions.get(self.leader).get('knownTxs')):
                    print(
                        f'{self.address} at {time(self.env)}: Transaction {tx.hash[:8]} was already sent to {self.leader}')
                    transactions.remove(tx)
                else:
                    self._mark_transaction(tx.hash, self.leader)
            except AttributeError as err:
                print(f'{self.address} at active: ', err)
                exit()
        # Only send or process if it has new transactions
        if transactions:
            #print(
            #    f'{self.address} at {time(self.env)}: {len(transactions)} transactions ready to be sent/processed')
            transactions_msg = self.network_message.transactions(transactions, self.address)                       
            if self.is_leader():
                envelope = Envelope(transactions_msg, time(self.env),
                                self.leader, self.address) 
                self.process_txs(envelope)
            else:
                self.pending_txs.append(transactions)
                #print(
                #f'{self.address} at {time(self.env)}: {len(transactions)} transactions_msg')
                self.send_to_leader(transactions_msg)
                
    
    def send_to_leader(self,  msg):
        node = self.active_sessions.get(self.leader)
        connection = node['connection']
        origin_node = connection.origin_node
        destination_node = connection.destination_node
        
        #print(
        #     f'{self.address} at {time(self.env)}: transactions will be sent to {destination_node.location} from {origin_node.location}')
        
        txs = {}
        for tx in msg['transactions']:
            txs.update({f'{tx.hash[:8]}': self.env.now})
        self.env.data['tx_propagation'][f'{origin_node.address}_{destination_node.leader}'].update(
                        txs)
        envelope = Envelope(msg, time(self.env),
                                destination_node, origin_node)
        connection.put(envelope)   
       

    def _receive_full_transactions(self, envelope):
        """Handle full tx received. If node is miner store transactions in a pool (ordered by the gas price)"""
        transactions = envelope.msg.get('transactions')
        valid_transactions = []
        for tx in transactions:
            if self.is_mining: #eq. is_leader
                self.transaction_queue.put(tx)
            else:
                valid_transactions.append(tx)
        #self.env.process(self.broadcast_transactions(valid_transactions, envelope.msg.get('source')))


    ##              ##
    ## Blocks       ##
    ##              ##

    def broadcast_new_blocks(self, new_blocks: list, _from:str=None):
        """Specify one or more new blocks which have appeared on the network.
        To be maximally helpful, nodes should inform peers of all blocks that
        they may not be aware of."""       
        if _from == None:
            _from = self.address
        new_blocks_hashes = {}
        for block in new_blocks:
            new_blocks_hashes[block.header.hash] = block.header.number
        new_blocks_msg = self.network_message.new_blocks(new_blocks_hashes, self.address)
        self.env.process(self.broadcast(new_blocks_msg, _from))

    def _receive_new_blocks(self, envelope):
        """Handle new blocks received.
        The destination only receives the hash and number of the block. It is needed to
        ask for the header and body.
        If node is a miner, we need to interrupt the current candidate block mining process"""
        new_blocks = envelope.msg['new_blocks']
        print(f'{self.address} at {time(self.env)}: New blocks received {new_blocks}')
        # If the block is already known by a node, it does not need to request the block again
        block_numbers = []
        for block_hash, block_number in new_blocks.items():
            if self.chain.get_block(block_hash) is None:
                block_numbers.append(block_number)
        lowest_block_number = min(block_numbers)

        self.env.process(self.broadcast(envelope.msg, envelope.origin.address))

        self.request_headers(
            lowest_block_number, len(new_blocks), envelope.msg.get('source'))

    def request_headers(self, block_number: int, max_headers: int, destination_address: str):
        """Request a node (identified by the `destination_address`) to return block headers.
        At most `max_headers` items.
        """
        get_headers_msg = self.network_message.get_headers(
            block_number, max_headers)
        self.env.process(self.send(destination_address, get_headers_msg))

    def _send_block_headers(self, envelope):
        """Send block headers for any node that request it, identified by the `destination_address`"""
        block_number = envelope.msg.get('block_number', 0)
        max_headers = envelope.msg.get('max_headers', 1)
        block_hash = self.chain.get_blockhash_by_number(block_number)
        block_hashes = self.chain.get_blockhashes_from_hash(
            block_hash, max_headers)
        block_headers = []
        for _block_hash in block_hashes:
            block_header = self.chain.get_block(_block_hash).header
            block_headers.append(block_header)
        print(
            f'{self.address} at {time(self.env)}: {len(block_headers)} Block header(s) preapred to send')
        block_headers_msg = self.network_message.block_headers(block_headers)
        self.env.process(self.send(envelope.origin.address, block_headers_msg))

    def _receive_block_headers(self, envelope):
        """Handle block headers received"""
        block_headers = envelope.msg.get('block_headers')
        # Save the header in a temporary list
        hashes = []
        for header in block_headers:
            self.temp_headers[header.hash] = header
            hashes.append(header.hash)
        self.request_bodies(hashes, envelope.origin.address)

    def request_bodies(self, hashes: list, destination_address: str):
        """Request a node (identified by the `destination_address`) to return block bodies.
        Specify a list of `hashes` that we're interested in.
        """
        get_block_bodies_msg = self.network_message.get_block_bodies(hashes)
        self.env.process(self.send(destination_address, get_block_bodies_msg))

    def _send_block_bodies(self, envelope):
        """Send block bodies for any node that request it, identified by the `envelope.origin.address`.

        In `envelope.msg.hashes` we obtain a list of hashes of block bodies being requested.
        """
        block_bodies = {}
        for block_hash in envelope.msg.get('hashes'):
            block = self.chain.get_block(block_hash)
            block_bodies[block.header.hash] = block.transactions
        print(
            f'{self.address} at {time(self.env)}: {len(block_bodies)} Block bodies(s) preapred to send')
        block_bodies_msg = self.network_message.block_bodies(block_bodies)
        self.env.process(self.send(envelope.origin.address, block_bodies_msg))

    def _receive_block_bodies(self, envelope):
        """Handle block bodies received
        Assemble the block header in a temporary list with the block body received and
        insert it in the blockchain"""
        block_hashes = []
        block_bodies = envelope.msg.get('block_bodies')
        for block_hash, block_txs in block_bodies.items():
            block_hashes.append(block_hash[:8])
            if block_hash in self.temp_headers:
                header = self.temp_headers.get(block_hash)
                new_block = Block(header, block_txs)
                if self.chain.add_block(new_block):
                    del self.temp_headers[block_hash]
                    print(
                        f'{self.address} at {time(self.env)}: Block assembled and added to the tip of the chain  {new_block.header}')


    ##              ##
    ## Faults       ##
    ##              ##

    def notify_crash(self, p: str):
        super().notify_crash(p)
        #find a correct neighbor in p's cluster, if exists
        new_neighbor = self.vcube.neighbor(self.address, self.vcube.cluster(int(self.address), int(p)))
        print(
            f'{self.address} at {time(self.env)}: new neighbor {new_neighbor}')

        if new_neighbor != None:
            self.connect([self.network.get_node(new_neighbor)])
        
    
    def up(self, p: str):    
        super().notify_up(p)
        #self.connect(self.vcube.neighbors())
