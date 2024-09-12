from blocksim.utils import kB_to_MB


class Message:
    """Defines a model for the network messages of the VCubeFD.
    """

    def __init__(self, vcube, n):
        """size of the array status - lisf of correct processes"""
        self._vcube = vcube
        self._get_message_size = 1 #TO-DO
        self._info_message_size = 2*n #n*(status + ts) 

    def get_info(self):
        return {
            'id': 'fd_get_info',
            'size': kB_to_MB(self._get_message_size)
        }
    
    def info(self):
        return {
            'id': 'fd_info',
            'status': self._vcube.correct,
            'ts': self._vcube.ts,
            'size': kB_to_MB(self._info_message_size)
        }
