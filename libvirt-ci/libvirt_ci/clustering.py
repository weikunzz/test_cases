"""
A helper module for clustering strings
"""

import collections

import Levenshtein


class Classifier(object):
    """
    A helper class for online clustering strings into groups
    """
    def __init__(self, alpha=0.6, beta=0.8):
        self.classes = collections.defaultdict(list)
        self.alpha = alpha
        self.beta = beta

    def add(self, string, info=None):
        """
        Add a new string for clustering
        """
        src_words = string.split()
        best = 0.0
        best_str = ""
        for cls_str in self.classes.keys():
            tgt_words = cls_str.split()
            score = self._match_score(src_words, tgt_words)
            if score > self.beta and score > best:
                best = score
                best_str = cls_str
        if best <= 0.0:
            best_str = string

        if not info:
            info = {}
        info['message'] = string

        self.classes[best_str].append(info)
        return best_str, best

    def _match_score(self, src_words, tgt_words):
        src_bag = set(src_words)
        tgt_bag = set(tgt_words)

        common_words = list(src_bag & tgt_bag)
        if not common_words:
            return 0.0

        magic_src = ""
        magic_tgt = ""
        for word in src_words:
            try:
                magic_src += str(common_words.index(word))
            except ValueError:
                continue
        for word in tgt_words:
            try:
                magic_tgt += str(common_words.index(word))
            except ValueError:
                continue

        max_len = max(len(magic_src), len(magic_tgt))
        # Levenshein package use C code to define its functions and can't be
        # recognized by pylint properly.
        # pylint: disable=no-member
        seq_diff = ((max_len - Levenshtein.distance(magic_src, magic_tgt)) /
                    float(max_len))
        str_diff = float(len(common_words)) / len(src_bag | tgt_bag)
        return (1 - self.alpha) * str_diff + self.alpha * seq_diff
