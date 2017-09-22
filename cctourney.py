#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class CCTourney(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.threshold = 4
        self.rho = 3
        self.alpha = 0.2
        self.gamma = 0.1
        self.unchoking_fraction = 0.3
        # dictionaries for expected upload and download
        self.expected_dl = {}
        self.expected_ul = {}

    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # NOTE: perhaps sort by upload speed

        rareness_dict = {}

        # calculate rareness
        for peer in peers:
            av_set = set(peer.available_pieces)
            for key in np_set:
                if key in av_set:
                    if key in rareness_dict:
                        rareness_dict[key] += 1
                    else:
                        rareness_dict[key] = 0


        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            # other people have these
            av_set = set(peer.available_pieces)
            # we want these
            isect = av_set.intersection(np_set)

            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            if history.current_round() < self.threshold: 
                for piece_id in random.sample(isect, n):
                    # aha! The peer has this piece! Request it.
                    # which part of the piece do we need next?
                    # (must get the next-needed blocks in order)
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
            else:
                piece_request_list = []
                for key, value in sorted(rareness_dict.iteritems(), key= lambda (k, v): (v, k), reverse=True):
                    if key in av_set:
                        piece_request_list.append(key)

                for piece_id in random.sample(piece_request_list[:max(len(self.pieces)/3, 20)],n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)

                # rarest first
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
       # print("my requests")
       # print(requests)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """
        curr_round = history.current_round()
        # initialize in first round all speeds to 1
        logging.debug("%s again.  It's round %d." % (
                      self.id, curr_round))

        if curr_round == 0:
            for peer in peers:
                self.expected_dl[peer.id] = 0
                self.expected_ul[peer.id] = 1

        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        else:
            # update ratios based on histories
            last_round = history.downloads[curr_round - 1]

            download_dict = {}
            for download in last_round:
                if download.from_id in download_dict:
                    download_dict[download.from_id] += download.blocks
                else:
                    download_dict[download.from_id] = download.blocks

            for peer in peers:
                if peer.id not in download_dict:
                    self.expected_ul[peer.id] = (1 + self.alpha) * self.expected_ul[peer.id]
                else:
                    self.expected_dl[peer.id] = download_dict[peer.id]
                    counter = 0
                    max_round = min(curr_round, self.rho)
                    for i in range(max_round):
                        # print history.downloads
                        # print curr_round
                        # print max_round
                        # print i
                        my_round = history.downloads[curr_round - i - 1]
                        for download in my_round:
                            if download.from_id == peer.id:
                                counter += 1
                    if counter == max_round:
                        self.expected_ul[peer.id] = (1-self.gamma) * self.expected_ul[peer.id]


        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")

            ratio_dict = {}
            chosen = []
            bws = []
            capacity_used = 0

            needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
            needed_pieces = filter(needed, range(len(self.pieces)))
            still_needed_ratio = len(needed_pieces) / len(self.pieces)

            # print self.expected_dl
            for peer in peers:
                ratio_dict[peer.id] = self.expected_dl[peer.id] / self.expected_ul[peer.id]
                for key, value in sorted(ratio_dict.iteritems(), key= lambda (k, v): (v, k), reverse=True):
                    if capacity_used + self.expected_ul[key] <= self.up_bw * (1 - self.unchoking_fraction):
                        chosen.append(key)
                        bws.append(self.expected_ul[key])
                        capacity_used += self.expected_ul[key]

            # Evenly "split" my upload bandwidth among the one chosen requester

            # optimistic unchoking
            bandwidth_remaining =self.unchoking_fraction * self.up_bw
            while (bandwidth_remaining > 1):
                random_request = random.choice(requests)
                # boolean variable for if we have chosen all the requests already,
                # no need for unchoking in that case. 
                unchoke = 0
                for req in requests:
                    if req.requester_id not in chosen:
                        unchoke = unchoke + 1

                while random_request.requester_id in chosen and unchoke > 0:
                        random_request = random.choice(requests)

                if unchoke > 0:
                    chosen.append(random_request.requester_id)
                    # give the person one unit of bandwidth 
                    bws.append(1)
                    bandwidth_remaining = bandwidth_remaining-1
                    unchoke = unchoke - 1
                else:
                    break


                # unchoking fraction decays as we need less pieces
            self.unchoking_fraction = self.unchoking_fraction * still_needed_ratio

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
