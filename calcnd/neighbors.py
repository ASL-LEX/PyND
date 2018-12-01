import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(name)s - %(asctime)-14s %(levelname)-8s: %(message)s',
                              "%m-%d %H:%M:%S")

ch.setFormatter(formatter)

logger.handlers = []  # in case module is reload()'ed, start with no handlers
logger.addHandler(ch)


class Neighbors(object):
    """lexical neighborhood

    Args:
        data (pandas.DataFrame): a dataframe containing a column
            called Code, and columns with names matching the elements of
            'features'
        features (list of str): a character vector containing the column names in
             "data" over which to calculate neighborhood densities
        allowed_misses (int): an integer indicating how many features
             are allowed to differ between the target word and the
             candidate word while still considering the candidate a
             neighbor
        allowed_matches (int): (default:length(features)) an integer
            indicating the maximum number of features that are allowed to
            match between the target word and the candidate word while still
            considering the candidate a neighbor
    """
    def __init__(self, data, features, allowed_misses=0, allowed_matches=None):
        self.data = data
        self.features = list(features)

        missing_features = [
            x for x in self.features if x not in list(self.data.columns.values)]
        if missing_features:
            msg = "Feature(s) {} not in DataFrame data".format(missing_features)
            raise ValueError(msg)

        self.allowed_misses = allowed_misses
        if self.allowed_misses > len(self.features)-1:
            raise ValueError("allowed_misses must be less than or equal to"
                             " (length(features) - 1)")
        elif self.allowed_misses < 0:
            raise ValueError("allowed_misses must be >=0")

        self.allowed_matches = allowed_matches
        if self.allowed_matches is None:
            self.allowed_matches = len(self.features)
        elif self.allowed_matches > len(self.features):
            raise ValueError("allowed_matches cannot exceed length(features)")
        elif self.allowed_matches < 1:
            raise ValueError("allowed_matches must be greater than 1")

        logger.debug("len(data.index): %d" % len(data.index))
        logger.debug("len(features): %d" % len(features))
        logger.debug("features: %s " % features)

        self.nd, self.neighbors = self._Compute()

    def _MatchFeature(self, i, j, feature):
        """Check whether items match on a given feature

        Args:
            i, j (int): indices of items to evaluate
            feature (str): feature on which to evaluate match

        Returns:
           bool `True` if match is found, `False` otherwise
        """
        result = False
        if ((pd.notna(self.data.iloc[i, self.data.columns.get_loc(feature)]) and
             pd.notna(self.data.iloc[j, self.data.columns.get_loc(feature)])) and
            (self.data.iloc[i, self.data.columns.get_loc(feature)] ==
             self.data.iloc[j, self.data.columns.get_loc(feature)])):
            result = True
        return(result)

    def _MirrorNeighbors(self):
        """Mirrors a neighbors DataFrame from MinimalPairND

        Mirror the neighbors DataFrame such that every A-B pair appears as
        both A(target)-B(neighbor) and B(target)-A(neighbor)

        Args:
            df (pandas.DataFrame): a neighbors DataFrame from MinimalPairND()

        Returns:
            A pandas.DataFrame with twice as many rows as the input df,
            sorted by target, then neighbor
        """
        fd = self.neighbors.copy()

        fd.loc[:, 'target'] = self.neighbors.loc[:, 'neighbor']
        fd.loc[:, 'neighbor'] = self.neighbors.loc[:, 'target']

        result = pd.concat([self.neighbors, fd])
        result = result.sort_values(by=['target', 'neighbor'])
        return(result)

    @property
    def Neighbors(self, mirror_neighbors=True):
        """accessor for neighbors DataFrame"""
        if mirror_neighbors:
            return(self._MirrorNeighbors())
        else:
            return(self.neighbors)

    @property
    def ND(self):
        """accessor for neighborhood density DataFrame"""
        return(self.nd)

    def _FormatHMS(self, s):
        """formats a duration in seconds into `H:MM:SS.ms`

        Args:
            s (float): time in seconds

        Returns:
            string
        """
        hours, remainder = divmod(s, 60**2)
        minutes, seconds = divmod(remainder, 60)
        return("{:.0f}:{:02.0f}:{:05.2f}".format(hours, minutes, seconds))

    def _Compute(self):
        """compute neighborhood density

        Returns:
          (DataFrame): database of items with additional column for computed
            neighborhood density
          (DataFrame): pairs of neighbors
        """
        start_time = time.monotonic()

        nbr_target = []
        nbr_neighbor = []
        nbr_num_match_features = []
        nbr_match_features = []
        out_df = self.data.copy()
        nd = [0] * len(self.data.index)

        # outer loop will be stepping through words (source word)
        it_start_time = time.monotonic()
        it_start_iter = 0
        for i in range(0, len(self.data.index)):
            msg = 'starting word {} of {}, "{}"'
            msg = msg.format(i+1, len(self.data.index),
                             self.data.iloc[i, self.data.columns.get_loc("Code")])
            if i == 0:
                logger.info(msg)
            elif (i+1) % 10 == 0:
                frac_complete = i/len(self.data.index)
                et = time.monotonic() - it_start_time
                try:
                    rate = (i - it_start_iter)/et
                except ZeroDivisionError:
                    rate = float("inf")
                etc = (len(self.data.index)-i) * 1/rate
                logger.debug("i: %s etc: %s" % (i, etc))
                logger.debug("self._FormatHMS(etc): %s" % self._FormatHMS(etc))

                msg2 = (".. {complete:.1%} complete, {rate:.2f} words/sec."
                        + " Est. {etc}"
                        + " (H:MM:SS.ms) remaining.")
                msg2 = msg2.format(complete=frac_complete, rate=rate,
                                   etc=self._FormatHMS(etc))
                logger.info(msg2)
                logger.info(msg)
                it_start_time = time.monotonic()
                it_start_iter = i
            else:
                logger.debug(msg)
            # second level loop will also be stepping through words (candidate word)
            # for j in range(0, len(self.data.index)):
            for j in range(i, len(self.data.index)):
                if (i != j):  # TODO: change starting index to i+1 and remove this conditional
                    matches = 0
                    matched_features = ""
                    # third-level loop will step through features,
                    # counting the number of features of the candidate
                    # word that match the source word. If the matches
                    # equal or exceed (len(features) - allowed_misses),
                    # put the candidate word into the list of neighbors
                    for k in range(0, len(self.features)):
                        if self._MatchFeature(i, j, self.features[k]):
                            source = self.data.iloc[i, self.data.columns.get_loc("Code")],
                            target = self.data.iloc[j, self.data.columns.get_loc("Code")],
                            feature = self.features[k]
                            msg = "Matched {source} to {target} on feature {feature}"
                            msg = msg.format(source=source, target=target, feature=feature)
                            logger.debug(msg)
                            matches = matches + 1
                            if matched_features == "":
                                matched_features = self.features[k]
                            else:
                                matched_features = ", ".join([matched_features,
                                                              self.features[k]])

                    if (matches >= (len(self.features) - self.allowed_misses) and
                            matches <= self.allowed_matches):
                        logger.debug("adding match to neighbors")
                        nbr_target.append(self.data.iloc[i, self.data.columns.get_loc("Code")])
                        nbr_neighbor.append(self.data.iloc[j, self.data.columns.get_loc("Code")])
                        nbr_num_match_features.append(matches)
                        nbr_match_features.append(matched_features)
                        logger.debug("incrementing neighborhood density"
                                     + "for both members of the pair")
                        nd[i] += 1
                        nd[j] += 1

            # back to i loop
        data_dict = {'target': nbr_target,
                     'neighbor': nbr_neighbor,
                     'num_matched_features': nbr_num_match_features,
                     'matched_features': nbr_match_features}

        neighbors = pd.DataFrame(data_dict)
        elapsed_time = time.monotonic() - start_time
        msg = "completed {words} words in {et} (H:MM:SS.ms) ({rate:.2f} word/sec)"
        msg = msg.format(words=len(self.data.index),
                         et=self._FormatHMS(elapsed_time),
                         rate=len(self.data.index)/elapsed_time)
        logger.info(msg)

        out_df['Neighborhood Density'] = nd

        return(out_df, neighbors)
