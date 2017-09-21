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

class CCPropShare(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["threshold"] = 4
        self.num_slots = 3
    
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
            if history.current_round() < self.dummy_state["threshold"]: 
                for piece_id in random.sample(isect, n):
                    # aha! The peer has this piece! Request it.
                    # which part of the piece do we need next?
                    # (must get the next-needed blocks in order)
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
            else:
                piece_request_list = []
                for key, value in sorted(rareness_dict.iteritems(), key= lambda (k, v): (v, k)):
                    if key in av_set and len(piece_request_list) < n:
                        piece_request_list.append(key)

                for piece_id in piece_request_list:
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)

                # rarest first
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)

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
        logging.debug("%s again.  It's round %d." % (
            self.id, curr_round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.
        past_downloads = {}
        if curr_round > 0.0:
            past_downloads = history.downloads[curr_round-1]

        download_dict={}
        for i in past_downloads:
            download_dict[i.from_id] = i.blocks

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to peers")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            chosen = []
            bws = []
            for num, speed in sorted(download_dict.iteritems(), key=lambda (k,v): (v,k)):
                sat = 0
                total_speed = 0
                for j in requests:
                    if num == j.requester_id:
                        total_speed = total_speed + speed
                        if sat == 0:
                            chosen.append(num)
                            sat = 1
                if total_speed != 0:
                    bws.append(total_speed)


            print(chosen)
            print(bws)
            bw_sum = sum(bws)    
            bws = [0.9 * x * self.up_bw / max(bw_sum, 1) for x in bws]
            request = random.choice(requests)
            chosen.append(request.requester_id)
            bws.append(round(0.1 * self.up_bw - 0.4))
            print(chosen)
            print(bws)

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads