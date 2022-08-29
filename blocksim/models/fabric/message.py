from blocksim.utils import kB_to_MB


class Message:
    """Defines a model for the network messages of the Fabric blockchain.

    For each message its calculated the size, taking into account measurements from the live and public network.
    """

    def __init__(self, origin_node):
        self._origin_node = origin_node
        _env = origin_node.env
        self._message_size = _env.config['fabric']['message_size_kB']
        self._header_size = self._message_size['header']

    def leader(self, leader: str):
        """ When a node notifies a new leader"""
        return {
            'id': 'leader',
            'leader': leader,
            'size': kB_to_MB(self._header_size + self._message_size['leader'])
        }

    def new_blocks(self, new_blocks: dict, _from: str):
        """Advertises one or more new blocks which have appeared on the network"""
        num_new_block_hashes = len(new_blocks)
        new_blocks_size = num_new_block_hashes * \
            self._message_size['hash_size']
        return {
            'id': 'new_blocks',
            'new_blocks': new_blocks,
            'source': _from,
            'size': kB_to_MB(new_blocks_size)
        }

    def transactions(self, transactions: list, _from:str):
        """ Specify (a) transaction(s) that the peer should make sure is included on its
        transaction queue. Nodes must not resend the same transaction to a peer in the same session.
        This packet must contain at least one (new) transaction.
        """
        num_txs = len(transactions)
        transactions_size = num_txs * self._message_size['tx']
        return {
            'id': 'transactions',
            'transactions': transactions,
            'size': kB_to_MB(transactions_size),
            'source': _from
        }

    def get_headers(self, block_number: int, max_headers: int):
        return {
            'id': 'get_headers',
            'block_number': block_number,
            'max_headers': max_headers,
            'size': kB_to_MB(self._message_size['get_headers'])
        }

    def block_headers(self, block_headers: list):
        """ Reply to `get_headers` the items in the list are block headers.
        This may contain no block headers if no block headers were able to be returned
        for the `get_headers` message.
        """
        num_headers = len(block_headers)
        block_headers_size = num_headers * self._message_size['header']
        return {
            'id': 'block_headers',
            'block_headers': block_headers,
            'size': kB_to_MB(block_headers_size)
        }

    def get_block_bodies(self, hashes: list):
        block_bodies_size = len(hashes) * self._message_size['hash_size']
        return {
            'id': 'get_block_bodies',
            'hashes': hashes,
            'size': kB_to_MB(block_bodies_size)
        }

    def block_bodies(self, block_bodies: dict):
        """ Reply to `get_block_bodies`. The items in the list are some of the blocks, minus the header.
        This may contain no items if no blocks were able to be returned for the `get_block_bodies` message.
        """
        txsCount = 0
        for block_hash, block_txs in block_bodies.items():
            txsCount += len(block_txs)
        message_size = (
            txsCount * self._message_size['tx']) + self._message_size['block_bodies']
        print(
            f'block bodies with {txsCount} txs have a message size: {message_size} kB')
        return {
            'id': 'block_bodies',
            'block_bodies': block_bodies,
            'size': kB_to_MB(message_size)
        }