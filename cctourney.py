#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import math

from messages import Upload, Request
from util import even_split
from peer import Peer

class CCTourney(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.threshold = 4
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
        logging.debug("%s again.  It's round %d." % (
            self.id, curr_round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.
        past_downloads = {}
        if curr_round > 0.0:
            past_downloads = history.downloads[curr_round-1]

        download_dict = {}
        for download in past_downloads:
            if download.from_id in download_dict:
                download_dict[download.from_id] += download.blocks
            else:
                download_dict[download.from_id] = download.blocks

        chosen_dict = {}
        output_dict = {}
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
        else:
            logging.debug("Still here: uploading to peers")
            # initialize dictionary with peer ids as keys and bandwidth
            # allocated as values
            dl_dict_items = download_dict.items()
            dl_dict_items.sort(key=lambda x: x[1], reverse=True)
            for tup in dl_dict_items:
                num = tup[0]
                speed = tup[1]
                already_chosen = False
                # total speed allows for possibility of getting piece 1 and piece 2
                for request in requests:
                    if num == request.requester_id:
                        if already_chosen == False:
                            chosen_dict[num] = speed
                            already_chosen = True

            bw_sum = sum(chosen_dict.values())
           
            needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
            needed_pieces = filter(needed, range(len(self.pieces)))
            np_set = set(needed_pieces)  
                
            # optimistic unchoking
            random_request = random.choice(requests)
            unchoke_list = []

            # boolean variable for if we have chosen all the requests already,
            # no need for unchoking in that case. 
            for req in requests:
                if req.requester_id not in chosen_dict:
                    for peer in peers:
                        if req.requester_id == peer.id and peer not in unchoke_list:
                            peer_piece_set = peer.available_pieces
                            peer_set = set(peer_piece_set)
                            if len(peer_set.intersection(np_set)) != 0:
                                unchoke_list.append(peer)

            if len(unchoke_list) != 0:
                random_peer = random.choice(unchoke_list)
                output_dict[random_peer.id] = math.floor(0.25 * self.up_bw)
                for x in chosen_dict:  
                    output_dict[x] = math.floor(0.75 * chosen_dict[x] * self.up_bw / max(bw_sum, 1))
                if sum(output_dict.values()) > self.up_bw:
                        print ('e1')
            else:
                for x in output_dict:  
                    output_dict[x] = math.floor(output_dict[x] * self.up_bw / max(bw_sum, 1))
                    if sum(output_dict.values()) > self.up_bw:
                        print ('e2')

            #if unchoke == True:
            #    chosen_dict[random_request.requester_id] = (round(0.1 * self.up_bw - 0.49))
             #   for x in chosen_dict:  
            #        chosen_dict[x] = round((0.9 * chosen_dict[x] * self.up_bw / max(bw_sum, 1)) - 0.49)
            #else:
            #    for x in chosen_dict:  
            #        chosen_dict[x] = round((chosen_dict[x] * self.up_bw / max(bw_sum, 1)) - 0.49)
            # print(chosen)
            # print(bws)
            print(chosen_dict)
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, output_dict[peer_id])
                   for peer_id in output_dict]

        return uploads