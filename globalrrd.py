#!/usr/bin/python
# -*- coding: utf-8; -*-

"""
Initialization
==============

    NODEDBPATH=nodedb
    rrdtool create "${NODEDBPATH}/nodes.rrd" --step 60 \
         DS:nodes:GAUGE:120:0:NaN    \
         DS:clients:GAUGE:120:0:NaN  \
         RRA:AVERAGE:0.5:1:120       \
         RRA:AVERAGE:0.5:60:744      \
         RRA:AVERAGE:0.5:1440:1780
"""

import sys
import os, os.path
import json
import subprocess

def count_online(nodes):
	online = 0
	for n in nodes['nodes']:
		if not 'flags' in n:
			continue
		if not 'online' in n['flags']:
			continue
		if not n['flags']['online']:
			continue

		online += 1

	return online

def count_clients(nodes):
	clients = 0
	for n in nodes['nodes']:
		if not 'statistics' in n:
			continue
		if not 'clients' in n['statistics']:
			continue

		clients += n['statistics']['clients']

	return clients

def main():
	if len(sys.argv) != 3:
		print("./globalrrd.py INPATH NODEDBPATH")
		sys.exit(1)

	inpath = sys.argv[1]
	nodedbpath = sys.argv[2]

	nodes_in = os.path.join(inpath, "nodes.json")
	rrdpath = os.path.join(nodedbpath, "nodes.rrd")

	# load
	nodes = json.load(open(nodes_in))

	# evaluate
	online_count = count_online(nodes)
	clients = count_clients(nodes)

	# append
	pargs = ["rrdtool", "update", rrdpath,
	         '--template', 'nodes:clients',
	         'N:%u:%u' % (online_count, clients)]
        subprocess.check_output(pargs)

if __name__ == "__main__":
	main()
