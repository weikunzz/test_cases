"""
Class to collect all the parameters used for testing
"""


class Parameters(dict):
    """
    Class to collect all the parameters used for testing
    """
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def copy(self):
        res = Parameters()
        for key, value in self.items():
            res[key] = value
        return res
